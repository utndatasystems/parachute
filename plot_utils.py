import os
import re
import json
import utils
import pandas as pd
import plan_utils

def search_dir_by_token(base_path, token):
  # print(f'token={token}')
  experiment_dirs = [d for d in os.listdir(base_path) if d == token]
  if not experiment_dirs:
    return None
  return experiment_dirs[0]

def config_to_str(competitor_type, config):
  if competitor_type == 'duckdb':
    # print(f'config={config}')
    assert len(config) == 1
    return f'{competitor_type}-{config[0]}'
  if competitor_type in ['sip', 'rpt']:
    return f'{competitor_type}'
  if competitor_type in ['parachute', 'sip_parachute']:
    assert len(config) == 5
    # {}-{pbw}-{transitivity}-{adaptivity}-{altitude}-{opt}
    return f'{competitor_type}-{config[0]}-{config[1]}-{config[2]}-{config[3]}-{config[4]}'
  assert 0

import os
import re
from datetime import datetime

def extract_timestamp_from_filename(filename):
  timestamp_str = filename.split('-')[-4:]
  timestamp = ''.join(timestamp_str)
  return datetime.strptime(timestamp, '%Y%m%d%H%M%S')

def get_latest_experiments_of_competitor(competitor_type, base_path):
  if not os.path.isdir(base_path):
    return None

  subfolders = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))]

  # TODO: Was this wrong?
  # subfolders = [f for f in subfolders if f.startswith(f'{competitor_type}-')]
  if not subfolders:
    return None

  if competitor_type == 'duckdb':
    # Match `duckdb` with its version.
    pattern = re.compile(r'^duckdb_([^-\s]+)-.*$')

    # Match both duckdb and duckdb_<version> prefixes
    # pattern = re.compile(r'^duckdb(?:_[^-\s]+)?-.*$')
  elif competitor_type in ['sip', 'rpt']:
    pattern = re.compile(rf'^{re.escape(competitor_type)}-.*$')
  elif competitor_type in ['parachute', 'sip_parachute']:
    pattern = re.compile(rf'^{competitor_type}-([^-\s]+)-([^-\s]+)-([^-\s]+)-([^-\s]+)-([^-\s]+).*$')
  else:
    assert 0

  latest_experiments = {}

  for folder in subfolders:
    match = pattern.match(folder)
    if not match:
      continue
    
    key = match.groups()  # (pbw, transitivity, adaptivity, altitude, opt)

    # print(f'key={key}')
    if competitor_type in ['parachute', 'sip_parachute']:
      if len(key) != 5:
        continue
      # pbw = <0>, transitivity = <1>, adaptivity = <2>, altitude = <3>, opt = <4>.
      if not (int(key[1]) in [0, 1] and int(key[2]) in [0, 1] and int(key[3]) in [1, 2, 3] and int(key[4]) in [0, 1, 2]):
        continue

      # # Skip OPT.
      # if int(key[3]) == 1:
      #   continue

    folder_timestamp = extract_timestamp_from_filename(folder)

    if key not in latest_experiments or folder_timestamp > extract_timestamp_from_filename(latest_experiments[key]):
      latest_experiments[key] = folder

  print(f'competitor_type={competitor_type}')
  return latest_experiments

def extract_data_from_experiment(experiment_path, data_name, competitor_type, num_threads, folder, config):
  results = []

  # Transform the config.
  config = config_to_str(competitor_type, config)

  print(f'config={config}')

  # Read the table sizes.
  table_sizes = utils.read_json(os.path.join('metadata', data_name, 'table-sizes.json'))

  acc_filepath = os.path.join(experiment_path, 'acc.csv')
  if os.path.isfile(acc_filepath):
    return pd.read_csv(acc_filepath)

  for mode in ['cold', 'hot']:
    mode_path = os.path.join(experiment_path, mode)
    assert os.path.exists(mode_path)

    for file in os.listdir(mode_path):
      if file.endswith('.json'):
        txt_file = file.replace('.json', '-optimization-time.txt')
        txt_path = os.path.join(mode_path, txt_file)
        
        if competitor_type in ['parachute', 'sip_parachute']:
          assert os.path.exists(txt_path)
        
        json_path = os.path.join(mode_path, file)

        # Check if the file actually exists.
        if not os.path.isfile(json_path):
          return None        

        with open(json_path, 'r') as f:
          json_data = json.load(f)

        if 'result' in json_data and json_data['result'] == 'error':
          return None

        extra_optimization_time = None
        if competitor_type in ['parachute', 'sip_parachute']:
          # Extract the only number in the file.
          with open(txt_path, 'r') as f:
            tmp = f.read().strip().split(' ')
            assert tmp[1] == 'ns'
            extra_optimization_time = int(tmp[0])

        query_id = file.replace('.json', '')
        # print(query_id)
        results.append({
          'competitor-type': competitor_type,
          'db-file' : folder,
          'config': config,
          'mode': mode,
          'num-threads': num_threads,
          'query': query_id,
          'latency (s)': json_data.get('latency', json_data.get('timing', None)),
          # 'cout' : plan_utils.compute_cout(json_data),
          '#made-it': plan_utils.compute_made_it(json_data, competitor_type, config),
          'base-size': plan_utils.compute_base_size(json_data, competitor_type, table_sizes, config),
          'extra-optimization-time (ns)': extra_optimization_time
        })

        assert results[-1]['latency (s)'] is not None

  # Convert to df.
  ret_df = pd.DataFrame(results)

  # Flush.
  ret_df.to_csv(acc_filepath, index=False)

  return ret_df

def collect_data(root_path, data_name, workload_name, machines, list_num_threads, competitor_types):
  # Empty df.
  all_data = pd.DataFrame()
  
  for competitor_type in competitor_types:
    # Note: This only takes the folder in which the experiments are.
    pattern = None
    if competitor_type in ['parachute', 'sip_parachute']:
      tag = f'{workload_name}_{data_name}-parachute'
      pattern = re.compile(f'^{tag}')
    elif competitor_type in ['duckdb', 'sip', 'rpt']:
      tag = f'{data_name}'
      pattern = re.compile(f'^{re.escape(tag)}$')
    else:
      assert 0
    assert pattern is not None

    for folder in os.listdir(root_path):
      # Match?
      if not pattern.match(folder):
        continue

      # Find the workload directory.
      variant_path = os.path.join(root_path, folder)
      workload_dir = search_dir_by_token(variant_path, token=workload_name)
      if workload_dir is None:
        continue

      for machine in machines:
        # print(f'>>>>> MACHINE={machine}')    
        for num_threads in list_num_threads:
          # print(f'num_threads={num_threads}')

          # Hack.
          fake_num_threads = num_threads
          # if competitor_type == 'sip':
            # fake_num_threads = 1

          workload_threads_dir = search_dir_by_token(os.path.join(variant_path, workload_dir), token=f'{machine}-{fake_num_threads}-threads')
          if workload_threads_dir is None:
            continue

          # print(f'#### workload_threads_dir={workload_threads_dir}')
          exp_dirs = get_latest_experiments_of_competitor(competitor_type, os.path.join(variant_path, workload_dir, workload_threads_dir))

          print(exp_dirs)

          # No exps?
          if not exp_dirs or exp_dirs is None:
            continue

          # print(f'exp_dirs={exp_dirs}')

          for config, exp_dir in exp_dirs.items():
            # print(f'config={config}, exp_dir={exp_dir}')
            
            curr_data = extract_data_from_experiment(os.path.join(
              variant_path,
              workload_dir,
              workload_threads_dir,
              exp_dir
            ), data_name, competitor_type, num_threads, folder, config)
            if curr_data is None:
              continue
            all_data = pd.concat([all_data, curr_data])
  
  return all_data

def load_space_consumption(metadata_folder, data_name, workload_name):
# Load space consumption from the corresponding JSON file.
  space_data = {}

  for file in os.listdir(os.path.join(metadata_folder, data_name)):
    if file.startswith(f'{workload_name}_parachute-size-'):
      parts = file.replace('.json', '').split('-')
      db_file = f'{workload_name}_{data_name}-parachute-{parts[3]}-{parts[4]}-{parts[5]}'

      with open(os.path.join(metadata_folder, data_name, file), 'r') as f:
        stats = json.load(f)
        space_consumption = ((stats['final_db_file_size'] - stats['init_db_file_size']) / stats['init_db_file_size']) * 100
        space_data[db_file] = space_consumption
  return space_data

def deduplicate_legend(handles, labels):
# Deduplicate the legend.
  from collections import OrderedDict
  unique = OrderedDict()
  for h, l in zip(handles, labels):
      if l not in unique:
          unique[l] = h

  return list(unique.values()), list(unique.keys())

def filter_legend(obj, filter_expr, handles=None, labels=None):
# Filter legend handles to only include parachute[duckdb] and parachute[duckdb+psf].
  if handles is None and labels is None:
    handles, labels = obj.get_legend_handles_labels()

  # Deduplicate the legend.
  handles, labels = deduplicate_legend(handles, labels)

  # And filter it.
  return zip(*filter(lambda pair: filter_expr(pair[1]), zip(handles, labels)))

def add_space_agnostic_competitors(axs, workload_name, agg_df, y_metric, baselines, legend_fontsize, plot_hacks, strip_version=False):
# Add the space-agnostic competitors.
  def add_competitor(info, y_value, idx):
    axs.axhline(y=y_value, color=info['color'], linestyle=info['linestyle'], label=info['label'], lw=3)

    # Determine horizontal alignment and x-position shift
    ha = plot_hacks['ha'][y_metric]

    assert workload_name in plot_hacks[ha]
    if y_metric == '#made-it':
      x_pos = axs.get_xlim()[0] + plot_hacks[ha][workload_name] * (axs.get_xlim()[1] - axs.get_xlim()[0])
    else:
      x_pos = axs.get_xlim()[1] + plot_hacks[ha][workload_name] * (axs.get_xlim()[1] - axs.get_xlim()[0])  # Slightly inside right edge

    # Set the y-scale.
    y_scale = None
    if 'y-scale' in info:
      y_scale = info['y-scale'][y_metric]
    else:
      assert 'y-scale' in plot_hacks
      y_scale = plot_hacks['y-scale'][y_metric]
    assert y_scale is not None

    # Set the y-shift.
    y_shift = None
    if 'y-shift' in info:
      y_shift = info['y-shift'][y_metric]
      if isinstance(y_shift, dict):
        y_shift = y_shift[workload_name]
    else:
      assert 'y-shift' in plot_hacks
      y_shift = plot_hacks['y-shift'][y_metric]
    assert y_shift is not None

    y_pos = y_value + y_scale * (axs.get_ylim()[1] - axs.get_ylim()[0]) + y_shift

    # Strip the version if requested.
    label = info['label']
    if strip_version:
      label = re.sub(r'\s?v\d+\.\d+(\.\d+)?', '', label)

    if idx is not None:
      axs.text(
        x_pos,
        y_pos,
        label,
        color='black',
        va='center',
        ha=ha,
        fontsize=legend_fontsize,
        fontweight='bold',
        clip_on=True  # Ensures text doesn't overflow outside the plot area
      )

  for idx, info in enumerate(baselines):
    if info['tag'] not in agg_df['config'].values:
      continue
    y_value = agg_df.loc[agg_df['config'] == info['tag'], y_metric].values[0]

    # add_competitor(info, y_value, None)
    add_competitor(info, y_value, idx)