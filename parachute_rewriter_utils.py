import numpy as np

def precompute_stuff(join_preds):
  # Take the distinct alias and map them to distinct indices.
  alias2idx, idx2alias, alias2tn = dict(), dict(), dict()
  for (alias_pair, _) in join_preds:
    # Join predicate: ({'lt': 'link_type', 'ml': 'movie_link'}, 'lt.id = ml.link_type_id')
    assert len(alias_pair) == 2
    for alias in alias_pair.keys():
      # Assign a unique integer.
      if alias not in alias2idx:
        idx = len(alias2idx)
        alias2idx[alias] = idx
        idx2alias[idx] = alias
    
      # Also construct a mapping alias2tn.
      if alias not in alias2tn:
        alias2tn[alias] = alias_pair[alias]
  return alias2idx, idx2alias, alias2tn

def compute_adj_matrix(schema, alias2idx, alias2tn, join_preds):
  def decide_pk_fk_pair(x_alias, y_alias):
    # Take the corresponding table names.
    x_tn, y_tn = alias2tn[x_alias], alias2tn[y_alias]

    # Check if `x` is the FK-side.
    if 'fks' in schema[x_tn]:
      for (_, fk_info) in schema[x_tn]['fks'].items():
        if fk_info['table'] == y_tn:
          return y_alias, x_alias
        
    # Check if `y` is the FK-side.
    if 'fks' in schema[y_tn]:
      for (_, fk_info) in schema[y_tn]['fks'].items():
        if fk_info['table'] == x_tn:
          return x_alias, y_alias

    # FK-FK join.
    return None, None

  # Construct the *directed* adjacency matrix.
  directed_adj = np.zeros(shape=(len(alias2idx), len(alias2idx)))
  for (alias_pair, _) in join_preds:
    l, r = alias_pair.keys()
    l, r = decide_pk_fk_pair(l, r)

    # Skip FK-FK joins.
    if l is None or r is None:
      continue

    # NOTE: We only consider PK-FK / FK-PK joins.
    # NOTE: By construction, `l` is PK and `r` is FK.

    # Convert to int.
    l, r = alias2idx[l], alias2idx[r]

    # PK -> FK.
    directed_adj[l][r] = 1
  return directed_adj

# Cumulative power matrix.
def cum_power(adj, k):
  assert adj.shape[0] == adj.shape[1]
  S = np.zeros(shape=(adj.shape[0], adj.shape[0]))
  A_power = np.eye(adj.shape[0])

  for _ in range(k):
    A_power = A_power @ adj
    S += A_power
  return S

def compute_transitive_adj_matrix(schema, join_preds, transitivity):
  # Precompute.
  alias2idx, idx2alias, alias2tn = precompute_stuff(join_preds)

  # Compute the directed adj. matrix.
  # NOTE: We could create a directed adjacent matrix and then rise to `n - 1`, so that we obtain all possible join paths.
  # TODO: Might also work for semi-joins, e.g., TPC-H.
  A = compute_adj_matrix(schema, alias2idx, alias2tn, join_preds)

  # No transitivity needed?
  if not transitivity:
    return A, alias2idx, idx2alias, alias2tn

  # Compute the transitive adjacency matrix.
  assert A.shape[0] == len(alias2idx)
  return cum_power(A, A.shape[0] - 1), alias2idx, idx2alias, alias2tn
