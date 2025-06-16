#!/bin/bash

# Ensure at least 1 argument(s) are passed
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <workload_dir>"
  exit 1
fi

# Parse arguments
workload_dir=$1

# Make it available to child processes (since we'll run multiple scripts afterwards).
if [[ -z "$SUDO_PASSWORD" ]]; then
    read -s -p "Please enter password for sudo: " SUDO_PASSWORD
    echo ""  # Newline after silent input
fi
export SUDO_PASSWORD

# ./run-script.sh metadata/imdb/ $workload_dir ../dev/stoian-duckdb-frozen-plans/build/release/duckdb parachute 1
./run-script.sh metadata/imdb/ $workload_dir ../dev/stoian-ub-sip-frozen-plans/build/release/duckdb sip_parachute 1