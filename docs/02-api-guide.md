# Backend Guide — UCSC_CarbonCast_API

> This is the brain of the operation. It's a Django REST API that serves carbon
> and energy data to the frontend, plus the machine-learning pipeline that
> produces the forecasts and a Celery-based system that keeps everything fresh.

Code lives in `UCSC_CarbonCast_API/CarbonCast/`. The deployed web service is the
Django app under `src/CarbonCastAPI/`.

---

## What it does, in plain English

CarbonCast (this is the v3 lineage from UMass Amherst) forecasts the **average
carbon intensity of the electric grid** up to 96 hours (and architecturally up to
168h) ahead for dozens of regions. It does this with a **two-tier ML approach**:

1. **First tier** — forecast how much electricity each *source* (solar, wind, gas,
   coal, nuclear, …) will produce.
2. **Second tier** — feed those source forecasts (plus weather) into a model that
   forecasts the resulting carbon intensity.

The trained models are saved per-region in `saved_first_tier_models/` and
`saved_second_tier_models/`. The Django API exposes the latest actuals and these
forecasts over HTTP. When the database has no row for a request, the API gracefully
**falls back to legacy CSV files** under `real_time/<REGION>/`.

---

## Two things live in this repo — don't confuse them

| Thing | Where | Role |
|-------|-------|------|
| **Original research pipeline** | `src/*.py` (standalone scripts) | The original training/forecasting scripts the research was built on. Reference + still used for model training. |
| **The Django REST API** | `src/CarbonCastAPI/` | What's actually deployed and what the UI talks to. This is where you'll spend most of your time. |

---

## Tech stack

| Concern | Choice |
|---------|--------|
| Web framework | Django 4.2.5 + Django REST Framework 3.14 |
| API style | Class-based `APIView`s, URL path versioning (`v1`/`v2`) |
| Database | PostgreSQL (runtime). SQLite was used during migration work — see `docs/sqlite_migration.md`. |
| Background jobs | Celery (+ Redis broker) for ingestion + retraining |
| Scheduling | Celery beat schedules, bootstrapped by a management command |
| ML | TensorFlow / Keras saved models |
| API docs | `drf_yasg` (Swagger / OpenAPI) |
| Container | `docker-compose.yml` (web, db, redis, celery worker/beat) |

---

## Folder structure (the important parts)

```
UCSC_CarbonCast_API/CarbonCast/
├─ README.md
├─ requirements.txt
├─ docker-compose.yml          # web + postgres + redis + celery
├─ installDependencies.sh
├─ setup.py
├─ docs/
│   ├─ API_instructions.md      # how to call the API
│   ├─ realtime_pipeline_v1.md  # the ingestion/forecast/retraining pipeline
│   └─ sqlite_migration.md      # notes from the DB migration work
├─ saved_first_tier_models/     # per-region source-production models
├─ saved_second_tier_models/    # per-region carbon-intensity models
├─ CI_forecast_data/<REGION>/   # forecast CSVs (fallback / reference data)
├─ real_time/<REGION>/          # latest actuals CSVs (fallback data)
├─ data_old (v2.1)/  data_old(v3.1)/   # historical datasets (large, archival)
└─ src/
    ├─ *.py                      # original research pipeline scripts
    └─ CarbonCastAPI/            # ← THE DJANGO PROJECT
        ├─ manage.py
        ├─ CarbonCastAPI/        # Django settings/urls/wsgi/celery config
        └─ CarbonCastRESTAPI/    # ← THE APP (models, views, urls, tasks, services)
```

### Inside the Django app (`src/CarbonCastAPI/CarbonCastRESTAPI/`)

| File | What it does |
|------|--------------|
| `models.py` (~160 lines) | The database schema (see below). |
| `views/` (package) | **All API endpoints live here.** Originally one ~1,900-line `views.py`, now split into focused modules — `carbon_intensity.py`, `energy_sources.py`, `forecasts.py`, `regions.py`, `retraining.py`, `auth.py` — sharing a `_base.py` header. `views/__init__.py` re-exports every view so `urls.py` is unchanged. |
| `urls.py` | Maps URL paths to the views. |
| `serializers.py` | DRF serializers (user serialization, etc.). |
| `helper.py` | The CSV-fallback readers + metadata helpers used by the views. |
| `consts.py` | Constants: version, region code lists, auth/permission class config. |
| `tasks.py` | Celery tasks (daily ingestion, weather ingestion, weekly retraining). |
| `services/retraining_service.py` | The logic behind weekly model retraining. |
| `management/commands/setup_pipeline_schedules.py` | One-shot command to register the Celery beat schedules. |

---

## The data models (what's in the database)

All defined in `models.py`:

| Model | Purpose | Key fields |
|-------|---------|------------|
| `UserModel` | Custom user (extends `AbstractUser`), with optional TOTP/OTP 2FA. | `username`, `email`, `otp_*`, `throttle_limit` |
| `UserThrottleLimit` | Per-user rate-limit setting. | `throttle_limit` |
| `EmissionActual` | Observed actuals per region+hour. Carbon today; demand/price reserved for the future. | `region`, `ts`, `metric_type`, `lifecycle`, `direct`, `data` (JSON) |
| `Forecast96` | Forecast rows (up to 168h). | `region`, `ts`, `value`, `forecast_type`, `forecast_horizon`, `batch_id` |
| `Weather` | Runtime weather rows. | `region`, `ts`, `temp`, `data` |
| `WeatherForecast` | Processed weather forecasts (from the RDA automation tool / fallbacks). | `region`, `forecast_created`, `forecast_target`, `variable`, `source` |
| `ModelRun` | Tracks each weekly retraining run. | `region`, `model_name`, `status`, `metrics`, `model_artifact_path` |

Note the `metric_type` design choice: carbon is the only metric ingested today,
but `demand` and `price` are baked into the schema so the platform can grow
without a redesign.

---

## API endpoints

All endpoints are versioned and mounted under the API prefix (e.g.
`/carboncastapi/v1/...`). Most accept a `region_code` query param; `region_code=all`
returns every supported US region. From `urls.py`:

| Method | Path | What it returns |
|--------|------|-----------------|
| GET | `CarbonIntensity` | Latest actual carbon intensity (lifecycle + direct) for a region. |
| GET | `EnergySources` | Latest energy-source breakdown (the mix) for a region. |
| GET | `CarbonIntensityHistory` | Historical carbon-intensity actuals. |
| GET | `EnergySourcesHistory` | Historical energy-source breakdown. |
| GET | `CarbonIntensityForecasts` | Carbon-intensity forecast (the headline feature). |
| GET | `CarbonIntensityForecastsHistory` | Past forecasts (for evaluation/backtesting). |
| GET | `EnergySourcesForecastsHistory` | Past energy-source forecasts. |
| GET | `SupportedRegions` | List of supported region codes. |
| GET | `DataFreshness` | How fresh the data is per region (drives the UI's freshness indicator). |
| GET | `RetrainingStatus` | Status of model retraining runs. |
| —   | `UserAuthenticationEnforced` | Auth-gated probe endpoint. |
| POST | `SignUp` / `SignIn` / `Logout` | Auth flows. |
| POST | `VerifyOTP` | TOTP/2FA verification. |

> Every response includes a `carbon_cast_version` field. The data-serving
> endpoints try the cache → then PostgreSQL → then CSV fallback, and attach
> metadata describing whether a fallback was used (the UI reads this).

For request/response examples, see `docs/API_instructions.md` and the live Swagger
UI when the server is running.

---

## The real-time pipeline (ingestion → forecast → retrain)

Documented in detail in `docs/realtime_pipeline_v1.md`. The short version, driven
by Celery (`tasks.py`) on schedules registered by `setup_pipeline_schedules.py`:

```
  Daily:   ingest latest grid actuals  ──► EmissionActual / EnergySources
  Daily:   ingest weather              ──► Weather / WeatherForecast
           (weather files come from the RDA automation tool, project #3)
  Daily:   run two-tier ML forecast    ──► Forecast96
  Weekly:  retrain models (per region) ──► saved_*_tier_models/ + ModelRun row
```

`services/retraining_service.py` owns the retraining logic and records a
`ModelRun` for each execution (status, metrics, artifact path) so you can see what
happened and when.

---

## Running it

### Docker (recommended — gets you the full stack)
```bash
cd UCSC_CarbonCast_API/CarbonCast
docker compose up --build
```
This brings up the Django web service, PostgreSQL, Redis, and the Celery
worker/beat together.

### Plain Django (for quick API work)
```bash
cd UCSC_CarbonCast_API/CarbonCast
pip install -r requirements.txt        # heavy: includes TensorFlow
cd src/CarbonCastAPI
python manage.py migrate
python manage.py runserver
# To register the scheduled jobs (once):
python manage.py setup_pipeline_schedules
```

You'll need a PostgreSQL database reachable per the settings, plus Redis if you
want Celery to run.

---

## Gotchas & honest notes

- **`views.py` was ~1,900 lines — now split into a `views/` package.** ✅ Done:
  it's been carved into focused modules (`carbon_intensity`, `energy_sources`,
  `forecasts`, `regions`, `retraining`, `auth`) sharing a `_base.py`, with
  `__init__.py` re-exporting everything so imports are unchanged. Verified with
  `python manage.py check`.
- **CSV fallback is load-bearing.** Don't delete `real_time/` or `CI_forecast_data/`
  assuming the DB has everything — endpoints rely on them when rows are missing.
- **There are still stray `print()` statements** inside the `get` handlers (the
  import-time one is gone). They're noisy; converting them to proper logging is a
  safe next win — see the reorganization doc.
- **Rate limiting is currently disabled** (`check_throttle_limit` always returns
  `True`). The throttle models/fields exist but aren't enforced. Know this before
  you debug "why isn't throttling working."
- **TensorFlow makes the environment heavy.** Installs are large and slow; Docker
  saves you pain.
- **Two databases appear in the history** (SQLite during migration, PostgreSQL in
  production). `docs/sqlite_migration.md` explains the transition.
