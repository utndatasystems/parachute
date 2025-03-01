import os
import re
import json
import pandas as pd
import plan_utils

def search_dir_by_token(base_path, token):
  print(f'token={token}')
  experiment_dirs = [d for d in os.listdir(base_path) if d == token]
  if not experiment_dirs:
    return None
  return experiment_dirs[0]

def config_to_str(competitor_type, config):
  if competitor_type in ['duckdb', 'sip']:
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
  subfolders = [f for f in subfolders if f.startswith(f'{competitor_type}-')]
  if not subfolders:
    return None

  if competitor_type in ['duckdb', 'sip']:
    pattern = re.compile(rf'^{competitor_type}-.*$')
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

    print(f'key={key}')
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

  return latest_experiments

def extract_data_from_experiment(experiment_path, competitor_type, num_threads, folder, config):
  results = []
  config_str = config_to_str(competitor_type, config)

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
        results.append({
          'competitor-type': competitor_type,
          'db-file' : folder,
          'config': config_str,
          'mode': mode,
          'num-threads': num_threads,
          'query': query_id,
          'latency (s)': json_data.get('latency', None),
          'cout' : plan_utils.compute_cout(json_data),
          '#made-it': plan_utils.compute_made_it(json_data),
          'base-size': plan_utils.compute_base_size(json_data),
          'extra-optimization-time (ns)': extra_optimization_time
        })

  # Convert to df.
  ret_df = pd.DataFrame(results)
  print(experiment_path, competitor_type, num_threads, folder, config)
  print(len(ret_df))

  # Flush.
  ret_df.to_csv(acc_filepath, index=False)

  return ret_df

def collect_data(root_path, data_name, workload_name, machines, list_num_threads, competitor_types):
  # Empty df.
  all_data = pd.DataFrame()
  
  for competitor_type in competitor_types:
    print(f'\n[NEW] competitor_type={competitor_type}')
    pattern = None
    if competitor_type in ['parachute', 'sip_parachute']:
      if workload_name == 'job':
        tag = f'{data_name}-parachute'
      else:
        tag = f'{workload_name}_{data_name}-parachute'
      pattern = re.compile(f'^{tag}')
    elif competitor_type in ['duckdb', 'sip']:
      tag = f'{data_name}'
      pattern = re.compile(f'^{tag}$')
    else:
      assert 0
    assert pattern is not None

    print(f'tag={tag}')

    for folder in os.listdir(root_path):
      if not pattern.match(folder):
        continue
      print(f'\nfolder={folder}')
      variant_path = os.path.join(root_path, folder)
      workload_dir = search_dir_by_token(variant_path, token=workload_name)
      if workload_dir is None:
        continue

      print(f'Found: {workload_dir}')

      for machine in machines:
        print(f'>>>>> MACHINE={machine}')    
        for num_threads in list_num_threads:
          print(f'num_threads={num_threads}')

          # Hack.
          fake_num_threads = num_threads
          # if competitor_type == 'sip':
            # fake_num_threads = 1

          workload_threads_dir = search_dir_by_token(os.path.join(variant_path, workload_dir), token=f'{machine}-{fake_num_threads}-threads')
          if workload_threads_dir is None:
            continue


          print(f'#### workload_threads_dir={workload_threads_dir}')
          exp_dirs = get_latest_experiments_of_competitor(competitor_type, os.path.join(variant_path, workload_dir, workload_threads_dir))

          # No exps?
          if exp_dirs is None:
            continue

          print(f'exp_dirs={exp_dirs}')

          for config, exp_dir in exp_dirs.items():
            print(f'config={config}, exp_dir={exp_dir}')
            
            curr_data = extract_data_from_experiment(os.path.join(
              variant_path,
              workload_dir,
              workload_threads_dir,
              exp_dir
            ), competitor_type, num_threads, folder, config)
            if curr_data is None:
              continue
            all_data = pd.concat([all_data, curr_data])
  
  return all_data