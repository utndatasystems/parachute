#!/usr/bin/env bash

# Arguments
db=$1
workload_dir=$2
duckdb_binary=$3

# Ensure required arguments are provided
test -z "$db" && echo "Usage: $0 <dbfile> <workload-dir> <duckdb-binary>" && exit 1
test -f "$db" || { echo "Error: Database file $db does not exist"; exit 1; }
test -d "$workload_dir" || { echo "Error: Workload directory $workload_dir does not exist"; exit 1; }

echo "Running EXPLAIN (FORMAT JSON) on queries in $workload_dir/sql..."

# Output directory
output_dir="$workload_dir/plan"
mkdir -p "$output_dir"

# Iterate over all SQL files in workload_dir/sql
for sql_file in "$workload_dir"/sql/*.sql; do
    [ -f "$sql_file" ] || { echo "No SQL files found in $workload_dir/sql"; exit 1; }
    
    query=$(cat "$sql_file")
    output_file="$output_dir/$(basename "$sql_file" .sql).json"
    
    echo "Processing $(basename "$sql_file")..."
    
    # Run the query and save the JSON output
    $duckdb_binary "$db" -c "EXPLAIN (FORMAT JSON) $query;" > "$output_file"
    
    echo "Execution plan saved to $output_file"
done
