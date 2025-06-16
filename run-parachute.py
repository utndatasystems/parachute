import parachute
import parachute_rewriter
import sys
import os

USE_LIKE = True

data_dir = sys.argv[1]
workload_dir = sys.argv[2]
query_file = sys.argv[3]
tmp_file = sys.argv[4]
competitor = sys.argv[5]

print(workload_dir)
print(query_file)

assert competitor.startswith('parachute-') or competitor.startswith('sip_parachute-')
_, pbw, transitivity, adaptivity, altitude, opt = competitor.split('-')
pbw, transitivity, adaptivity, altitude, opt = int(pbw), int(transitivity), int(adaptivity), int(altitude), int(opt)

print(f'pbw={pbw}, transitivity={transitivity}, adaptivity={adaptivity}, altitude={altitude}, opt={opt}')

workload_name = os.path.basename(os.path.normpath(workload_dir))

print(f'workload_name={workload_name}')

parachute_obj = parachute.Parachute(data_dir, transitivity=transitivity, adaptivity=adaptivity, catalog_path=os.path.join(data_dir, f'{workload_name}_data-catalog-{pbw}-{transitivity}-{adaptivity}.json'))
rewriter = parachute_rewriter.ParachuteRewriter(parachute_obj, USE_LIKE)
rewritten_sql_query = rewriter.rewrite(query_file, altitude)

with open(tmp_file, 'w') as f:
  f.write(rewritten_sql_query + '\n')

# Dump the rewritten query.
if not os.path.isdir(os.path.join(workload_dir, 'rewritten')):
  os.mkdir(os.path.join(workload_dir, 'rewritten'))
with open(os.path.join(workload_dir, 'rewritten', os.path.basename(query_file).replace('.sql', f'-{pbw}-{transitivity}-{adaptivity}-{altitude}-{opt}.sql')), 'w') as f:
  f.write(f'explain analyze {rewritten_sql_query}')