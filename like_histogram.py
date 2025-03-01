import re
import math

def compute_bitmask(text: str, mapping: dict) -> int:
  bitmask = 0
  for byte in text.encode('utf-8'):
    bitmask |= 1 << mapping[byte]
  return bitmask

# Create a new function for each mapping
def make_bitmask_function(mapping):#, tn, col):
  return lambda text: compute_bitmask(text, mapping)#:, tn, col)

class LikeHistogramWrapper:
  OPERATORS = sorted(['like', 'ilike', 'not like', 'not ilike', '=', '!=', 'in'], key=len, reverse=True)

  def __init__(self, data, con=None):
    self.con = con
    self.is_nullable = data['is-nullable']
    self.bin_count = data['crutch']['bin-count']
    
    # Transform the dict to `int`-keys.
    self.mapping = { int(k) : v for k, v in data['crutch']['mapping'].items() }

  def split_str_pred(self, pred_col, pred):
    op_pattern = "|".join(map(re.escape, filter(lambda op: op != 'in', self.OPERATORS)))

    # Try with `LIKE` and `=`.
    standard_re_str = rf"{re.escape(pred_col)}\s*({op_pattern})\s*'([^']*)'"
    standard_str_match = re.fullmatch(standard_re_str, pred, re.IGNORECASE)

    print(standard_str_match)

    if standard_str_match:
      op, val = standard_str_match.groups()
      return op.lower(), val

    # Not found? Then try with `IN` (as in `str_histogram`).
    in_re_str = rf"{re.escape(pred_col)}\s*(in)\s*\(\s*'([^']*)'(?:\s*,\s*'([^']*)')*\s*\)?"
    in_match = re.finditer(in_re_str, pred, re.IGNORECASE)
    matches = next(in_match, None)
    assert matches, 'Invalid SQL predicate format.'

    # Get the operator.
    op = matches.group(1)
    assert op.lower() == 'in'

    # Extract values separately.
    values_str = matches.group(0)
    values = re.findall(r"'([^']*)'", values_str)

    # print(f'op={op}, values={values}')

    # And return.
    return op.lower(), values

  def translate(self, col_name, pred, pred_col):
    print(f"[LIKE::translate] {pred} {pred_col}")

    # Check for `IS NULL`. By definition, since '\0' already included, a NULL is represented by the empty bitmask.
    # TODO: Support in ORs!
    if pred.lower() == f'{pred_col} is not null':
      return f'{col_name} <> 0'

    op, val = self.split_str_pred(pred_col, pred)
    assert op in self.OPERATORS, 'Invalid SQL operator.'

    if op == 'like':
      # print(self.mapping)
      # TODO: What if the string itself contains '%', e.g., escaped?
      filtered_text = val.replace('%', '')
      bitmask_pattern = compute_bitmask(filtered_text, self.mapping)

      # If it's already the full bitmask, it doesn't make sense to do the `&`.
      if bitmask_pattern == 2**self.bin_count - 1:
        return f'{col_name} = {bitmask_pattern}'
      
      # Standard case.
      return f'({col_name} & {bitmask_pattern}) = {bitmask_pattern}'

    if op == 'ilike':
      # TODO: What if the string itself contains '%', e.g., escaped?
      filtered_text = val.replace('%', '')
      bitmask_pattern1 = compute_bitmask(filtered_text.lower(), self.mapping)
      bitmask_pattern2 = compute_bitmask(filtered_text.upper(), self.mapping)

      # Best try.
      bitmask_pattern = bitmask_pattern1 | bitmask_pattern2

      # If it's already the full bitmask, it doesn't make sense to do the `&`.
      if bitmask_pattern == 2**self.bin_count - 1:
        return f'{col_name} = {bitmask_pattern}'
      
      # Standard case.
      return f'({col_name} & {bitmask_pattern}) = {bitmask_pattern}'


    if op in ['not like', 'not ilike']:
      # We cannot prune anything!
      return f'true'

    if op == '=':
      bitmask_pattern = compute_bitmask(val, self.mapping)
      
      # NOTE: This works, because it's equality.
      return f'{col_name} = {bitmask_pattern}'
    
    if op == '!=':
      # We cannot prune anything!
      # TODO: Can we actually do sth here? I mean, if `val` is the empty string, maybe that works?
      # TODO: For now, just return true.
      return f'true'
    
    if op == 'in':
      # TODO: Optimize if the bins are consecutive!
      # NOTE: We simply take the unique ones.
      bitmasks = set()
      for v in val:
        bitmask_pattern = compute_bitmask(v, self.mapping)
        bitmasks.add(bitmask_pattern)
      if bitmasks:
        return f"{col_name} IN ({', '.join(map(str, bitmasks))})"
      
      # NOTE: Should not be the case. Unless the `IN` predicate is empty.
      assert 0
      return 'true'

    assert 0
    return None

  def to_sql(self, col, use_alias=True):
    assert self.con is not None
    # print(f'[like_histogram::to_sql] {col}')

    # NOTE: This should before the following split.
    self.fn_name = f'compute_bitmask_{col.split('.')[0]}_{col.split('.')[1]}'

    # Create function.
    self.con.create_function(self.fn_name, make_bitmask_function(self.mapping), return_type="INT32")

    if not use_alias:
      assert col.count('.') == 1 and not col.startswith('.') and not col.endswith('.')
      col = col.split('.')[1]

    # SQL stmt.
    terms = f"CASE WHEN {col} IS NULL THEN 0 ELSE {self.fn_name}({col}) END"
    return terms
  
  def destroy(self):
    assert self.fn_name is not None
    self.con.remove_function(self.fn_name)

def build_like_histogram(col_name, stats, pbw):
  # print(f'[build_like_histogram] {col_name}')

  # Skip if only nulls.
  if stats['only-null']:
    return None

  # TODO: Update for NULLs.
  # TODO: This is NOT 2**pwb, since we have to set many more bits as in the case of numeric columns.
  bin_count = pbw

  # TODO: make instance-optimal.
  mapping = {i: i % bin_count for i in range(256)}

  return {
    'type' : 'like',
    'bin-count' : bin_count,
    'mapping' : mapping
  }