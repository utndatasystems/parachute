# Parachute: Single-Pass Bi-Directional Information Passing.

If you just want to run JOB, follow these steps.

## Download Data

Download IMDb from http://event.cwi.nl/da/job/imdb.tgz and place it under `raw-data/imdb`.

## Python Setup

Then install the required packages:

`pip install -r requirements.txt`

## Build iMDB Database

Use `data-loader.ipynb` to load IMDb into `duckdb`.

This will create a `.duckdb` file: `dbs/imdb.duckdb`.

## SIP repository

To download `duckdb` with frozen plans, please download [this](https://github.com/stoianmihail/duckdb-parachute/tree/stoian-card-est) branch.

To download our SIP implementation in `duckdb` (with bloom-filter size upper-bound), please use [this](https://github.com/utndatasystems/duckdb-adaptive-sip/tree/stoian-adaptive-sip) branch.

To download the SIP implementation with _frozen_ duckdb plans, use [this](https://github.com/utndatasystems/duckdb-adaptive-sip/tree/stoian-adaptive-sip) branch.

## Building `parachute`

### `build-script.sh`

```
./build-script.sh data/imdb workload/job
```

or

to run `pbw = 4`, `transitivity = 0`, `adaptivity = 1`:

```
python build-script.py  --pbw 4 --data-dir data/imdb --workload-dir workload/job --transitivity 0 --adaptivity 1
```

## Benchmark

### vanilla `parachute`:

```
./run-script.sh data/imdb/ workload/job ../dev/duckdb-parachute/build/release/duckdb parachute 1
```

### `parachute[duckdb + sip]`:

```
./run-script.sh data/imdb/ workload/job ../dev/duckdb-frozen-plans/build/release/duckdb sip_parachute 1
```

or, individually (single-threaded): E.g., `altitude = 3`, `opt = 0`.

```
./bench-utils/run-queries.sh dbs/job_imdb-parachute-4-0-1.duckdb data/imdb workload/job/ 1 ../dev/duckdb-frozen-plans/build/release/duckdb parachute-4-0-1-3-0
```