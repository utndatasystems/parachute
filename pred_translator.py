import num_histogram
import str_histogram
import like_histogram
import utils
import re

class PredTranslator:
  def __init__(self, rewriter):
    self.rewriter = rewriter

  def get_histogram(self, col_key, src_tn, dest_tn):
    assert col_key.startswith(src_tn)

    if not col_key in self.rewriter.parachute.catalog[dest_tn]['parachutes']:
      # TODO: Maybe we could return `true` here?
      # TODO: Not quite, since we might get an OR above us!
      print(f'-> Not in the catalog!')
      return None
    
    data_type = self.rewriter.parachute.catalog[dest_tn]['parachutes'][col_key]['type']
    col_info = self.rewriter.parachute.catalog[dest_tn]['parachutes'][col_key]

    if data_type == 'integer':
      return num_histogram.NumHistogramWrapper(col_info)
    elif data_type == 'char':
      assert col_info['crutch']['type'] == 'lw'
      return str_histogram.StrHistogramWrapper(col_info)
    elif data_type == 'varchar':
      if col_info['crutch']['type'] == 'lw':
        return str_histogram.StrHistogramWrapper(col_info)
      elif col_info['crutch']['type'] == 'like':
        if self.rewriter.use_like:
          return like_histogram.LikeHistogramWrapper(col_info)
  
    # Not supported.
    assert 0
    return None
  
  def translate(self, cols, pred, src_tn, dest_tn, dest_alias, tab=0):
    # print(f'[translate] pred={pred}')

    tab_str = '\t' * tab

    # TODO: This is not entirely correct! We might have to fix this for TPC-H.
    def solve_sql_token(sql_token):
      assert sql_token in ['or', 'and']
      
      # Ensure spaces around sql_token for correct splitting.
      # token_regex = rf'\s+{sql_token}\s+'
      
      # Inside?
      if utils.check_token_in_pred(sql_token, pred):
      # if re.search(token_regex, pred, re.IGNORECASE):
        # We only want a pure conjunction, thus we avoid `BETWEEN`.
        if sql_token == 'and' and re.search(r'\s+between\s+', pred, re.IGNORECASE):
          return False, None

        # print(f'{tab_str} sql_token={sql_token} inside????')
        assert pred.strip().startswith('(') and pred.strip().endswith(')')

        # Strip the outer parentheses carefully.
        cleaned_pred = pred.strip()
        cleaned_pred = cleaned_pred[1 : -1].strip()

        # print(f'{tab_str} cleaned_pred={cleaned_pred}')

        # Split while preserving expressions inside parentheses (e.g., `LIKE` cases).
        # pred_parts = re.split(token_regex, cleaned_pred, flags=re.IGNORECASE)

        pred_parts = utils.split_pred_by_token(sql_token, cleaned_pred)

        # And translate.
        # TODO: Optimize this for the case where the bins are the same.
        # TODO: It should still be generic enough to account for LIKEs!

        # Example 1: (ct.kind ='production companies' OR ct.kind = 'distributors')
        # If they fall into the same bin, optimize this!
        # Maybe even for workload-aware this is interesting to optimze the bins like for LIKEs!
        #
        # Example 2: (t.title LIKE 'Birdemic%' OR t.title LIKE '%Movie%')

        # TODO: Maybe optimize for the margins, like >= bin.
        translated_pred_parts = [self.translate(cols, p.strip(), src_tn=src_tn, dest_tn=dest_tn, dest_alias=dest_alias, tab=tab+1) for p in pred_parts]

        # Do we have only NULLs? 
        if len(translated_pred_parts) == translated_pred_parts.count(None):
          # Then we can't translate it.
          return True, None
        elif translated_pred_parts.count(None):
          # NOTE: This could happen, if we have a parachute on one of `cols`, but not on all.
          # NOTE: Maybe we could just put `true` in the local translation?
          assert 0
        
        # Recompose.
        return True, '(' + f' {sql_token.upper()} '.join(translated_pred_parts) + ')'
      return False, None

    or_solver_flag, or_solver_ret = solve_sql_token('or')
    if or_solver_flag:
      return or_solver_ret
    and_solver_flag, and_solver_ret = solve_sql_token('and')
    if and_solver_flag:
      return and_solver_ret
    
    # Base case.
    # Strip the predicate.
    # print(f'pred={pred}')
    column_matches = re.findall(r"@\.(\w+)", pred)

    # print(f'{tab_str} {column_matches}')
    # print(f'{tab_str} src_tn={src_tn}, dest_tn={dest_tn}')

    # Moreover, the column should be on the a single column.
    # NOTE: This also enforces that there is only one column!
    assert len(column_matches) == 1

    # The column found should be in the pre-defined ones, i.e., those in the original predicate.
    curr_col = column_matches[0]
    assert curr_col in cols

    # print(f'{tab_str} curr_col={curr_col}')

    # Take the histogram.
    curr_col_key = f'{src_tn}.{curr_col}'
    histogram = self.get_histogram(curr_col_key, src_tn, dest_tn)

    # No histogram? Then skip.
    # NOTE: This happens in case we disabled an option from above (??).
    if histogram is None:
      return None
      
    assert dest_tn in self.rewriter.parachute.catalog
    other_parachute_tag = self.rewriter.parachute.catalog[dest_tn]['parachutes'][curr_col_key]['tag']
    other_parachute_col_name = f'{dest_alias}.parachute_{other_parachute_tag}'

    # Remove the alias placeholders.
    pred = pred.replace('@.', '')

    # print(f'{tab_str} Translate: {other_parachute_col_name} in {pred}')
    
    # Strip brackets.
    if pred.startswith('(') and pred.strip().endswith(')'):
      pred = pred.strip()[1:-1].strip()

    # And return the translation.
    print(f'other_parachute_col_name={other_parachute_col_name}, pred={pred}, curr_col={curr_col}')
    return histogram.translate(other_parachute_col_name, pred, curr_col)