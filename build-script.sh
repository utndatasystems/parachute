#!/bin/bash

# Ensure correct number of arguments are passed
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <data_dir> <workload_dir> [show]"
  exit 1
fi

# Parse arguments
data_dir=$1
workload_dir=$2
show=${3:-0}  # Default to 0 if not provided

# Define the array of parachute bit-width values
PBW_VALUES=(2 4 8 16)
TRANSITIVITY_VALUES=(0)
ADAPTIVITY_VALUES=(1)

# Loop through each bit-width and run the script
for pbw in "${PBW_VALUES[@]}"; do
  # Loop through transitive values (0 and 1).
  for transitivity in "${TRANSITIVITY_VALUES[@]}"; do
    for adaptivity in "${ADAPTIVITY_VALUES[@]}"; do
      echo "Running with pbw=$pbw and transitivity=$transitivity and adaptivity=$adaptivity"
      
      # Construct the Python command
      cmd=("python" "build-script.py" "--pbw" "$pbw" "--data-dir" "$data_dir" "--workload-dir" "$workload_dir" "--transitivity" "$transitivity" "--adaptivity" "$adaptivity")
      
      # Add --show 1 if show is 1
      if [[ "$show" -eq 1 ]]; then
        cmd+=("--show")
      fi

      # Execute the command
      "${cmd[@]}"
    done
  done
done