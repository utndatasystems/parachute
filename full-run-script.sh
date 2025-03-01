# Make it available to child processes (since we'll run multiple scripts afterwards).
if [[ -z "$SUDO_PASSWORD" ]]; then
    read -s -p "Please enter password for sudo: " SUDO_PASSWORD
    echo ""  # Newline after silent input
fi
export SUDO_PASSWORD

./run-script.sh data/imdb/ workload/job ../dev/duckdb-parachute/build/release/duckdb parachute 1
./run-script.sh data/imdb/ workload/job ../dev/duckdb-frozen-plans/build/release/duckdb sip_parachute 1