import os
import utils
import plan_utils
import pred_translator
import numpy as np
import parachute_rewriter_utils

def debug_matrix(mat, alias_mapping, msg):
  print(msg)
  print(mat)
  for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
      if mat[i, j]:
        print(f'{alias_mapping[i]} w/ {alias_mapping[j]}')

class ParachuteRewriter:
  def __init__(self, parachute, use_like):
    self.parachute = parachute
    self.schema = self.parachute.schema
    self.use_like = use_like

  def rewrite(self, query_filepath, altitude):
    assert os.path.isfile(query_filepath)

    # Alitude is represented as a bitmask:
    # 01: low-altitude only.
    # 10: high-altitude only.
    # 11: both.
    # low-altitude means: SIP is amenable.
    assert altitude in [1, 2, 3]

    # Read the SQL query.
    sql_query = open(query_filepath, 'r').read()

    # Get the explained plan.
    assert query_filepath.endswith('.sql')
    assert '/sql/' in query_filepath
    print(f'query_filepath={query_filepath}')
    explained_plan = utils.read_json(query_filepath.replace('/sql/', '/plan/').replace('.sql', '.json'))

    # Infer the SIP-relation from the plan.
    sip_relation = plan_utils.infer_flow_relation(explained_plan, self.schema)

    def get_sip_pair(pk_tn, fk_tn):
      # NOTE: There could be multiple. We have to fix this somehow.
      for elem in sip_relation:
        if elem['R'] == pk_tn and elem['S'] == fk_tn:
          return elem

    # print(sip_relation)

    table_preds = utils.extract_table_preds(sql_query)
    join_preds = utils.extract_join_preds(sql_query)

    # print(f'---- table_preds ----')
    # print(table_preds)
    # print('\n\n')
    # print(f'---- join_preds ----')
    # print(join_preds)
    # print(f'\n\n')

    # Compute the transitive adjacent matrix. It's transitive only if specified.
    # NOTE: This is at alias-level.
    power_adj, _, idx2alias, alias2tn = parachute_rewriter_utils.compute_transitive_adj_matrix(
      self.parachute.schema,
      join_preds,
      transitivity=self.parachute.transitivity
    )

    # debug_matrix(power_adj, idx2alias, 'power')

    # print(f'TRANSITIVITY={self.parachute.transitivity}')

    def solve_pair(src_alias, src_tn, dest_alias, dest_tn):
      print(f'[solve_pair] src_alias={src_alias}, dest_alias={dest_alias}')

      # Not in the catalog?
      if dest_tn not in self.parachute.catalog:
        return []
      
      # No parachutes on the destination table?
      if 'parachutes' not in self.parachute.catalog[dest_tn]:
        return []

      # Declare the translator.
      translator = pred_translator.PredTranslator(self)

      # No preds on this table?
      if (src_alias, src_tn) not in table_preds:
        return []

      # Iterate the predicates.
      translations = []
      for pred in table_preds[(src_alias, src_tn)]:
        # The cols that are accessed in this predicate.
        cols = pred['cols']

        # Translate.
        translation = translator.translate(cols, pred['template'], src_tn=src_tn, dest_tn=dest_tn, dest_alias=dest_alias)

        print(f'++++++++ Translation={translation}\n')

        # No translation available? Then skip.
        if translation is None:
          continue

        # Just skip if we have `true`.
        if translation == 'true':
          continue

        # Add the translation.
        translations.append(translation)
      return translations

    parachute_preds = []
    for i in range(power_adj.shape[0]):
      for j in range(power_adj.shape[1]):
        # Skip.
        # NOTE: This is what we can attach with parachute.
        if not power_adj[i][j]:
          continue

        # Take the aliases.
        i_alias, j_alias = idx2alias[i], idx2alias[j]

        i_tn, j_tn = alias2tn[i_alias], alias2tn[j_alias]

        # Check if we should really take it. For this, we check the SIP-relation and the altitude.
        sip_info = get_sip_pair(i_tn, j_tn)
        assert sip_info is not None
       
        # print(f'\n$$$ CHECK  {i_alias} {j_alias} $$$')
        # print(sip_info)

        # SIP-amenable?
        if sip_info['sip-amenable']:
          # We're not allowed to take it (since the low-altitude bit is not set).
          if (altitude & 1) == 0:
            continue
          # NOTE: Apparently, in the current implementation, SIP doesn't do information passing (since DuckDB might already do sth, but apparently it doesn't work).
          # NOTE: Thus, to not exarcebate the benefit of plugging parachute in SIP, we remove them.
          # if i_tn in ['info_type', 'role_type', 'link_type', 'kind_type', 'company_type', 'comp_cast_type']:
          #   continue
        else:
          # Check the high bit.
          if ((altitude >> 1) & 1) == 0:
            continue

        # print(f'i_alias={i_alias}, j_alias={j_alias} ~~~~~~~~~ SURVIVE')

        # Solve the pair.
        translations = solve_pair(i_alias, alias2tn[i_alias], j_alias, alias2tn[j_alias])
        parachute_preds.extend(translations)

    # print(f'Final parachute predicates:')
    # print(parachute_preds)

    def place_parachutes(rewritten_sql_query):
      if rewritten_sql_query.strip().endswith(';'):
        rewritten_sql_query = rewritten_sql_query.strip().strip(';')
      if not rewritten_sql_query.endswith('\n'):
        rewritten_sql_query += '\n'
      rewritten_sql_query += '\tand ' + '\n\tand '.join(parachute_preds) + '\n'
      return rewritten_sql_query

    # Add the parachute preds.
    rewritten_sql_query, used = '', False
    for line in sql_query.split('\n'):
      # In particular, before group-by or order-by (CEB).
      if line.strip().upper().startswith('GROUP BY') or line.strip().upper().startswith('ORDER BY'):
        if not used and parachute_preds:
          rewritten_sql_query = place_parachutes(rewritten_sql_query)
          used = True

      # Add the original line.
      rewritten_sql_query += line + '\n'

    # Corner case, in case there was no `GROUP BY` or `ORDER BY` to insert before.
    if not used and parachute_preds:
      rewritten_sql_query = place_parachutes(rewritten_sql_query)

    # Add `;`.
    if not rewritten_sql_query.strip().endswith(';'):
      rewritten_sql_query = rewritten_sql_query.strip() + ';'
    return rewritten_sql_query