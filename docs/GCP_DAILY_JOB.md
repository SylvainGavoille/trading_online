# GCP Daily ML Job — Architecture & Step-by-Step Documentation

## Overview

The daily GCP pipeline runs every weekday after US market close (22:20 New York time) to:

1. Refresh today's stock price history (Yahoo Finance via `download_history.py`)
2. Train a price-only LightGBM model and rank top stocks (`actions_pipeline.py`)
3. Collect today's options chain snapshot (Yahoo Finance via `collect_options_snapshot.py`)
4. Run the full options ML pipeline: walk-forward backtest + ranker (`pipeline.py`)

All data is stored in a GCS bucket mounted as a FUSE volume at `/mnt/quantum`.

---

## Architecture Diagram

```text
Cloud Scheduler (22:20 NY time, Mon-Fri)
        │
        ▼
Cloud Run Job
   ├── Service Account: quantum-ml-runner
   ├── GCS Volume mount: /mnt/quantum  ← all persistent data
   └── Container: quantum-ml:latest
           │
           └── uv run python src/ml/gcp_daily_job.py
                     │
                     ├── [1] Price refresh     → download_history.py     (Yahoo Finance)
                     ├── [2] Actions pipeline  → actions_pipeline.py     (LightGBM, price-only)
                     ├── [3] Options snapshot  → collect_options_snapshot.py (Yahoo Finance)
                     ├── [4] Portfolio check   → pipeline.py --snapshot  (bootstrap if empty)
                     └── [5] ML pipeline       → pipeline.py             (options ranker)
```

---

## Data Sources

| Data                                   | Source                     | Notes                                                              |
| -------------------------------------- | -------------------------- | ------------------------------------------------------------------ |
| Stock prices (OHLCV)                   | Yahoo Finance (`yfinance`) | Free, no API key needed                                            |
| Option chains (bid/ask/iv/volume/OI)   | Yahoo Finance (`yfinance`) | Free, no API key needed                                            |
| Option greeks (delta/gamma/vega/theta) | Not available              | Yahoo does not provide greeks; columns are `None` in training data |
| Symbol universe                        | `ibkr_us.sqlite`           | Pre-built list of US-listed symbols; ships in the Docker image     |

> **Note**: Yahoo Finance only provides _current_ option market data. Each daily run captures
> that day's prices. Historical option snapshots (past dates) are not available from Yahoo.
> The system builds its options history one day at a time, starting from the first job run.

---

## Deployment Modes

### Mode A — Single Job (`split_jobs_enabled = false`, default)

One Cloud Run Job runs all steps sequentially with `--mode full`.

```text
quantum-daily-ml  (2 CPU / 8Gi, timeout 2h)
   triggered by → quantum-daily-ml-trigger (22:20 NY, Mon-Fri)
```

### Mode B — Split Jobs (`split_jobs_enabled = true`)

Two independent Cloud Run Jobs for better resource isolation and independent retries.

```text
quantum-daily-ml-refresh   (2 CPU / 8Gi,  timeout 1.5h)  --mode refresh_only
   triggered by → quantum-daily-ml-refresh-trigger (22:20 NY)
   writes: /mnt/quantum/ml_output/_status/refresh_done_YYYY-MM-DD.json

quantum-daily-ml-pipeline  (4 CPU / 16Gi, timeout 3h)    --mode pipeline_only
   triggered by → quantum-daily-ml-pipeline-trigger (22:50 NY)
   waits: polls refresh marker before starting training (up to 120 min)
```

The 30-minute gap between triggers gives the refresh job time to start before the pipeline job begins polling.

---

## Terraform Infrastructure

### GCP APIs Enabled

| API                               | Purpose              |
| --------------------------------- | -------------------- |
| `run.googleapis.com`              | Cloud Run Jobs       |
| `cloudscheduler.googleapis.com`   | Cron triggers        |
| `artifactregistry.googleapis.com` | Docker image storage |
| `storage.googleapis.com`          | GCS data bucket      |
| `iam.googleapis.com`              | Service accounts     |
| `cloudbuild.googleapis.com`       | Remote Docker builds |

### GCS Data Bucket

- **Versioning enabled** — protects Parquet files from accidental overwrites
- **`force_destroy = false`** — `terraform destroy` will not delete the bucket or its data
- Mounted read/write into every Cloud Run container at `/mnt/quantum`

**Directory layout:**

```text
/mnt/quantum/
├── price_historical/         ← OHLCV Parquet, Hive-partitioned: year=/month=/day=
├── options_snapshot/         ← Options chain Parquet, same partitioning
├── portfolio_daily/          ← Portfolio position history
├── ml_output/
│   ├── actions/              ← Actions pipeline results (price-only model)
│   ├── recommendations/      ← Final ranker output (options model)
│   └── _status/
│       └── refresh_done_YYYY-MM-DD.json  ← Sync marker (split mode only)
└── ibkr_us.sqlite            ← Symbol universe DB (baked into Docker image)
```

### Service Accounts & IAM

**`quantum-ml-runner`** (runtime SA — runs inside containers)

- `roles/storage.objectAdmin` → read/write all GCS data

**`quantum-ml-scheduler`** (scheduler SA — used by Cloud Scheduler)

- `roles/run.developer` → can start Cloud Run Job executions
- `roles/iam.serviceAccountUser` on runtime SA → can impersonate it when launching

This separation means the scheduler cannot access data; it can only trigger a job.

### Cloud Scheduler Jobs

All schedulers POST to the Cloud Run Jobs API using an OAuth token signed by `quantum-ml-scheduler`.

Default schedules (America/New_York):

- Single mode: `20 22 * * 1-5` — 22:20 NY, weekdays
- Split refresh: `20 22 * * 1-5` — same
- Split pipeline: `50 22 * * 1-5` — 30 min later

---

## `gcp_daily_job.py` — Step-by-Step Execution Flow

### Step 0 — Initialization

Resolves all four data roots from CLI args (injected by Terraform), creates them if missing, and sets `today` / `run_day` (ISO date string) once for the entire run.

---

### Step 1 — Price Historical Refresh (`mode != pipeline_only`)

**Function**: `_step_price_refresh()`

**Goal**: ensure today's OHLCV bars exist in `price_historical/`.

**Idempotency**: if `price_historical/.../day=YYYY-MM-DD/` already has a Parquet file, the step is skipped entirely. Safe to rerun.

**Symbol universe**: `download_history.py` reads the symbol list from `ibkr_us.sqlite`.

- Resolved from `IBKR_SQLITE_PATH` env var, or project root default.
- If DB is missing + `--allow_missing_symbol_db` → warning, uses existing data.
- If DB is missing without that flag → `FileNotFoundError`, job fails.

**Two-phase download**:

1. **Daily refresh** (`--days 7`, `--skip-existing`): fast, fills the last 7 trading days.
2. **Bootstrap backfill** (`--days 365`, `--skip-existing`): runs once when the number of distinct day partitions is below `min_train_days + max(horizons)` (minimum 120). Fills the full year of history needed for model training. `--skip-existing` ensures already-downloaded days are never re-fetched.

---

### Step 2 — Actions Pipeline (`mode != pipeline_only`)

**Function**: `_step_actions_pipeline()`

**Goal**: train a pure price-based LightGBM model and rank top-K stocks. No options data dependency.

Runs `src/ml/actions_pipeline.py` as a subprocess with:

- `--horizons 2,5,10,21` — forward return prediction windows (days)
- `--topk 5` — minimum 5 recommendations even if `pipeline_topk=3`
- `--max_symbols 1500` — caps the universe to highest-volume stocks
- `--max_minutes 55` — internal soft timeout
- **Hard timeout**: 35 minutes via `subprocess.run(timeout=...)`

**What `actions_pipeline.py` does**:

1. Reads `price_historical/` Parquet
2. Builds technical indicator features (returns, volatility, momentum)
3. Computes forward return labels for each horizon
4. Runs walk-forward cross-validation (train=80d, test=20d, step=20d)
5. Trains `LGBMRegressor` per fold per horizon
6. Ranks top-K symbols by predicted forward return
7. Saves JSON results to `ml_output/actions/`

**Failure handling**: non-fatal — logs a warning and continues to the options step.

---

### Step 3 — Options Snapshot Collection (`mode != pipeline_only`)

**Function**: `_step_options_collect()`

**Goal**: collect today's option chains from Yahoo Finance and save to `options_snapshot/`.

**Idempotency**: if today's partition already exists, the step is skipped.

Runs `src/data/collect_options_snapshot.py` as a subprocess with:

- `--date YYYY-MM-DD` — today's date (controls the Hive partition path)
- `--top_n 30` — top 30 symbols by volume from `price_historical/`
- `--max_minutes 30` — soft internal cap
- **Hard timeout**: 45 minutes

**What `collect_options_snapshot.py` does per symbol**:

1. Fetches spot price from Yahoo Finance (`yf.Ticker.history(period="5d")`)
2. Gets available expirations (`yf.Ticker.options`) filtered by DTE range [7, 90]
3. Fetches `yf.Ticker.option_chain(expiry)` for each of the top 3 expirations
4. Filters strikes to ±20% of spot price
5. Saves bid/ask/last/iv/volume/OI rows (greeks are always `None`)
6. Saves to `options_snapshot/year=Y/month=M/day=YYYY-MM-DD/part-0.parquet`

**Gate check**: returns `False` if today's partition is still missing after collection. The caller then exits early to prevent the options ML pipeline from training on stale data.

---

### Step 4 — Refresh Marker (split mode, `mode == refresh_only`)

After completing steps 1–3, writes a JSON status file:

```json
{ "day": "2026-03-11", "status": "ok", "written_at_epoch_s": 1741651200.0 }
```

Path: `ml_output/_status/refresh_done_2026-03-11.json`

The pipeline job polls this file every 30 seconds (up to 120 minutes) before starting ML training.

---

### Step 5 — Pipeline-Only Wait (`mode == pipeline_only` + `--wait_for_refresh`)

Polls the refresh marker until found or timeout:

```python
while time.time() < deadline:
    if marker.exists() and json.loads(marker.read_text())["status"] == "ok":
        return True
    time.sleep(30)
```

On timeout → `TimeoutError`, job fails.

---

### Step 6 — Guards Before ML Training

Three guards protect against training on empty or stale data:

1. **No price data** → exit. Occurs on the very first job run before any download.
2. **No options data** → exit. Occurs if collection failed or on the very first run.
3. **No portfolio data** → runs `pipeline.py --snapshot` once to bootstrap, then exits if still empty.

---

### Step 7 — Portfolio Bootstrap

**Function**: `_step_portfolio_bootstrap()`

If `portfolio_daily/` has no Parquet files, runs `pipeline.py --snapshot` to create the initial portfolio history entry. Without portfolio history the options ranker has no context for position sizing.

---

### Step 8 — Options ML Pipeline

**Function**: `_step_ml_pipeline()`

Runs the full walk-forward backtest and ranker via `src/ml/pipeline.py`:

```text
--price_root     /mnt/quantum/price_historical
--options_root   /mnt/quantum/options_snapshot
--portfolio_root /mnt/quantum/portfolio_daily
--out_dir        /mnt/quantum/ml_output
--start          YYYY-MM-DD  (today - lookback_days)
--end            YYYY-MM-DD  (today)
--horizons       5 10
--categories     long_premium
--topk           3
--min_train_days 80
--test_days      20
--step_days      20
--lgbm_jobs      1
--max_minutes    45
```

**What `pipeline.py` does**:

1. `read_underlyings()` — price Parquet in date range
2. `read_options()` — options snapshot Parquet
3. `read_portfolio()` — portfolio history
4. `build_training_table()` — joins price features + IV features + portfolio context
5. `walk_forward_splits()` — time-ordered train/test windows
6. Per fold: `train_ranker()` (LightGBM ranker), `backtest_ranker()` (simulate top-K selection)
7. Aggregates fold results, writes ranked JSON to `ml_output/recommendations/`

**Hard subprocess timeout**: 60 minutes.

---

## Key Design Decisions

### Idempotency

Every data step checks for an existing today partition before running. Re-running the job within the same day (after a failure or manual trigger) is always safe — it only fills gaps.

### Fault Isolation

Each subprocess has its own timeout. A failure in one step logs a warning and either skips or aborts only that stage — it does not crash the entire container.

### Timeout Layering

Two timeout layers per subprocess:

1. **Soft (`--max_minutes`)**: internal budget — stops adding ML fold iterations gracefully
2. **Hard (`timeout_s`)**: OS-level `subprocess.run` kill — prevents hangs from blocking the Cloud Run Job

### No Options History Before First Run

Yahoo Finance only provides current market data, not historical snapshots. Options training history accumulates one day at a time from the first job run. Price history is backfilled on first run (up to 365 days), but options history cannot be retroactively reconstructed.

### Split Jobs vs. Single Job

|                      | Single Job              | Split Jobs     |
| -------------------- | ----------------------- | -------------- |
| `split_jobs_enabled` | `false`                 | `true`         |
| Jobs                 | 1                       | 2              |
| Memory for training  | 8Gi shared              | 16Gi dedicated |
| Independent retries  | No                      | Yes            |
| Use case             | Simple / cost-conscious | Production     |

---

## Variables Reference

| Variable                       | Default            | Description                               |
| ------------------------------ | ------------------ | ----------------------------------------- |
| `project_id`                   | _(required)_       | GCP project ID                            |
| `region`                       | `us-central1`      | GCP region                                |
| `bucket_name`                  | _(required)_       | Globally unique GCS bucket name           |
| `container_image`              | _(required)_       | Artifact Registry image URI               |
| `split_jobs_enabled`           | `false`            | Enable two-job split mode                 |
| `scheduler_cron`               | `20 22 * * 1-5`    | Trigger schedule (22:20 NY, weekdays)     |
| `price_refresh_days`           | `7`                | Days of price history to refresh daily    |
| `price_backfill_days`          | `365`              | Bootstrap backfill range (first run only) |
| `pipeline_lookback_days`       | `365`              | Training window in calendar days          |
| `pipeline_horizons`            | `[5, 10]`          | Forward return horizons for options model |
| `pipeline_categories`          | `["long_premium"]` | Options strategy categories               |
| `pipeline_topk`                | `3`                | Top-K recommendations to output           |
| `pipeline_min_train_days`      | `80`               | Minimum trading days per fold             |
| `pipeline_test_days`           | `20`               | Test window per fold                      |
| `pipeline_step_days`           | `20`               | Walk-forward step size                    |
| `pipeline_lgbm_jobs`           | `1`                | LightGBM threads (keep 1 for memory)      |
| `pipeline_run_max_minutes`     | `45`               | Soft timeout for pipeline subprocess      |
| `job_timeout_seconds`          | `7200`             | Cloud Run Job hard timeout (2h)           |
| `job_cpu` / `job_memory`       | `2` / `8Gi`        | Single-job container resources            |
| `pipeline_job_cpu` / `_memory` | `4` / `16Gi`       | Split pipeline job resources              |

---

## Deployment Steps

### 1. Build and push the Docker image

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t us-central1-docker.pkg.dev/sylvain-488510/quantum/quantum-ml:latest -f Dockerfile.ml-job .
docker push us-central1-docker.pkg.dev/sylvain-488510/quantum/quantum-ml:latest
```

Or use Cloud Build (no local Docker required):

```powershell
.\scripts\deploy.ps1 -Target cloud-build -ProjectId sylvain-488510
```

### 2. Configure variables

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit: project_id, bucket_name, container_image
```

### 3. Deploy

```bash
 .\scripts\deploy.ps1 -Target tf-only -ProjectId sylvain-488510 -AutoApprove
```

### 4. Manual test run

```bash
# Single job mode
gcloud run jobs execute quantum-daily-ml --region us-central1 --project sylvain-488510 --wait

# Split mode (run in order)
gcloud run jobs execute quantum-daily-ml-refresh  --region us-central1 --project sylvain-488510 --wait
gcloud run jobs execute quantum-daily-ml-pipeline --region us-central1 --project sylvain-488510 --wait
```

### 5. Read results from dashboard

```bash
export ML_RESULTS_GCS_URI=gs://quantum-ml-bucket/ml_output
cd dashboard && uv run streamlit run dashboard_app.py
```

Or set it permanently in `.env` at the project root (already configured):

```text
ML_RESULTS_GCS_URI=gs://quantum-ml-bucket/ml_output
```

---

## Terraform Outputs

| Output                            | Description                                             |
| --------------------------------- | ------------------------------------------------------- |
| `runtime_service_account_email`   | SA email used by containers                             |
| `scheduler_service_account_email` | SA email used by Cloud Scheduler                        |
| `data_bucket_name`                | GCS bucket for all ML data                              |
| `cloud_run_job_name`              | Single-mode job name (null in split mode)               |
| `refresh_cloud_run_job_name`      | Refresh job name (null in single mode)                  |
| `pipeline_cloud_run_job_name`     | Pipeline job name (null in single mode)                 |
| `dashboard_results_gcs_uri`       | `gs://<bucket>/ml_output` — set as `ML_RESULTS_GCS_URI` |
