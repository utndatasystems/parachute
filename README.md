# Parachute: Single-Pass Bi-Directional Information Passing

If you just want to run JOB, follow these steps.

## Download Data

Download IMDb from http://event.cwi.nl/da/job/imdb.tgz and place it under `raw-data/imdb`.

## Python Setup

Then install the required packages:

`pip install -r requirements.txt`

## Build IMDb Database

Use `data-loader.ipynb` to load IMDb into `duckdb`.

This will create a `.duckdb` file: `dbs/imdb.duckdb`.

## Frozen `duckdb` plans

To have frozen duckdb plans, please download and compile our `duckdb` branch, available at:

https://github.com/stoianmihail/duckdb-parachute/tree/stoian-card-est

## SIP repository

We adapt Andi Zimmerer's implementation of SIP in DuckDB v1.2: https://github.com/andizimmerer/duckdb/tree/azimmerer/sideways-information-passingm, as follows:
1. Bound the bloom-filter size (this avoids an OS-`kill` due to excessive allocation in CEB): https://github.com/utndatasystems/duckdb-adaptive-sip/tree/stoian-adaptive-sip.
2. Frozen plans for SIP: https://github.com/utndatasystems/duckdb-adaptive-sip/tree/stoian-adaptive-sip

To this end, download (1) and (2) and prepare their corresponding binaries for the upcoming benchmarks.

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

Before you start, you should compile the corresponding binaries.

The benchmark results are stored into `query-log`.

### `duckdb`

You can install `duckdb` from the [official page](https://duckdb.org/docs/installation/?version=stable&environment=cli&platform=macos&download_method=direct).

```
./run-script.sh data/imdb/ workload/job <your_duckdb_binary> duckdb 1
```

### `sip`

```
./run-script.sh data/imdb/ workload/job ../dev/duckdb-adaptive-sip/build/release/duckdb sip 1
```


### vanilla `parachute`:

```
./run-script.sh data/imdb/ workload/job ../dev/duckdb-parachute/build/release/duckdb parachute 1
```

or, individually (single-threaded): E.g., `altitude = 2`, `opt = 0`.

```
./bench-utils/run-queries.sh dbs/job_imdb-parachute-4-0-1.duckdb data/imdb workload/job/ 1 ../dev/duckdb-parachute/build/release/duckdb parachute-4-0-1-2-0
```

### `parachute[duckdb + sip]`:

```
./run-script.sh data/imdb/ workload/job ../dev/duckdb-frozen-plans/build/release/duckdb sip_parachute 1
```

or, individually (single-threaded): E.g., `altitude = 2`, `opt = 0`.

```
./bench-utils/run-queries.sh dbs/job_imdb-parachute-4-0-1.duckdb data/imdb workload/job/ 1 ../dev/duckdb-frozen-plans/build/release/duckdb sip_parachute-4-0-1-2-0
```
