import re
import math
import pandas as pd
from histogram_builder.equi_depth_builder import EquiDepthHistogramBuilderWithDP

NULL_TAG = 'null'

class StrHistogramWrapper:
  OPERATORS = sorted(['=', '!=', 'in', 'like', 'ilike'], key=len, reverse=True)

  def __init__(self, data):
    self.is_nullable = data['is-nullable']
    self.mapping = data['crutch']['mapping']

  def split_str_pred(self, pred_col, pred):
    op_pattern = '|'.join(map(re.escape, self.OPERATORS))
    re_str = rf"{re.escape(pred_col)}\s*({op_pattern})\s*(?:\(\s*)?'([^']*)'(?:\s*,\s*'([^']*)')*(?:\s*\))?"

    str_match = re.finditer(re_str, pred, re.IGNORECASE)
    matches = next(str_match, None)
    assert matches, 'Invalid SQL predicate format.'

    # Get the operator.
    operator = matches.group(1)

    # Extract values separately.
    values_str = matches.group(0)
    values = re.findall(r"'([^']*)'", values_str)

    # And return.
    return operator.lower(), values

  def predict_bin(self, x):
    assert x in self.mapping
    return self.mapping[x]

  def translate(self, col_name, pred, pred_col):
    # print(f'[Str::translate] {pred} {pred_col}')

    # Check for `IS (NOT) NULL`.
    if pred.lower() == f'{pred_col} is not null':
      # TODO: Adapt this later.
      if self.is_nullable:
        assert NULL_TAG in self.mapping
        return f'{col_name} != {self.mapping[NULL_TAG]}'
      else:
        return 'true'
    elif pred.lower() == f'{pred_col} is null':
      if self.is_nullable:
        return f'{col_name} = {self.mapping[NULL_TAG]}'
      else:
        return 'false'

    op, val = self.split_str_pred(pred_col, pred)
    # print(f'op={op}, val={val}')
    assert op in self.OPERATORS, 'Invalid SQL operator.'

    if op == '=':
      assert len(val) == 1
      val = val[0]
      bin = self.predict_bin(val)
      return f"{col_name} = {bin}"

    if op == '!=':
      assert len(val) == 1
      val = val[0]

      bin = self.predict_bin(val)

      # VERY IMPORTANT: Check that we are alone in the bin.
      alone_in_bin = True
      for key in self.mapping:
        if key != val and self.mapping[key] == bin:
          alone_in_bin = False

      if alone_in_bin:
        return f'{col_name} != {bin}'
      else:
        # Essentially, we cannot skip anything because we might generate false negatives!
        return 'true'
    
    if op == 'in':
      # TODO: Optimize if the bins are consecutive!
      # NOTE: We simply take the unique ones.
      bins = set()
      for v in val:
        # NOTE: This can happen, e.g., 33a.sql: `link in ('sequel', 'follows', 'followed by')`.
        if v in self.mapping:
          bins.add(self.predict_bin(v))
      if bins:
        return f"{col_name} IN ({', '.join(map(str, bins))})"

      # NOTE: Should not be the case. Unless the `IN` predicate is empty.
      assert 0
      return 'true'
    
    if op == 'like':
      assert len(val) == 1
      val = val[0]
      assert val.count('%') == 2
      filtered_pattern = val.replace('%', '')

      bins = set()
      for key in self.mapping:
        # LIKE execution.
        if filtered_pattern in key:
          bins.add(self.predict_bin(key))
      if bins:
        return f"{col_name} IN ({', '.join(map(str, bins))})"
      
      # NOTE: Should not be the case. Unless ...?
      assert 0
      return 'true'
    
    if op == 'ilike':
      assert len(val) == 1
      val = val[0]
      assert val.count('%') == 2
      filtered_pattern = val.replace('%', '')

      bins = set()
      for key in self.mapping:
        # ILIKE execution.
        if filtered_pattern.lower() in key.lower():
          bins.add(self.predict_bin(key))
      if bins:
        return f"{col_name} IN ({', '.join(map(str, bins))})"
      
      # NOTE: Should not be the case. Unless ...?
      assert 0
      return 'true'
 
    assert 0
    return None

  def to_sql(self, col, use_alias=True):
    # print(f'[str_histogram::to_sql] {col}')

    if not use_alias:
      assert col.count('.') == 1 and not col.startswith('.') and not col.endswith('.')
      col = col.split('.')[1]

    # Is it nullable?
    if self.is_nullable:
      assert None in self.mapping
      terms = \
          [f"CASE WHEN {col} IS NULL THEN {self.mapping[None]}"] \
        + [f"WHEN {col} = '{value}' then {bin_index}" for value, bin_index in self.mapping.items()]
    else:
      terms = [("CASE " if not idx else "") + f"WHEN {col} = '{value}' then {bin_index}" for idx, (value, bin_index) in enumerate(self.mapping.items())]  
    return '(\n' + '\n'.join(map(lambda term: f'\t{term}', terms)) +  '\n end)'

def build_adaptive_str_histogram(con, dest_tn, col_info, col_stats, pbw, sample_size=10_000, seed=42):
  pk, fk = col_info['pk'], col_info['fk']
  col_name = col_info['pk-col']
  src_tn = col_info['pk-tn']
  # print(f'[build_adaptive_str_histogram] {src_tn}.{col_name} -> {dest_tn}')

  # Skip if only nulls.
  if col_stats['only-null']:
    return None

  # NOTE: In case the column is nullable, we should still have NULL in our values; we add it artificially.
  if col_stats['is-nullable']:
    if None not in col_stats['values']:
      col_stats['values'].append(None)

  # Set the bin count.
  bin_count = 2**pbw

  # The final mapping.
  mapping = dict()

  # When we can't fit everything into a unique bin.
  # Run the query.
  query = f"""
    select {src_tn}.{col_name} as __val__, count(*) as __count__
    from {dest_tn} TABLESAMPLE reservoir({sample_size} ROWS) REPEATABLE ({seed}), {src_tn}
    where {dest_tn}.{fk} = {src_tn}.{pk}
    group by {src_tn}.{col_name}
    order by count(*) desc;
  """

  query_ret = con.sql(query).df()

  # Get the values.
  # NOTE: We also have to consider NULLs.
  query_val_list = list(map(lambda x: x if pd.notna(x) else None, query_ret['__val__']))
  query_count_list = list(query_ret['__count__'])

  print(list(zip(query_val_list, query_count_list)))

  # Add those that are not present in the sample with frequency 0.
  # TODO: Maybe put 1?
  for k in col_stats['values']:
    if k not in query_val_list:
      query_val_list.append(k)
      query_count_list.append(0)

  # Zip them.
  query_ret = list(zip(query_val_list, query_count_list))

  # NOTE: This also accounts for NULLs!
  distinct_count = col_stats['#distinct']
  if distinct_count <= bin_count:
    # Fit a distinct value to a unique bin.
    bin_count = 2**int(math.ceil(math.log2(distinct_count)))

    # NOTE: We arrange them in the order of the frequency found in the query.
    # This ensures that really occuring values are in the first bins (=> the first bits are occupied) -> less space.

    assert len(col_stats['values']) == len(query_ret)
    bin_index = 0
    for v, _ in query_ret:
      mapping[v] = bin_index
      bin_index += 1

    # And return.
    return {
      'type' : 'lw',
      'mapping' : mapping
    }

  # Build when we don't have enough bins.
  builder = EquiDepthHistogramBuilderWithDP(query_ret, bin_count)
  cost, boundaries = builder.optimized_build()

  print(boundaries)

  ptr = 0
  for (k, v) in query_ret:
    if ptr < len(boundaries) and k == boundaries[ptr]:
      mapping[k] = ptr
      ptr += 1
    else:
      mapping[k] = ptr

  return {
    'type' : 'lw',
    'mapping' : mapping
  }

def build_str_histogram(col_name, col_stats, pbw):
  # print(f'[build_str_histogram] {col_name}')

  # Skip if only nulls.
  if col_stats['only-null']:
    return None
  
  # NOTE: This also accounts for NULLs!
  distinct_count = col_stats['#distinct']

  bin_count = 2**pbw
  if bin_count < distinct_count:
    # We have to restrict the domain a bit.
    bin_width = int(math.ceil(distinct_count / bin_count))
  else:
    # Fit a distinct value to a unique bin.
    bin_count = 2**int(math.ceil(math.log2(distinct_count)))
    bin_width = 1
  
  # NOTE: In case is nullable, we should still have NULL in our values. That's why, we add it artificially.
  if col_stats['is-nullable']:
    if None not in col_stats['values']:
      col_stats['values'].append(None)

  # Create a mapping for each value. This also covers the case of `bin_width = 1`.  
  mapping = dict()
  bin_index = -1
  for index, val in enumerate(col_stats['values']):
    if index % bin_width == 0:
      bin_index += 1
    mapping[val] = bin_index

  return {
    'type' : 'lw',
    'mapping' : mapping
  }