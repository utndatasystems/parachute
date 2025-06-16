import re
import math
import bisect
import collections
import pandas as pd
from histogram_builder.equi_depth_builder import EquiDepthHistogramBuilderWithDP

PARACHUTE_NULL_BIN_IDX = 0
NULL_REPRESENTATION = -math.inf

def get_real_bin_count(pbw):
  # assert 'is-nullable' in col_stats
  # if col_stats['is-nullable']:
  #   return 2**pbw - 1, True
  return 2**pbw

class NumHistogramWrapper:
  OPERATORS = sorted(['=', '!=', '>=', '>', '<', '<='], key=len, reverse=True)
  
  def __init__(self, data):
    self.is_nullable = data['is-nullable']
    self.boundaries = data['crutch']

  @staticmethod
  def get_reverse_op(op):
    if op == '>=':
      return '<='
    if op == '>':
      return '<'
    if op == '<':
      return '>'
    if op == '<=':
      return '>='
    return op

  def split_int_pred(self, pred_col, pred):
    op_pattern = '|'.join(map(re.escape, self.OPERATORS))

    # column op constant.
    int_match1 = re.fullmatch(rf"{re.escape(pred_col)}\s*({op_pattern})\s*(\d+)", pred)
    if int_match1:
      return False, int_match1.groups()

    # constant op column.
    int_match2 = re.fullmatch(rf"(\d+)\s*({op_pattern})\s*{re.escape(pred_col)}", pred)
    if int_match2:
      return True, int_match2.groups()[::-1]

    between_match = re.fullmatch(rf"{re.escape(pred_col)}\s+BETWEEN\s+(\d+)\s+AND\s+(\d+)", pred, re.IGNORECASE)
    if between_match:
      return False, ('BETWEEN', between_match.groups())

    assert False, 'Invalid SQL predicate format.'

  def predict_bin(self, x):
    # Corner case.
    if x > self.boundaries[-1]:
      return len(self.boundaries)

    # Corner case for `None`.
    if self.boundaries[0] is None:
      return 1 + bisect.bisect_left(self.boundaries[1:], x)

    # Return index.
    return bisect.bisect_left(self.boundaries, x)

  def translate(self, col_name, pred, pred_col):
    print(f'[Int::translate] {pred}')

    # Check for `IS NULL`.
    # TODO: Maybe the column is actuall never null?
    if pred.lower() == f'{pred_col} is not null':
      if self.is_nullable:
        # NOTE: This is an over-approximation.
        return f"{col_name} != {PARACHUTE_NULL_BIN_IDX}"
      else:
        # Since it can't be NULL!
        return 'true'

    # TODO: Compile.
    is_reversed, match = self.split_int_pred(pred_col, pred)

    print(f'is_reversed={is_reversed}, match={match}')

    # Get the op and the constant.
    op, val = match

    # If reversed, get the reverse operator.
    if is_reversed:
      op = NumHistogramWrapper.get_reverse_op(op)

    # Check.
    assert op in self.OPERATORS + ['BETWEEN'], 'Invalid SQL operator'

    print(f'op={op}, val={val}')

    if op == '>':
      bin = self.predict_bin(int(val))
      # NOTE: This is NOT a typo! In the same bin there could be also larger values!
      return f'{col_name} >= {bin}'
    if op == '>=':
      bin = self.predict_bin(int(val))
      return f'{col_name} >= {bin}'
    if op == '<':
      bin = self.predict_bin(int(val))
      # NOTE: This is NOT a typo! In the same bin there could be also smaller values!
      return f'{col_name} <= {bin}'
    if op == '<=':
      bin = self.predict_bin(int(val))
      return f'{col_name} <= {bin}'
    if op == '=':
      bin = self.predict_bin(int(val))
      return f"{col_name} = {bin}"
    if op == '!=':
      # TODO: This is not yet optimal!
      # We cannot skip anything for now. Unless distinct values in different bins?
      return 'true'
    if op == 'BETWEEN':
      assert len(val) == 2
      l, r = int(val[0]), int(val[1])
      assert l <= r
      left_bin = self.predict_bin(l)
      right_bin = self.predict_bin(r)
      return f'{col_name} BETWEEN {left_bin} AND {right_bin}'
    assert 0
    return None

  def get_ranges(self):
    ranges = [self.min]
    for i in range(1, self.bin_count):
      ranges.append(ranges[-1] + self.bin_width)
    return ranges

  def to_sql(self, col, use_alias=True):
    print(f'[num_histogram::to_sql] {col}')
    # print(self.boundaries)
    if not use_alias:
      assert col.count('.') == 1 and not col.startswith('.') and not col.endswith('.')
      col = col.split('.')[1]
      
    # Is the first bin full of NULLs?
    # NOTE: We consider inclusive ranges.
    assert len(self.boundaries) > 1
    if self.boundaries[0] == None:
      terms = \
        [f'case when {col} is null then {PARACHUTE_NULL_BIN_IDX}'] \
      + [f'when {col} <= {boundary} then {pos}' for pos, boundary in enumerate(self.boundaries[1:], start=1)] \
      + [f'else {len(self.boundaries)}']
    elif self.is_nullable:
      # In this case, the NULL might still be in the first bin. Yet, it's at least not declared as a boundary!      
      terms = \
        [f'case when {col} is null then {PARACHUTE_NULL_BIN_IDX}'] \
      + [f'when {col} <= {boundary} then {pos}' for pos, boundary in enumerate(self.boundaries[0:], start=0)] \
      + [f'else {len(self.boundaries)}']
    else:
      # Just skip the NULL case.
      terms = \
        [f"case when {col} <= {self.boundaries[0]} then 0"] \
      + [f"when {col} <= {boundary} then {pos}" for pos, boundary in enumerate(self.boundaries[1:], start=1)] \
      + [f"else {len(self.boundaries)}"]

    # Create the case-stmt.
    return '(\n' + '\n'.join(map(lambda term: f'\t{term}', terms)) + '\n end)'

def build_adaptive_histogram(con, table, col_name, col_stats, pbw, catalog, sample_size=2**10):
  # Skip if only nulls.
  if col_stats['only-null']:
    return None
 
  # In case there are really many distinct values that we cannot *actually* cover!
  if col_stats['#distinct'] > sample_size:
    # TODO: Re-enable.
    return build_equi_width_histogram(col_name, col_stats, pbw)

  # We have enough bins to tackle this.
  if get_real_bin_count(pbw) > sample_size:
    return build_equi_width_histogram(col_name, col_stats, pbw)

  # Otherwis, an equi-depth histogram.
  return build_equi_depth_histogram(con, table, col_name, col_stats, pbw, catalog, sample_size=sample_size)

def build_equi_width_histogram(col_name, col_stats, pbw):
  print(f'[#####] [build equi-width histogram]')
  print(col_name, col_stats, pbw)

  # Skip if only nulls.
  assert not col_stats['only-null']

  # TODO: Maybe take into account the number of distinct values?

  # TODO: We should have in the future `2**pbw` - 1 to account for NULLs, since -1 is to expensive to compress.
  bin_count = get_real_bin_count(pbw)

  # TODO: Check this once again.
  # TODO: I mean, if there is only one distinct value, what should we do? Maybe there is also a NULL there.
  assert col_stats['max'] != col_stats['min']
  bin_width = int(math.ceil((col_stats['max'] - col_stats['min']) / bin_count))

  print(f'bin_width={bin_width}')

  last = col_stats['min']
  boundaries = []
  for _ in range(1, bin_count):
    last += bin_width

    # Did we already exceed the max-value? Then just stop.
    # NOTE: This happens for `production_year` with a large number of bins.
    if last >= col_stats['max']:
      break

    # Otherwise, put it to the boundary.
    boundaries.append(last)
  assert len(boundaries) <= bin_count - 1
  return boundaries

def build_equi_depth_histogram(con, table, col_name, col_stats, pbw, catalog, sample_size=10_000):
  print(f'[#####] [build equi-depth histogram]')
  print(col_name, col_stats, pbw)

  # Skip if only nulls.
  assert not col_stats['only-null']

  # Check the catalog for precomputed boundaries. This saves us some time for the expensive DP.
  tag = f'{col_name}_{pbw}'
  if '__pre__' not in catalog:
    catalog['__pre__'] = dict()
  if table not in catalog['__pre__']:
    catalog['__pre__'][table] = dict()
  if tag in catalog['__pre__'][table]:
    return catalog['__pre__'][table][tag]

  # Sample data from the table
  # TODO: Do a group-by on the sample.
  sample = con.sql(f"""
    SELECT {col_name} as val
    FROM {table}
    USING SAMPLE reservoir({sample_size} ROWS)
    REPEATABLE (42);
  """).df()['val'].values.tolist()

  # Consider NULLs as values per se.
  sample = list(map(lambda x: x if pd.notna(x) else NULL_REPRESENTATION, sample))

  # print(sample)

  # Determine the bin count.
  bin_count = get_real_bin_count(pbw)

  # Determine the boundaries for each bin (equi-depth).
  freqs = collections.Counter(sample)

  # Really important that the keys are sorted (since we're dealing with numeric data).
  freqs = sorted(freqs.items())

  # Build the histogram with DP.
  builder = EquiDepthHistogramBuilderWithDP(freqs, bin_count)
  cost, boundaries = builder.optimized_build()

  print(boundaries)

  assert len(boundaries) <= bin_count - 1

  # Save into the catalog.
  catalog['__pre__'][table][col_name] = boundaries

  return boundaries