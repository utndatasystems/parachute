# 🪂 Parachute: Single-Pass Bi-Directional Information Passing

Parachute builds join-induced fingerprint columns on FK-tables to enable a bi-directional information flow through the query plan.

The following steps will reproduce the results on the JOB workload.

## 🌐 Repositories

All necessary repositories are collected in a common repository. `PSF` refers to Probe-Side Filtering - the implementation is due to [@andizimmerer](https://github.com/andizimmerer).

- ❄️ (<img src="assets/duckdb.png" alt="duckdb" style="height: 1em;">): DuckDB w/ frozen query plans.
  - v1.2.0: Branch [`duckdb-v1.2.0-frozen-plans`](https://github.com/utndatasystems/parachute-competitors/tree/stoian-duckdb-v1.2.0-frozen-plans).
  - v0.9.2: Branch [`duckdb-v0.9.2-frozen-plans`](https://github.com/utndatasystems/parachute-competitors/tree/stoian-duckdb-v0.9.2-frozen-plans).
- <img src="assets/duckdb.png" alt="duckdb" style="height: 1em;"> + `PSF`: DuckDB + `PSF`: Branch [`psf`](https://github.com/utndatasystems/parachute-competitors/tree/stoian-psf).
- ❄️ (<img src="assets/duckdb.png" alt="duckdb" style="height: 1em;"> + `PSF`): DuckDB + `PSF` w/ frozen query plans: Branch [`psf-frozen-plans`](https://github.com/utndatasystems/parachute-competitors/tree/stoian-psf-frozen-plans). 

## 🗂️ Data

Download IMDb from http://event.cwi.nl/da/job/imdb.tgz and place it under `data/imdb`.

Use `data-loader.ipynb` to load IMDb into `duckdb`. This will create a database file `dbs/imdb.duckdb`.

## 🛠️ Setup

Install the required packages:

`pip install -r requirements.txt`

## 🧱 Building `parachute`

Build parachute columns of bit-width `pbw` $\in \{2, 4, 8, 16\}$.

```
./build-script.sh metadata/imdb workload/job
```

or to run for a single `pbw`, e.g., `pbw = 4`, `transitivity = 0`, `adaptivity = 1`:

```
python build-script.py  --pbw 4 --data-dir metadata/imdb --workload-dir workload/job --transitivity 0 --adaptivity 1
```

## 📊 Benchmark

All benchmark results are stored under `query-log`.

### <img src="assets/duckdb.png" alt="duckdb" style="height: 1em;"> `duckdb`

DuckDB v1.2.0:

```
./bench-utils/run-queries.sh dbs/imdb.duckdb metadata/imdb workload/job/ 1 ~/.duckdb/cli/1.2.0/duckdb duckdb
```

### <img src="assets/duckdb.png" alt="duckdb" style="height: 1em;"> + PSF: `psf`

DuckDB v1.2.0 + PSF:

```
./bench-utils/run-queries.sh dbs/imdb.duckdb metadata/imdb workload/job/ 1 ../dev/stoian-psf/build/release/duckdb sip
```

### <img src="assets/duckdb.png" alt="duckdb" style="height: 1em;"> + RPT: `rpt`

Official RPT implementation by Zhao et al. ([GitHub](https://github.com/embryo-labs/Robust-Predicate-Transfer)):

```
./bench-utils/run-queries.sh dbs/imdb-v0.9.2.duckdb metadata/imdb workload/job/ 1 ../dev/rpt-v0.9.2/build/release/duckdb rpt
```

### 🪂 (<img src="assets/duckdb.png" alt="duckdb" style="height: 1em;">): `parachute[duckdb]`


To run all `parachute[duckdb]` configurations:

```
./run-script.sh metadata/imdb/ workload/job ../dev/stoian-duckdb-frozen-plans/build/release/duckdb parachute 1
```

or, individually (single-threaded), e.g., `altitude = 3`, `opt = 0`:

```
./bench-utils/run-queries.sh dbs/job_imdb-parachute-4-0-1.duckdb metadata/imdb workload/job/ 1 ../dev/stoian-duckdb-v1.2.0-frozen-plans/build/release/duckdb parachute-4-0-1-3-0
```

### 🪂(<img src="assets/duckdb.png" alt="duckdb" style="height: 1em;"> + PSF): `parachute[duckdb + psf]`

To run all `parachute[duckdb + psf]` configurations:

```
./run-script.sh metadata/imdb/ workload/job ../dev/stoian-psf-frozen-plans/build/release/duckdb sip_parachute 1
```

or, individually (single-threaded), e.g., `altitude = 2`, `opt = 0`.

```
./bench-utils/run-queries.sh dbs/job_imdb-parachute-4-0-1.duckdb metadata/imdb workload/job/ 1 ../dev/stoian-psf-frozen-plans/build/release/duckdb sip_parachute-4-0-1-2-0
```