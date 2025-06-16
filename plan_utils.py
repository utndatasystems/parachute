import numpy as np
import re

def get_pk_fk_matrix(schema):
  n = len(schema)
  adj = np.zeros(shape=(n, n), dtype=bool)

  tn2idx, idx2tn = dict(), dict()
  index = 0
  for tn in schema:
    tn2idx[tn] = index
    idx2tn[index] = tn
    index += 1

  for fk_tn in schema:
    if 'fks' not in schema[fk_tn]:
      continue
    for fk in schema[fk_tn]['fks']:
      pk_tn = schema[fk_tn]['fks'][fk]['table']
      adj[tn2idx[pk_tn]][tn2idx[fk_tn]] = 1
  return adj, tn2idx, idx2tn

def debug_mat(mat, idx2tn, msg):
  print(f'Debug {msg}')
  for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
      if mat[i, j]:
        print(f'{idx2tn[i]} <{msg}> {idx2tn[j]}')

def to_bin(x):
  # print(f'x={x}')
  return ''.join(map(lambda x: str(x), x))
  # return '{0:12b}'.format(x)

def infer_flow_relation(plan, schema):
  # TODO: What about duplicate tables? The alias is not kept.
  # Get the PK->FK-matrix.
  pk_mat, tn2idx, idx2tn = get_pk_fk_matrix(schema)

  # fk_mat = pk_mat.T @ pk_mat

  # debug_mat(pk_mat, idx2tn, 'pk')
  # debug_mat(fk_mat, idx2tn, 'fk')
  
  # Collect information about the base tables.
  plan_info = collect_table_info(plan)

  # for elem in plan_info:
  #   print(f'side-mask: {to_bin(elem["side-mask"])} | {elem["name"]}')

  def is_build(x):
    assert len(x['side-mask'])
    return x['side-mask'][-1] != 0

  def is_probe(x):
    assert len(x['side-mask'])
    return x['side-mask'][-1] == 0

  def get_type_as_str(node):
    if is_build(node):
      return 'build'
    return 'probe'

  def pipeline(x):
    return x['side-mask'][:-1]

  def pipeline_less_than(x, y):
    x_mask = x['side-mask']
    y_mask = y['side-mask']

    # First strip the build/probe-marker.
    x_mask = x_mask[:-1]
    y_mask = y_mask[:-1]

    # Same pipeline => skip, since we only want `<`.
    if x_mask == y_mask:
      return False

    # Then, if we want `x < y`, i.e., `x` is on a pipeline above `y`, we have to ensure that `x` is a prefix of `y`.
    # Of course, if `y` is larger, no way.
    if len(y_mask) < len(x_mask):
      return False
    
    # Otherwise, check for equality.
    for i in range(len(x_mask)):
      if x_mask[i] != y_mask[i]:
        return False
    return True

  # We define `<` on relations as follows:
  # R < S :<=> (pipeline(R) < pipeline(S)) or (pipeline(R) = pipeline(S) and is_probe(R)).
  # NOTE: It's `is_probe(R)` and not `is_probe(S)`! 
  def relation_less_than(R, S):
    return pipeline_less_than(R, S) or (pipeline(R) == pipeline(S) and is_probe(R))

  # Information-flow relation:
  # R ~> S :<=> R > S and R <-> S.
  # R ~>^{n + 1} S :<=> \exists T. R ~>^n T ~> S.
  # R ~>^* S:<=> \exists n. R ~>^n S.
  def information_flow_less_than(R, S):
    # print(f'\n[information_flow_less_than]: {R["name"]} {S["name"]}')

    # Take the indices in the matrix.
    R_idx, S_idx = tn2idx[R['name']], tn2idx[S['name']]

    # NOTE: Since we only do FK-parachutes, checking for `pk_mat[R][S]` suffices to compare to SIP.
    # If we also want to consider _transitive_ parachutes, we should use the transitive PK-matrix as in `compute_transitive_adj_matrix`.
    return relation_less_than(S, R) and pk_mat[R_idx][S_idx]

  relation = []
  for x in plan_info:
    for y in plan_info:
      if x == y:
        continue

      # Check if `x ~> y`.
      check_val = information_flow_less_than(x, y)

      # if check_val:
      #   print(f'@@@ SIP-amenable')

      # TODO: Maybe we later need the aliases.
      relation.append({
        'R' : x['name'],
        'R-type': get_type_as_str(x),
        'R-pipeline': x['side-mask'], 
        'S' : y['name'],
        'S-pipeline': y['side-mask'],
        'S-type': get_type_as_str(y),
        'sip-amenable' : check_val
      })

  return relation

def extract_version(config):
  # Special case for RPT.
  if config == 'rpt':
    return '0.9.2'
  version_match = re.search(r'\bv\d+(?:\.\d+){1,2}\b', config)
  version = version_match.group(0) if version_match else 'v1.2.0'
  assert version.startswith('v')
  return version[1:]

class PlanParser:
  def __init__(self, competitor_type, version):
    self.competitor_type = competitor_type
    self.version = version

  @property
  def fallthrough_operators(self):
    default_ops = {'UNGROUPED_AGGREGATE', 'PROJECTION', 'HASH_GROUP_BY', 'ORDER_BY'}
    rpt_ops = {'CREATE_BF'}

    if self.version == '1.2.0':
      return default_ops if self.competitor_type != 'rpt' else default_ops | rpt_ops

    if self.version == '0.9.2':
      base = default_ops | {'RESULT_COLLECTOR'}
      return base if self.competitor_type != 'rpt' else base | rpt_ops

    raise ValueError(f'Unsupported version: {self.version}')

  @property
  def extra_operators(self):
    if self.version == '1.2.0':
      return [('operator_cardinality', 'exact-card'), ('cumulative_rows_scanned', 'base-size')]
    if self.version == '0.9.2':
      return [('cardinality', 'exact-card')]
    assert 0

  def get_table_name(self, node):
    if self.version == '1.2.0':
      assert 'Table' in node['extra_info']
      return node['extra_info']['Table']
    if self.version == '0.9.2':
      return node['extra_info'].split('\n')[0]
    assert 0

  def get_est_card(self, node):
    if self.version == '1.2.0':
      return int(node['extra_info']['Estimated Cardinality'])
    if self.version == '0.9.2':
      match = re.search(r'EC:\s*(\d+)', node['extra_info'])
      if match:
        return int(match.group(1))
      
      assert node[self.__key__].strip() in ['COLUMN_DATA_SCAN']
      return 0

    assert 0

  def get_join_type(self, node):
    if self.version == '1.2.0':
      return node['extra_info']['Join Type'].lower()
    if self.version == '0.9.2':
      pos = node['extra_info'].find('\n')
      assert pos != -1
      return node['extra_info'][:pos].lower()
    assert 0

  def get_join_conditions(self, node):
    if self.version == '1.2.0':
      return node['extra_info']['Conditions']
    if self.version == '0.9.2':
      return node['extra_info'].split('\n')[1]
    assert 0

  # Add options if we have an analyzed plan.
  def add_options(self, node, info):
    for opt, label in self.extra_operators:
      if opt in node:
        info[label] = int(node[opt])
    return info

  def _impl_(self, node, side_mask, build_rank):
    # print(self.__key__)
    # print(f'[__impl__] {node[self.__key__]} | build_rank={build_rank}')

    # Fall-through operator?
    if node[self.__key__] in self.fallthrough_operators:
      assert len(node['children']) == 1
      return self._impl_(node['children'][0], side_mask.copy(), build_rank)
    
    # Filter.
    if node[self.__key__] == 'FILTER':
      assert len(node['children']) == 1

      # Parse child.
      join_below_child, child_plan = self._impl_(node['children'][0], side_mask.copy(), build_rank)

      return join_below_child, self.add_options(node, {
        'type': 'filter',
        'name': None,
        'side-mask': side_mask,
        'est-card': self.get_est_card(node),
        'children': [child_plan]
      })
    
    # The new operator (for RPT).
    if node[self.__key__] == 'USE_BF':
      assert len(node['children']) == 1

      # Parse child.
      join_below_child, child_plan = self._impl_(node['children'][0], side_mask.copy(), build_rank)

      return join_below_child, self.add_options(node, {
        'type': 'filter',
        'name': 'use-bf',
        'side-mask': side_mask,
        'est-card': None,
        'children': [child_plan]
      })

    # NOTE: Currently, there is a bug in DuckDB, that `SEQ_SCAN` has a trailing space to the right.
    # NOTE: That's why we use `.strip()`!
    if node[self.__key__].strip() in ['SEQ_SCAN', 'COLUMN_DATA_SCAN', 'INDEX_SCAN']:
      tab_name = 'dummy'
      if node[self.__key__].strip() in ['SEQ_SCAN', 'INDEX_SCAN']:
        tab_name = self.get_table_name(node)
      
      # print(f'\n$$$$ TABLE $$$$')
      # print(f'tab_name={tab_name} ===> {to_bin(side_mask)}')

      # Set the node type.
      node_type = 'seq_scan'
      if node[self.__key__].strip() == 'COLUMN_DATA_SCAN':
        node_type = node[self.__key__].strip().lower()

      assert tab_name is not None
      return False, self.add_options(node, {
        'type': node_type,
        'name': tab_name,
        'side-mask': side_mask,
        'est-card': self.get_est_card(node)
      })
    
    if node[self.__key__] == 'HASH_JOIN':
      assert len(node['children']) == 2

      # print(f'\n$$$$ JOIN {node['extra_info']['Conditions']} $$$$')

      # Get the join type.
      join_type = self.get_join_type(node)

      # Make sure there is a weird attribute for this type of joins.
      if join_type in ['mark', 'semi']:
        assert '#' in self.get_join_conditions(node)

      if join_type == 'inner':
        # Build.
        join_below_build, build_plan = self._impl_(
          node['children'][1],
          side_mask.copy() + [build_rank],
          # Reset since we change to a new pipeline (even thought it might be a single table scan).
          1
        )

        # print(f'\n------- AFTER BUILD -------')
        # print(node['extra_info']['Conditions'])
        # print(f'___ child={node['children'][0][__key__]}, build_rank={build_rank}, side_mask={to_bin(side_mask)}')

        # Probe.
        join_below_probe, probe_plan = self._impl_(
          node['children'][0],
          side_mask.copy(),
          build_rank + 1
        )

        # print(f'\t\t>>>>>>>>finds that join_below_prbe={join_below_probe} FOR {node['children'][0]}')

        # Revise probe index if end of the pipeline.
        if not join_below_probe:
          _, probe_plan = self._impl_(
            node['children'][0],
            side_mask.copy() + [0],
            None
          )

        # print(f'@@@@@@ after revision')
      elif join_type in ['mark', 'semi']:
        # Build. This should always be a `COLUMN_DATA_SCAN`.
        assert node['children'][1][self.__key__] == 'COLUMN_DATA_SCAN'

        join_below_build, build_plan = self._impl_(
          node['children'][1],
          side_mask.copy(),
          1
        )

        # Probe. This leads to a table scan (maybe with a filter on top?).
        join_below_probe, probe_plan = self._impl_(
          node['children'][0],
          side_mask.copy(),
          None
        )

        assert (not join_below_build) and (not join_below_probe)
      else:
        assert 0

      # print(f'\n****** BUILDS FOR JOIN: {node['extra_info']['Conditions']} $$$$')


      # Check.      
      assert build_plan is not None, probe_plan is not None
      assert join_below_build is not None, join_below_probe is not None

      # Gather the build- and probe-plans.
      children = [build_plan, probe_plan]

      return (join_type == 'inner') or join_below_build or join_below_probe, self.add_options(node, {
        'type': 'join',
        'join-type': join_type,
        'name': None,
        'side-mask': side_mask,
        'cond': self.get_join_conditions(node),
        'est-card': self.get_est_card(node),
        'children': children
      })

    # When we really find a new operator.
    # print(node)
    assert len(node['children']) == 1
    raise ValueError(f'Unknown operator type: {node[self.__key__]}')

  def parse(self, json_plan):
    # This is the snt
    self.__key__ = None

    # EXPLAIN ANALYZE?
    plan_to_parse = None
    if self.version == '1.2.0':
      if 'latency' in json_plan:
        plan_to_parse = json_plan['children'][0].copy()
        self.__key__ = 'operator_name'
      else:
        # Just EXPLAIN.
        plan_to_parse = json_plan.copy()
        self.__key__ = 'name'
    elif self.version == '0.9.2':
      plan_to_parse = json_plan['children'][0].copy()
      self.__key__ = 'name'
    assert plan_to_parse is not None

    _, parsed_plan = self._impl_(plan_to_parse, [], 1)

    # And return.
    return parsed_plan
  
def get_sides(plan):
  assert plan['type'] == 'join'
  l = plan['children'][0]
  r = plan['children'][1]

  # NOTE: It's the other way around than in Umbra.
  # assert r['est-card'] <= l['est-card']
  return r, l
  # l, r = plan['children']
  # assert 'est-card' in l
  # assert 'est-card' in r
  # return (l, r) if l['est-card'] <= r['est-card'] else (r, l)

# def put_pipeline_indices(parsed_plan):
#   def _impl_(plan, idx=0):
#     if plan['type'] == 'join':
#       plan['pipeline'] = idx
#       build_side, probe_side = get_sides(plan)

#       join_below_build = _impl_(build_side, idx + 1)
#       join_below_probe = _impl_(probe_side, idx)

#       if plan['join-type'] == 'inner':
#         # Revise if on the same pipeline.
#         if not join_below_build:
#           plan['children'][0]['pipeline'] = idx
#         return True
#       elif plan['join-type'] == 'mark':
#         # NOTE: We assume that this comes from a MARK-JOIN for `IN`-clauses.
#         # NOTE: WE don't take its cardinality, since it's a fake join.
#         # NOTE: In the regular case, there should be no join below us.
#         assert not (join_below_build or join_below_probe)
#         return False
#       else:
#         assert 0
#     elif plan['type'] == 'filter':
#       plan['pipeline'] = idx
#       _ = _impl_(plan['children'][0], idx)
#     else:
#       plan['pipeline'] = idx
#       return False
#   _impl_(parse_plan)

def collect_table_info(json_plan):
  def _impl_(plan, collected_info):
    # Table scan.
    if plan['type'] == 'seq_scan':
      collected_info.append(plan)
      return
    
    if plan['type'] == 'column_data_scan':
      return

    if plan['type'] == 'filter':
      _impl_(plan['children'][0], collected_info)
      return

    if plan['type'] == 'join':
      _impl_(plan['children'][0], collected_info)
      _impl_(plan['children'][1], collected_info)
      return

    assert 0
    
  # Parse the plan.
  parser = PlanParser('parachute', '1.2.0')
  parsed_plan = parser.parse(json_plan)

  # And collect.
  collected_info = []
  _impl_(parsed_plan, collected_info)
  return collected_info

# def compute_cout(json_plan):
#   def compute_cout_impl(plan):
#     if plan['type'] == 'join':
#       build_side, probe_side = get_sides(plan)

#       (join_below_build, b_cout) = compute_cout_impl(build_side)
#       (join_below_probe, p_cout) = compute_cout_impl(probe_side)

#       if plan['join-type'] == 'inner':
#         return True, plan['exact-card'] + b_cout + p_cout
#       elif plan['join-type'] in ['mark', 'semi']:
#         # Note: We assume that this comes from a MARK-JOIN for `IN`-clauses.
#         # Note: In DuckDB v0.9.2, this could also be a SEMI-JOIN. But we only make sure that this happens with a COLUMN_DATA_SCAN.
#         # Note: We don't take its cardinality, since it's a fake join.
#         # Note: In the regular case, there should be no join below us.
#         assert not (join_below_build or join_below_probe)
#         return join_below_build or join_below_probe, b_cout + p_cout
#       else:
#         assert 0
#     elif plan['type'] == 'filter':
#       # NOTE: It can by a dynamically-pushed filter. So we *have* to propagate.
#       (join_below_child, child_cout) = compute_cout_impl(plan['children'][0])
#       if not join_below_child:
#         assert child_cout == 0
#         return join_below_child, 0
      
#       return join_below_child, child_cout
#     else:
#       return False, 0

#   parsed_plan = parse_plan(json_plan)

#   ret = compute_cout_impl(parsed_plan)
#   return ret[1]

def compute_made_it(json_plan, competitor_type, config):
  def compute_made_it_impl(plan):
    # Table scan.
    if plan['type'] == 'seq_scan':
      return False, plan['exact-card']
    
    if plan['type'] == 'column_data_scan':
      return False, 0

    if plan['type'] == 'filter':
      assert len(plan['children']) == 1
      join_below_child, table_size = compute_made_it_impl(plan['children'][0])
      if not join_below_child:
        # Return myself, i.e., *this filter's cardinality* (since it's pushed down).
        return join_below_child, plan['exact-card']

      # If there is a join below, we just forward what we found.
      return join_below_child, table_size

    if plan['type'] == 'join':
      # Join.
      build_side, probe_side = get_sides(plan)

      (join_below_left, l) = compute_made_it_impl(build_side)
      (join_below_right, r) = compute_made_it_impl(probe_side)

      # Inner-join?
      if plan['join-type'] == 'inner':
        # Then set the join flag and add.
        return True, l + r
      elif plan['join-type'] in ['mark', 'semi']:
        # Propagate the OR.
        return (join_below_left or join_below_right), max(l, r)
    assert 0

  parser = PlanParser(competitor_type, extract_version(config))
  parsed_plan = parser.parse(json_plan)
  ret = compute_made_it_impl(parsed_plan)
  return ret[1]

def compute_base_size(json_plan, competitor_type, table_sizes, config):
  def compute_base_size_impl(parser, plan):
    # Table scan.
    if plan['type'] == 'seq_scan':
      if parser.version == '1.2.0':
        return False, plan['base-size']
      if parser.version == '0.9.2':
        assert plan['name'] in table_sizes
        return False, table_sizes[plan['name']]
      assert 0
    
    if plan['type'] == 'column_data_scan':
      return False, 0

    if plan['type'] == 'filter':
      assert len(plan['children']) == 1
      # NOTE: I mean, we could also eliminate filters, but duckdb also has the dynamic filters.
      # NOTE: In principle, we could detect them..
      return compute_base_size_impl(parser, plan['children'][0])

    if plan['type'] == 'join':
      # Join.
      build_side, probe_side = get_sides(plan)

      (join_below_left, l) = compute_base_size_impl(parser, build_side)
      (join_below_right, r) = compute_base_size_impl(parser, probe_side)

      # Inner-join?
      if plan['join-type'] == 'inner':
        # Then set the join flag and add.
        return True, l + r
      elif plan['join-type'] in ['mark', 'semi']:
        # Propagate the OR.
        return (join_below_left or join_below_right), max(l, r)

    assert 0

  parser = PlanParser(competitor_type, extract_version(config))
  parsed_plan = parser.parse(json_plan)
  ret = compute_base_size_impl(parser, parsed_plan)
  return ret[1]

# def compute_base_size(json_plan):
#   def compute_base_size_impl(plan):
#     # Table scan.
#     if plan['name'] is not None:
#       # If it's a column scan, the base size is anyway 0 (DuckDB default).
#       return plan['base-size']
  
#     # Join.
#     build_side, probe_side = get_sides(plan)
#     return compute_base_size_impl(build_side) + compute_base_size_impl(probe_side)

#   parsed_plan = parse_plan(json_plan)
#   return compute_base_size_impl(parsed_plan)