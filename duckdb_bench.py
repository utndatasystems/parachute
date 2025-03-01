import subprocess
import os
import utils
import json

def prepare_query(sql_query, prefix=None):
  sql_query = sql_query.strip('\n')
  if not sql_query.endswith(';'):
    sql_query += ';'
  if prefix is not None:
    sql_query = f'{prefix} {sql_query}'
  sql_query += '\n'
  return sql_query

def get_query_result(cli_path, db_path, sql_query, num_threads):
  process = subprocess.Popen([cli_path, db_path, "-readonly"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
  process.stdin.write(f"set threads to {num_threads};\n")
  process.stdin.write(".mode json\n")
  process.stdin.write(prepare_query(sql_query))
  # process.stdin.close()  
  output, error = process.communicate()  
  process.kill()

  # TODO: This only works for JOB-like queries, since there is only 1 line to read from.
  if output:
    return output.splitlines()
  return []

# def parse_result_from_output(stream):
#   print(f'\n\n[parse_result] !!!! ')
#   ret = []
#   while True:
#     print(f'what????')
#     line = stream.readline()
#     print(f'...{line}..')
#     if not line:
#       break
#     print(line)
#     ret.append(line)

#   print(ret)

#   return ret

def parse_plan_from_output(stream):
  while True:
    line = stream.readline()
    print(line)
    if not line:
      break
    if line.startswith('['):
      return True
  assert 0

def parse_time_from_output(stream):
  pattern = 'Run Time (s): real '
  while True:
    line = stream.readline()
    # print(line)
    if not line:
      break
    if pattern in line:
      return float(line[len(pattern):].split(' ')[0])
  assert 0

def consume_output(stream):
  while True:
    line = stream.readline()
    print(f'[consume_output] {line}')
    if not line:
      break

def read_time_from_logfile(log_filename):
  # Read the actual query time from the log file.
  actual_time = None
  query_plan = utils.read_json(log_filename)
  actual_time = query_plan['latency']
  assert actual_time is not None
  return actual_time

class DuckdbPlanAnalyzer:
  def __init__(self, cli_path, db_path, num_threads):
    self.process = subprocess.Popen([cli_path, db_path, '-readonly'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    self.process.stdin.write(f"set threads to {num_threads};\n")
    self.process.stdin.flush()
    self.process.stdin.write(".mode json\n")
    self.process.stdin.flush()
    self.process.stdin.write("SET enable_profiling = 'json';\n")
    self.process.stdin.flush()
    self.process.stdin.write("SET profile_output = 'profile-test.json';\n")    
    self.process.stdin.flush()

  def analyze(self, sql_query):
    sql_query = prepare_query(sql_query)
    self.process.stdin.write(sql_query)
    self.process.stdin.flush()
    _ = parse_plan_from_output(self.process.stdout)
    return utils.read_json('profile-test.json')

class DynamicDuckdbBench:
  def __init__(self, cli_path, db_path, num_threads):
    self.process = subprocess.Popen([cli_path, db_path, '-readonly'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    self.process.stdin.write(f"set threads to {num_threads};\n")
    self.process.stdin.flush()
    self.process.stdin.write(".timer on\n")
    self.process.stdin.flush()
    self.process.stdin.write(".mode json\n")
    self.process.stdin.flush()

  def send(self, sql_query, num_repeats=1):
    assert num_repeats > 0
    times = []
    for _ in range(num_repeats):
      sql_query = prepare_query(sql_query)
      self.process.stdin.write(sql_query)
      self.process.stdin.flush()
      output = parse_time_from_output(self.process.stdout)
      times.append(output)
    # self.process.kill()
    
    # Skip the first one if `num_repeats` > 1.
    if num_repeats > 1:
      times = times[1:]

    return sum(times) / len(times)
  
  def take_plan(self, sql_query):
    sql_query = prepare_query(sql_query)
    self.process.stdin.write(sql_query)
    self.process.stdin.flush()
    output = parse_time_from_output(self.process.stdout)

class StaticDuckdbBench:
  def __init__(self, cli_path, vanilla_db_path, parachute_db_path, parachute_stats_file, num_threads):
    self.cli_path = cli_path
    self.vanilla_db_path = vanilla_db_path
    self.parachute_db_path = parachute_db_path
    self.parachute_stats_file = parachute_stats_file
    self.num_threads = num_threads

  def get_db_path(self, type):
    if type == 'parachute':
      return self.parachute_db_path
    elif type == 'opt-parachute':
      return self.parachute_db_path
    elif type == 'vanilla':
      return self.vanilla_db_path

  def send(self, type, sql_query, num_repeats=1, return_output=False):
    assert num_repeats > 0
    print(f'\n\n[bench_query]')
    db_path = self.get_db_path(type)

    # Define the process.
    process = subprocess.Popen([self.cli_path, db_path, '-readonly'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    process.stdin.write(f"set threads to {self.num_threads};\n")
    process.stdin.flush()
    process.stdin.write(".timer on\n")
    process.stdin.flush()
    process.stdin.write(".mode json\n")
    process.stdin.flush()

    if type == 'opt-parachute':
      process.stdin.write(f"set parachute_stats_file='{self.parachute_stats_file}';")

    # Prepare the query.
    sql_query = prepare_query(sql_query)

    times = []
    for _ in range(num_repeats):
      process.stdin.write(sql_query)
      process.stdin.flush()
      output = parse_time_from_output(process.stdout)
      times.append(output)
    process.kill()

    print(f'>>>> DONE!!!!')
    
    # Skip the first one if `num_repeats` > 1.
    if num_repeats > 1:
      times = times[1:]

    query_result = None
    if return_output:
      db_path = self.get_db_path(type)
      query_result = get_query_result(self.cli_path, db_path, sql_query, self.num_threads)

    return sum(times) / len(times), query_result