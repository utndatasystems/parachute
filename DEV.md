# Slow Path (for dev)

# Setup

## Download Data

## Schema Parser

Run `schema-parser.ipynb` to have a JSON-representation of the SQL schema.

## Data Cleaning

NOTE: Starting from v1.2.0, this was fixed!

Run `data-cleaner.ipynb` before to prepare it for `duckdb`.

There is somewhere a bug related to double-quoted strings in `duckdb`.

## Python Setup

Please create a virtual env. Sth like: `python -m venv .venv`.

Then install the required packages:

`pip install -r requirements.txt`

## DuckDB Setup

To use `duckdb` within notebooks, please compile `duckdb` like this:

`./tools/pythonpkg/clean.sh && BUILD_PYTHON=1 GEN=ninja make`.

Note: `clean.sh` makes sure that the latest version is used, e.g., if you switch between branches.

We currently use our repo: https://github.com/stoianmihail/duckdb-parachute/tree/stoian-card-est.

## Build Database

Use `data-loader.ipynb` to load iMDB into duckdb.

This will create two `.duckdb` files: `imdb.duckdb`.

## Convert SQL queries to .qfn

Note: For JOB, this is already done. The converted queries are in `workload/job/qfn`.

Run `sql-to-qfn.ipynb` to convert queries to qfn-form.

## Analyze Data.

Note: For iMDB, this is already done. The result is in `workload/job/analysis.json`.

Check out `analyze-data.ipynb`.

# Benchmarks

Our binary: `../dev/duckdb-parachute/build/release/duckdb`

## `duckdb`

### JOB

```
./bench-utils/run-queries.sh dbs/imdb.duckdb data/imdb workload/job/ 1 ~/.duckdb/cli/1.2.0/duckdb duckdb
```

### CEB

```
./bench-utils/run-queries.sh dbs/imdb.duckdb data/imdb workload/ceb/ 1 ~/.duckdb/cli/1.2.0/duckdb duckdb
```

## `duckdb` + `sip`

### JOB

Single-threaded:

```
./bench-utils/run-queries.sh dbs/imdb.duckdb data/imdb workload/job/ 1 ../dev/duckdb-sip/build/release/duckdb sip
```

Multi-threaded:

```
./bench-utils/run-queries.sh dbs/imdb.duckdb data/imdb workload/job/ 48 ../dev/duckdb-sip/build/release/duckdb sip
```

### CEB

Single-threaded:

```
./bench-utils/run-queries.sh dbs/imdb.duckdb data/imdb workload/ceb/ 1 ../dev/duckdb-sip/build/release/duckdb sip
```

Multi-threaded:

```
./bench-utils/run-queries.sh dbs/imdb.duckdb data/imdb workload/ceb/ 48 ../dev/duckdb-sip/build/release/duckdb sip
```

## `parachute`

### `build-script.sh`

#### JOB

```
./build-script.sh data/imdb workload/job
```

or

to run `pbw = 4`, `transitivity = 0`, `adaptivity = 1`:

```
python build-script.py  --pbw 4 --data-dir data/imdb --workload-dir workload/job --transitivity 0 --adaptivity 1
```

It's always good to activate the `adaptivity` option.

#### CEB

```
./build-script.sh data/imdb workload/ceb
```

or

to run `pbw = 4`, `transitivity = 0`, `adaptivity = 1`:

```
python build-script.py --pbw 4 --data-dir data/imdb --workload-dir workload/ceb --transitivity 0 --adaptivity 1
```

### `run-script.sh`

#### Pre-processing

Note: Before you run a workload, you should make sure you have the `explained` query plans.

This can be achieved by using `gen-expl-plan.sh` and then `fix-expl-plan.ipynb` to ensure we indeed have JSON data.

##### JOB

```
./gen-expl-plan.sh dbs/imdb.duckdb workload/job ~/.duckdb/cli/1.2.0/duckdb
```

##### CEB

```
./gen-expl-plan.sh dbs/imdb.duckdb workload/ceb ~/.duckdb/cli/1.2.0/duckdb
```

#### Benchmarks

##### JOB

vanilla `parachute`:

```
./run-script.sh data/imdb/ workload/job ../dev/duckdb-parachute/build/release/duckdb parachute 1
```

`parachute[duckdb + sip]`:

```
./run-script.sh data/imdb/ workload/job ../dev/duckdb-frozen-plans/build/release/duckdb sip_parachute 1
```

or, individually (single-threaded): E.g., `altitude = 3`, `opt = 0`.

```
./bench-utils/run-queries.sh dbs/job_imdb-parachute-4-0-1.duckdb data/imdb workload/job/ 1 ../dev/duckdb-frozen-plans/build/release/duckdb parachute-4-0-1
```

##### CEB

vanilla `parachute`:

```
./run-script.sh data/imdb/ workload/ceb ../dev/duckdb-parachute/build/release/duckdb parachute 1
```

`parachute[duckdb + sip]`:

```
./run-script.sh data/imdb/ workload/ceb ../dev/duckdb-frozen-plans/build/release/duckdb sip_parachute 1
```

or, individually (single-threaded):

```
./bench-utils/run-queries.sh dbs/ceb_imdb-parachute-4-0-1.duckdb data/imdb workload/ceb/ 1 ../dev/duckdb-frozen-plans/build/release/duckdb parachute-4-0-1-2-0
```

### Sample

```
./bench-utils/run-queries.sh dbs/imdb-parachute-2-0.duckdb data/imdb workload/job/ 48 ../dev/duckdb-parachute/build/release/duckdb parachute-2-0-1
```

### `run-script.sh`

Single-threaded:

```
./run-script.sh data/imdb/ workload/job ../dev/duckdb-parachute/build/release/duckdb 1
```

or 

to run `pbw = 2`, `transitivity=0`, `adaptivity=` `opt=1`:


```
./bench-utils/run-queries.sh dbs/imdb-parachute-2-0.duckdb data/imdb workload/job/ 48 ../dev/duckdb-parachute/build/release/duckdb parachute-2-0-1
```

## Handy Examples

Build `pbw=16, transitivity=0, adaptivity=1`:

```
python build-script.py  --pbw 16 --data-dir data/imdb --workload-dir workload/job --transitivity 0 --adaptivity 1
```

Run: Vanilla parachute, single-threaded, 16-0-1, altitude = 1, opt = 0.

```
./bench-utils/run-queries.sh dbs/imdb-parachute-16-0-1.duckdb data/imdb workload/job/ 1 ../dev/duckdb-parachute/build/release/duckdb parachute-16-0-1-1-0
```

Run: Parachute + SIP, single-threaded, 16-0-1, altitude = 2, opt = 0.

./bench-utils/run-queries.sh dbs/imdb-parachute-16-0-1.duckdb data/imdb workload/job/ 1 ../dev/duckdb-frozen-plans/build/release/duckdb sip_parachute-16-0-1-2-0

Run: Parachute + SIP, single-threaded, 16-0-1, altitude = 3, opt = 0.

./bench-utils/run-queries.sh dbs/imdb-parachute-16-0-1.duckdb data/imdb workload/job/ 1 ../dev/duckdb-frozen-plans/build/release/duckdb sip_parachute-16-0-1-3-0

# Plotting

## Figure 1

Run `plan-analyzer.ipynb`.

## Debugging

If your use `parachute-bench.ipynb`, please use `show-progress.ipynb`. To this end, in `results/`, please suffix the latest file with `-takeit`, such that it's considered.