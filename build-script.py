import os
import sys
import argparse
import utils
import parachute_wrapper

def main():
  num_threads_available = os.cpu_count()
  print(f'num_threads_available={num_threads_available}')

  parser = argparse.ArgumentParser(description='Run Parachute with given parameters.')
  parser.add_argument('--pbw', type=int, required=True, help='Parachute bit-width.')
  parser.add_argument('--data-dir', type=str, required=True, help='Path to the data directory.')
  parser.add_argument('--workload-dir', type=str, required=True, help='Path to the workload directory.')
  parser.add_argument('--transitivity', type=int, required=True, help='Whether we should use transitivity or not.')
  parser.add_argument('--adaptivity', type=int, required=True, help='Whether we should use adaptivity or not.')
  parser.add_argument('--num-threads', type=int, default=num_threads_available, help=f'Number of threads (default: {num_threads_available}).')
  parser.add_argument('--do-not-drop-helpers', action='store_true', help='Don\'t drop helper columns.')
  parser.add_argument('--support-like', action='store_false', help='Disable support for LIKE predicates.')
  parser.add_argument('--show', action='store_true', help='Compute the parachute DB stats if set.')

  args = parser.parse_args()

  DATA_DIR = args.data_dir
  WORKLOAD_DIR = args.workload_dir
  PARACHUTE_BITWIDTH = args.pbw
  NUM_THREADS = args.num_threads
  SUPPORT_LIKE = args.support_like
  DROP_HELPERS = not args.do_not_drop_helpers
  TRANSITIVITY = args.transitivity
  ADAPTIVITY = args.adaptivity
  SHOW = args.show
  UNIQUENESS_THRESHOLD = 1

  print(f'DATA_DIR={DATA_DIR}')
  print(f'SUPPORT_LIKE={SUPPORT_LIKE}')
  assert SUPPORT_LIKE
  print(f'TRANSITIVITY={TRANSITIVITY}')
  print(f'ADAPTIVITY={ADAPTIVITY}')
  print(f'DROP_HELPERS={DROP_HELPERS}')

  print(f'SHOW={SHOW}')

  # Take the workload name.
  workload_name = os.path.basename(os.path.normpath(WORKLOAD_DIR))
  assert workload_name

  # Make sure we have a template database.
  data_name = os.path.basename(os.path.normpath(DATA_DIR))
  assert data_name

  default_db_file = os.path.join('dbs', f'{data_name}.duckdb')
  if not os.path.isfile(default_db_file):
    print(f'You might need to run `data-loader.ipynb` first.')
    sys.exit(-1)
  
  # Set the initial database file.
  init_db_file_size = os.path.getsize(default_db_file)

  # Create a custom db file.
  DB_FILE = os.path.join('dbs', f'{workload_name}_{data_name}-parachute-{PARACHUTE_BITWIDTH}-{TRANSITIVITY}-{ADAPTIVITY}.duckdb')

  # Remove the existing database file if it exists (just to be sure we don't use old parachutes).
  # NOTE: We only do this if we don't have to show. Otherwise, we _have_ to use the old database.
  if not SHOW:
    if os.path.isfile(DB_FILE):
      os.remove(DB_FILE)

    import subprocess
    subprocess.call(['cp', default_db_file, DB_FILE])
    assert os.path.isfile(DB_FILE)

  # Read schema and workload.
  print(f'Analyzing the workload..')

  # Already available?
  workload_summary_path = os.path.join(WORKLOAD_DIR, 'workload-summary.json')
  if os.path.isfile(workload_summary_path):
    # Read it.
    workload_summary = utils.read_json(workload_summary_path)
  else:
    # Read the schema, since we need it.
    schema = utils.read_json(os.path.join(DATA_DIR, 'schema.json'))

    # Collect the workload.
    all_preds = utils.parse_workload(schema, WORKLOAD_DIR)
    workload_summary = utils.cluster_preds(all_preds)

    # Set the workload name.
    workload_summary['__init__'] = {
      'name' : workload_name
    }

    # And write it.
    utils.write_json(workload_summary_path, workload_summary)

  print(f'Finished analyzing the workload.')
  # utils.print_dict(workload_summary)

  # Use a fake parachute stats file to mean that we're allowed to use the default DuckDB optimizer.
  # This can help when DuckDB does the joins during UPDATEs.
  con = utils.open_duckdb(DB_FILE, read_only=False, threads=NUM_THREADS)#, parachute_stats_file='fake')

  import time
  start_time = time.time_ns()
  if not SHOW:
    # Creates a new parachute object => new catalog.
    parachute_obj = parachute_wrapper.fresh_build(
      data_dir=DATA_DIR,
      pbw=PARACHUTE_BITWIDTH,
      con=con,
      support_like=SUPPORT_LIKE,
      transitivity=TRANSITIVITY,
      adaptivity=ADAPTIVITY,
      workload_summary=workload_summary,
      uniqueness_threshold=UNIQUENESS_THRESHOLD
    )
  else:
    # Reuse the old database file => use old catalog.
    catalog_path = os.path.join(DATA_DIR, f'{workload_name}_data-catalog-{PARACHUTE_BITWIDTH}-{TRANSITIVITY}-{ADAPTIVITY}.json')

    # And instantiate.
    parachute_obj = parachute_wrapper.reuse(
      data_dir=DATA_DIR,
      transitivity=TRANSITIVITY,
      adaptivity=ADAPTIVITY,
      catalog_path=catalog_path,
      con=con
    )
  end_time = time.time_ns()

  # Drop the helpers since they're not used during query execution.
  if not SHOW:
    if DROP_HELPERS:
      parachute_obj.drop_db_helper_columns()

  # Compute the stats.
  # NOTE: This is _always_ done.
  parachute_obj.flush_db_parachute_stats()

  # Close the connection.
  con.close()

  # Only save the time if we don't show.
  if not SHOW:
    import socket
    hostname = socket.gethostname()

    final_db_file_size = os.path.getsize(DB_FILE)
    utils.write_json(os.path.join(DATA_DIR, f'{workload_name}_parachute-size-{hostname}-{PARACHUTE_BITWIDTH}-{TRANSITIVITY}-{ADAPTIVITY}.json'), {
      'build_time' : end_time - start_time,
      'init_db_file_size' : init_db_file_size,
      'final_db_file_size' : final_db_file_size
    })

if __name__ == '__main__':
  main()
