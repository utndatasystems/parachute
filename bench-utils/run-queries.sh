#!/usr/bin/env bash

db=$1
data_dir=$2
workload_dir=$3
threads=$4
duckdb_binary=$5
competitor=$6

if [ "$EUID" -eq 0 ]; then
    echo "Please DON'T run this script as root by default. The script will ask you for the password."
    exit 1
fi

test -z "$1" && echo "Usage: $0 <dbfile> <data-dir> <workload-dir> <num-threads> <duckdb-binary> <competitor>" && exit 1
test -f "$db" || { echo "dbfile $db doesn't exist"; exit 1; }

if [[ "$(basename "$workload_dir")" == "sql" ]]; then
    echo "Error: workload_dir should not end in 'sql'"
    exit 1
fi

data_name=$(basename "$data_dir")
workload_name=$(basename "$workload_dir")

echo "$data_name"

# if [[ -z "$SUDO_PASSWORD" ]]; then
#     read -s -p "Please enter password for sudo: " SUDO_PASSWORD
#     echo ""  # Newline after silent input
# fi
# export SUDO_PASSWORD

test -z "$SUDO_PASSWORD" && read -s -p "Please enter password for sudo: " SUDO_PASSWORD

dbname="$(basename "$db" .duckdb)"
basedir="$dbname/$workload_name/$(hostname)-$threads-threads/$competitor-$(date +%Y%m%d-%H-%M-%S)"
logdir_cold="./query-log/$basedir/cold"
logdir_hot="./query-log/$basedir/hot"

echo $basedir

mkdir -p "$logdir_cold" "$logdir_hot"

for qfile in "$workload_dir"/sql/*.sql; do
    [ -f "$qfile" ] || { echo "No SQL files found in $workload_dir"; exit 1; }
    qnr=$(basename "$qfile" .sql)
    logfile_cold="$logdir_cold/$qnr.json"
    logfile_hot="$logdir_hot/$qnr.json"

    optimization_time_cold_file="$logdir_cold/$qnr-optimization-time.txt"
    optimization_time_hot_file="$logdir_hot/$qnr-optimization-time.txt"

    echo "Run ${qfile}.."

    # Default option.
    actual_query=$(cat "$qfile")

    echo $competitor

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
        python3 run-parachute.py "$data_dir" "$workload_dir" "$qfile" "$tmpfile" "$optimization_time_cold_file" "$optimization_time_hot_file" "$competitor"
        actual_query=$(cat "$tmpfile")
    else
        parachute_stats_file=""
    fi

    # The config that will be sent to duckdb.
    query="
SET threads = $threads;
PRAGMA enable_profiling='json';
PRAGMA profile_output='$logfile_cold';
-- PRAGMA profiling_mode = 'detailed';
$parachute_stats_file;
$actual_query;

PRAGMA profile_output='$logfile_hot';
$actual_query;
"
    echo "$SUDO_PASSWORD" | sudo -S bash -c 'free && sync && echo 3 > /proc/sys/vm/drop_caches && free' >/tmp/duckdb-dropcache.log
    # echo $actual_query
    $duckdb_binary "$db" -c "$query" -readonly
done