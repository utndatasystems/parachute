#!/usr/bin/env bash

db=$1
data_dir=$2
csv_file=$3
threads=$4
duckdb_binary=$5
competitor=$6

test -z "$1" && echo "Usage: $0 <dbfile> <data-dir> <workload-csv-file> <num-threads> <duckdb-binary> <competitor>" && exit 1
test -f "$db" || { echo "dbfile $db doesn't exist"; exit 1; }
test -f "$csv_file" || { echo "CSV file $csv_file doesn't exist"; exit 1; }

# Extracts '0_1_96' from '0_1_96.csv'
csv_basename=$(basename "$csv_file" .csv)                 
# Extracts '90_100' from '.../90_100/0_1_96.csv'        
csv_dirname=$(basename "$(dirname "$csv_file")")          

# The workload name.
workload_name="rab_${csv_dirname}_${csv_basename}"
workload_dir="workload/$workload_name"
output_sql="$workload_dir/${competitor}.sql"

echo $workload_dir

# Create folder.
data_name=$(basename "$data_dir")
dbname="$(basename "$db" .duckdb)"
basedir="$dbname/$workload_name/$(hostname)-$threads-threads/$competitor-$(date +%Y%m%d-%H-%M-%S)"
logdir="./query-log/$basedir/hot"

echo $basedir

mkdir -p "$logdir"

echo "Output SQL file: $output_sql for ${competitor}"

echo "
-- Generated SQL script
SET threads = $threads;
PRAGMA enable_profiling='json';
" > "$output_sql"

while IFS=, read -r filepath num_joins_user num_joins_benchmark was_cached query_id; do
    # Skip header line
    if [[ "$filepath" == "filepath" ]]; then
        continue
    fi

    # Modify path if needed
    if [[ "$filepath" == benchmarks/ceb/* ]]; then
        modified_path=$(echo "$filepath" | sed -E 's|benchmarks/ceb/([^/]+)/([^/]+).sql|workload/ceb/sql/\1_\2.sql|')
    elif [[ "$filepath" == benchmarks/job/* ]]; then
        modified_path=$(echo "$filepath" | sed -E 's|benchmarks/job/([^/]+).sql|workload/job/sql/\1.sql|')
    else
        modified_path="$filepath"
    fi

    qfile="$modified_path"
    [ -f "$qfile" ] || { echo "No SQL file found for $qfile"; exit 1; }

    # Get the query id.
    qnr=$(basename "$qfile" .sql)
    logfile="$logdir/$qnr.json"
    optimization_time_file="$logdir/$qnr-optimization-time.txt"

    # Default option.
    actual_query=$(cat "$qfile")

    if [[ "$competitor" == parachute* || "$competitor" == sip_parachute* ]]; then
        # Parse the competitor structure.
        IFS='-' read -r _ pbw transitivity adaptivity altitude opt <<< "$competitor"

        echo $altitude
        echo $opt

        # If `opt` is 2, set the parachute_stats_file path
        # If `opt` is 1, use the default duckdb optimizer. This KEEPS the parachute columns.
        # Otherwise, frozen plans!
        if [[ "$opt" == "2" ]]; then
            parachute_stats_file="SET parachute_stats_file='data/${data_name}/parachute-stats-$pbw-$transitivity-$adaptivity.csv'"
        elif [[ "$opt" == "1" ]]; then
            parachute_stats_file="SET parachute_stats_file='fake'"
        else
            # Completely ignore the parachute columns.
            parachute_stats_file=""
        fi

        tmpfile=$(mktemp)
        python3 run-parachute.py "$data_dir" "$workload_dir" "$qfile" "$tmpfile" "$optimization_time_file" "$optimization_time_file" "$competitor"
        actual_query=$(cat "$tmpfile")
    else
        parachute_stats_file=""
    fi

    # Append to output SQL file
    {
        echo "-- $filepath"
        echo "PRAGMA profile_output='$logfile';"
        $actual_query;
        echo ""
    } >> "$output_sql"

done < "$csv_file"

echo "Generated SQL saved to $output_sql."