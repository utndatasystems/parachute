#!/bin/bash

# Ensure at least 4 arguments are passed
if [[ $# -lt 4 ]]; then
  echo "Usage: $0 <data_dir> <workload_dir> <duckdb_binary> <competitor_type> [threads]"
  exit 1
fi

# Parse arguments
data_dir=$1
workload_dir=$2
duckdb_binary=$3
competitor_type=$4

workload_name=$(basename "$workload_dir")              

# If a 5th argument is provided, use it as the only thread count; otherwise, use the default list
if [[ -n "$5" ]]; then
  THREADS=("$5")
else
  THREADS=(1 48)
fi

# Make it available to child processes (since we'll run multiple scripts afterwards).
if [[ -z "$SUDO_PASSWORD" ]]; then
    read -s -p "Please enter password for sudo: " SUDO_PASSWORD
    echo ""  # Newline after silent input
fi
export SUDO_PASSWORD

# Extract the basename of the data_dir (e.g., 'imdb' from 'data/imdb/')
basename=$(basename "$data_dir")

# Define the array of parachute bit-width values
PBW=(16 8 4 2)
TRANSITIVITY=(0) # 0 1
ADAPTIVITY=(1)
ALTITUDE=(1 2 3)
OPT=(0)

# Loop through each bit-width and run the script.
for threads in "${THREADS[@]}"; do
  for pbw in "${PBW[@]}"; do
    # Loop through transitive values (0 and 1).
    for transitivity in "${TRANSITIVITY[@]}"; do
      for adaptivity in "${ADAPTIVITY[@]}"; do
        for altitude in "${ALTITUDE[@]}"; do
          for opt in "${OPT[@]}"; do
            echo "Running $competitor_type with $duckdb_binary"

            # Construct the db_file name
            db_file="dbs/${workload_name}_${basename}-parachute-${pbw}-${transitivity}-${adaptivity}.duckdb"

            echo "Running on db_file=$db_file: pbw=$pbw, transitivity=$transitivity, adaptivity=$adaptivity altitude=$altitude, opt=$opt, threads=$threads"

            # Check if the file exists
            if [[ ! -f "$db_file" ]]; then
              echo "Error: $db_file does not exist. Skipping pbw=$pbw, transitivity=$transitivity, adaptivity=$adaptive, altitude=$altitude, opt=$opt"
              continue
            fi
            
            # Run.
            ./bench-utils/run-queries.sh "$db_file" "$data_dir" "$workload_dir" "$threads" "$duckdb_binary" "${competitor_type}-${pbw}-${transitivity}-${adaptivity}-${altitude}-${opt}"
          done
        done
      done
    done
  done
done