import os
import utils
import parachute
  
def fresh_build(data_dir, transitivity, adaptivity, con=None, pbw=None, support_like=True, workload_summary=None, uniqueness_threshold=None, just_sniff=False):
  # Some checks.
  if uniqueness_threshold is not None:
    assert workload_summary is not None

  # Read the schema.
  schema = utils.read_json(os.path.join(data_dir, 'schema.json'))

  parachute_instance = parachute.Parachute(
    data_dir,
    pbw=pbw,
    con=con,
    support_like=support_like,
    transitivity=transitivity,
    adaptivity=adaptivity,
    new_catalog=True
  )

  for tn in schema:
    # if tn != 'movie_info_idx':
    #   continue
    print(f'[{tn}] ***** START *****')
    print(f'[{tn}] Sniff..')
    parachute_instance.sniff_parachute_cols(tn, workload_summary, uniqueness_threshold=uniqueness_threshold)

  if just_sniff:
    import sys
    sys.exit(0)

  # It's pretty important to have this before declaring due to two reasons:
  # (a) We want, e.g., to build `title` before `cast_info`, since `cast_info` requires `title` to already have the parachute on `kind_type`.
  ordered_tns = utils.order_tables(schema, utils.read_json(parachute_instance.get_catalog_path()))

  print(ordered_tns)

  # debug_tns = ['cast_info', 'title', 'kind_type']

  for tn in ordered_tns:
    # if tn not in debug_tns:
    #   continue

    print(f"[{tn}] Declare..")
    parachute_instance.declare_parachute_cols(tn)

    print(f"[{tn}] Compute..")
    parachute_instance.compute_parachute_cols(tn)

    if con is not None:
      print(f"Schema after processing {tn}:")
      print(con.sql(f'SHOW {tn};'))
  
  return parachute_instance

def reuse(con, data_dir, transitivity, adaptivity, catalog_path):
  assert catalog_path is not None
  parachute_instance = parachute.Parachute(
    data_dir,
    transitivity=transitivity,
    adaptivity=adaptivity,
    catalog_path=catalog_path,
    con=con
  )

  return parachute_instance