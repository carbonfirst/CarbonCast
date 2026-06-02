---
name: Real-Time CarbonCast Service
overview: Phased plan to harden the existing CarbonCast stack (Django API, React UI, RDA automation tool) into an automated real-time service. Phase 1 fixes prerequisites and gets PostgreSQL + Celery running. Phase 2 wires daily EIA ingestion and the RDA weather bridge. Phase 3 adds the weekly retraining loop. No new product features.
todos:
  - id: p1-fix-migration-0003
    content: Replace SQLite-specific RunSQL (strftime) in migrations/0003 with Postgres-compatible index expressions before attempting any PostgreSQL migrate
    status: completed
  - id: p1-pin-requirements
    content: Pin all deps, remove duplicate django-cors-headers, upgrade entsoe-py 0.5.10->>=0.7.11, add psycopg[binary]>=3.1.8, python-dateutil, celery, redis, django-celery-beat, django-redis, django-celery-results. Separate venvs.
    status: completed
  - id: p1-secrets-to-env
    content: Move SECRET_KEY, EIA_API_KEY (eiaParser.py:10), REQUIRES_AUTH, DEBUG, DB creds to env vars. Create .env.example. Set DEBUG=False, randomize SECRET_KEY.
    status: completed
  - id: p1-fix-settings-rest-framework
    content: Remove the duplicate REST_FRAMEWORK dict in settings.py (lines 120-124 silently overwrite lines 87-95). Merge into one block.
    status: completed
  - id: p1-postgres-switch
    content: Export SQLite with dumpdata. Switch DATABASES to postgresql. Run migrate (safe after 0003 fix). Import with loaddata. Verify all /v1/* endpoints return identical responses.
    status: completed
  - id: p1-celery-skeleton
    content: Create CarbonCastAPI/celery.py, update __init__.py, add django-celery-beat to INSTALLED_APPS, add CELERY_* to settings.py, create empty tasks.py. Verify heartbeat task fires.
    status: completed
  - id: p1-fix-api-base-url
    content: "Unify frontend API_BASE: make cache.ts read VITE_API_BASE_URL (same as useEnergyData.ts) instead of deriving from window.location.hostname. Remove Docker 172.17.0.1 fallback."
    status: completed
  - id: p2-eia-daily-task
    content: Create services/eia_service.py from eiaParser.py logic. Celery task fetch_daily_energy_data writes to EmissionActual via update_or_create. Idempotent on (region, ts).
    status: completed
  - id: p2-add-new-models
    content: Add WeatherForecast and ModelRun models only. Migrate. Do NOT add EnergyDemand/ElectricityPrice yet -- no data source for them.
    status: completed
  - id: p2-rda-weather-bridge
    content: "Create management command ingest_weather.py: scan RDA downloaded_files/, parse weather grids, write to WeatherForecast. Track processed files. Celery task runs it every 2h."
    status: completed
  - id: p2-data-freshness-endpoint
    content: Add GET /v1/DataFreshness endpoint returning MAX(ts) per data type per region. Lets frontend and health checks verify pipeline liveness.
    status: completed
  - id: p3-weather-fallback
    content: "Create check_weather_freshness_and_fallback Celery task. If no fresh RDA data: try NOMADS, then 12-month historical from DB. Tag source in WeatherForecast.source."
    status: completed
  - id: p3-model-retraining-task
    content: "Create retrain_models Celery task: query DB, export temp CSVs, call runFirstTier/runSecondTier, store 168h forecasts, record ModelRun. Use Redis lock to prevent overlap."
    status: completed
  - id: p3-extend-forecast-168h
    content: "Add forecast_horizon and batch_id fields to Forecast96. Backward-compatible: existing data keeps horizon=96."
    status: completed
isProject: false
---

# Real-Time CarbonCast Service -- Phased Implementation Plan

## Technical Audit Summary

Before writing any new code, here is what the codebase audit found. Every item below is a prerequisite or risk that must be addressed; ignoring any of them will cause failures during integration.

### Blocking issues (will cause crashes or data loss)

**1. Migration 0003 is not portable to PostgreSQL.**
[migrations/0003_optimize_indexes.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastRESTAPI/migrations/0003_optimize_indexes.py) contains a `RunSQL` with `strftime('%H', ts)` and `date(ts)` -- these are SQLite-only functions. Running `python manage.py migrate` against PostgreSQL will raise `ProgrammingError`. Must be replaced with Postgres-compatible expressions (`EXTRACT(HOUR FROM ts)`, `ts::date`) before any migration attempt.

**2. `settings.py` has a duplicate `REST_FRAMEWORK` dict.** Lines 87-95 define versioning, `AllowAny`, and empty auth classes. Lines 120-124 redefine `REST_FRAMEWORK` with only throttle keys. The second dict silently overwrites the first. Any code that assumes the first config is active will hit unexpected permission behavior.

**3. `requirements.txt` has version conflicts with the automation tool.** The Django API pins `pandas==1.4.4` and `matplotlib==3.5.3`. The RDA automation tool requires `pandas>=1.5.0` and `matplotlib>=3.6.0`. These two projects must use separate virtualenvs.

**4. No GRIB/NetCDF parsing libraries exist in either project.** The RDA automation tool downloads raw binaries from NCAR (typically `.tar` containing `.grib2` or `.nc` files). Neither `requirements.txt` includes `cfgrib`, `netCDF4`, or `pygrib`. The weather bridge cannot function without adding one.

### Non-blocking but high-risk issues

**5. Hardcoded secrets in source.**

- `SECRET_KEY` in settings.py line 23 is the Django insecure default
- `EIA_API_KEY` in eiaParser.py line 10 is committed in plaintext
- `DEBUG = True` and `ALLOWED_HOSTS = ['*']` in settings.py

**6. Two different `API_BASE` strategies in the frontend.**

- `cache.ts` lines 49-55: derives URL from `window.location.protocol/hostname:8000`, with a `172.17.0.1:8000` Docker fallback
- `useEnergyData.ts` line 6: reads `import.meta.env.VITE_API_BASE_URL`
- In production (`.env.production` points to `carboncast.duckdns.org:8000`), the map and the side panel can hit different backends

**7. No Django `CACHES` config.** `views.py` uses `django.core.cache.cache` with 10-second TTLs, but settings.py defines no `CACHES` dict. This defaults to `LocMemCache` which is per-process and not shared across Celery workers or gunicorn forks.

**8. `helper.py` path resolution is fragile.** `Path(__file__).resolve().parent.parent.parent.parent` walks four levels up to reach `CarbonCast/`. Moving any file breaks CSV fallback silently.

**9. `import_csvs.py` uses `python-dateutil` but it is not in `requirements.txt`.** Robust date parsing silently degrades if `dateutil` is not installed.

**10. `django-cors-headers` is listed twice in `requirements.txt` (lines 17 and 23).**

**11. Django 4.2 LTS reaches end-of-life April 30, 2026.** Per the [Django release schedule](https://docs.djangoproject.com/en/4.2/releases/4.2), security support ends this month. Django 5.2 LTS (supported until April 2028) is the recommended upgrade target. This is not a Phase 1 blocker but must be planned -- running an unsupported framework in production is a security risk.

**12. `entsoe-py==0.5.10` in requirements.txt is outdated and will fail.** ENTSO-E changed their API endpoint in November 2025. The library fixed this in later versions; current release is v0.7.11 (March 2026). The pinned v0.5.10 will get connection errors. Must upgrade to `entsoe-py>=0.7.11`. Additionally, the library now supports an `ENTSOE_ENDPOINT_URL` environment variable for endpoint configuration.

**13. cfgrib requires the eccodes C library as a system dependency.** `pip install cfgrib` alone is not sufficient on all platforms. On macOS: `brew install eccodes`. On Linux: `apt-get install libeccodes-dev` or use conda. As of eccodes Python package 2.43.0+, pip wheels include binaries on major platforms, but this is not guaranteed for all build environments. Must be documented and verified before the weather bridge can function.

**14. EIA API v2 now returns data values as strings.** As of v2.1.6 (January 2024), the EIA standardized data values as strings in JSON responses. The existing `eiaParser.py` and the new `eia_service.py` must explicitly cast values with `float(value)` during parsing.

### Exact files affected per integration step


| Change                | Files that must be modified                                                                                                                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PostgreSQL switch     | `settings.py` (DATABASES), `migrations/0003` (RunSQL), `requirements.txt` (+psycopg)                                                                                                                                |
| Celery setup          | `settings.py` (CELERY_*, INSTALLED_APPS), new `CarbonCastAPI/celery.py`, `CarbonCastAPI/__init__.py` (currently empty), new `CarbonCastRESTAPI/tasks.py`, `requirements.txt` (+celery, +redis, +django-celery-beat) |
| Shared cache          | `settings.py` (CACHES), `requirements.txt` (+django-redis). No code changes -- `views.py` already uses `cache.get`/`cache.set`                                                                                      |
| EIA daily ingestion   | New `services/eia_service.py`, `tasks.py` (new task), `eiaParser.py` (extract logic, remove hardcoded key)                                                                                                          |
| Weather bridge        | New `management/commands/ingest_weather.py`, `models.py` (WeatherForecast, ModelRun), new migration, `tasks.py` (new task), `requirements.txt` (+cfgrib or +netCDF4)                                                |
| Frontend API_BASE fix | `cache.ts` (~line 49), `cache-optimized.ts` (same pattern)                                                                                                                                                          |


### Idempotency requirements

- `import_csvs.py` already uses `update_or_create` on `(region, ts)` -- safe to re-run
- EIA daily task must also use `update_or_create` on `(region, ts)` -- re-running for the same date is a no-op
- Weather bridge must track ingested files (`processed_files.json`) to avoid re-parsing large GRIB files. Must NOT delete source files -- the automation tool may reference them
- Model retraining is NOT idempotent (TF has non-deterministic init). Each run creates a new `ModelRun` record

### Rollback concerns

- **PostgreSQL migration is one-way in practice.** Back up `db.sqlite3` before switching
- **New Django models can be reversed** with `migrate CarbonCastRESTAPI 0004` as long as no data exists in new tables
- **Celery tasks are additive.** Removing a task + its PeriodicTask DB row is clean undo
- **The RDA automation tool is untouched.** The bridge is read-only against `downloaded_files/`. Worst case: stop the bridge task

### Concurrency risks

- **RDA automation tool singleton:** No PID lockfile. Two instances will corrupt `batch_automation_state.json`, double-submit requests, and overwrite downloads
- **Celery task overlap:** Long-running tasks (weather ingestion, retraining) need `task_acks_late=True` and a Redis lock to prevent overlapping executions
- **Separate venvs mandatory:** Django API (Python <=3.10, pandas 1.4.4, TF 2.9) and RDA tool (Python 3.8-3.11, pandas >=1.5, Flask) cannot share a virtualenv

---

## Phase 1: Harden the Foundation

**Goal:** Make the existing stack production-safe and ready for automation. No new features. When done, the app works exactly as before but on PostgreSQL with secrets externalized and Celery plumbing in place.

### Step 1.1: Pin dependencies and fix requirements.txt

**File:** [requirements.txt](UCSC_CarbonCast_API/CarbonCast/requirements.txt)

- Remove the duplicate `django-cors-headers` (line 23 repeats line 17)
- Pin all currently unpinned packages (`drf-yasg`)
- Upgrade `entsoe-py==0.5.10` to `entsoe-py>=0.7.11` (v0.5.10 will fail against the new ENTSO-E API endpoint that changed November 2025)
- Add: `psycopg[binary]>=3.1.8` (Django 4.2 requires psycopg 3.1.8+ for the psycopg3 backend; psycopg2 is being deprecated by Django), `python-dateutil>=2.8`, `celery>=5.3`, `redis>=5.0`, `django-celery-beat>=2.5`, `django-redis>=5.4`, `django-celery-results>=2.5`
- Note: Django 4.2 supports both `psycopg` (v3) and `psycopg2` via the same `django.db.backends.postgresql` engine. We use psycopg v3 since psycopg2 is flagged for future deprecation per Django docs

### Step 1.2: Externalize all secrets

**Files:** [settings.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastAPI/settings.py), [eiaParser.py](UCSC_CarbonCast_API/CarbonCast/src/eiaParser.py)

- `SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', get_random_secret_key())`
- `DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'`
- `ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')`
- `EIA_API_KEY = os.environ.get('EIA_API_KEY', '')` in eiaParser.py replacing the hardcoded key
- Create `.env.example` documenting every variable, including:
  - `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
  - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
  - `REDIS_URL`
  - `EIA_API_KEY`
  - `ENTSOE_API_TOKEN` (for future ENTSO-E integration)
  - `ENTSOE_ENDPOINT_URL` (entsoe-py 0.7.x supports this env var for the new API endpoint that changed November 2025)
  - `RDA_TOKEN`, `RDA_DOWNLOAD_DIR`, `RDA_CONTROL_FILES_DIR`

### Step 1.3: Fix duplicate REST_FRAMEWORK in settings.py

**File:** [settings.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastAPI/settings.py)

Merge lines 87-95 and 120-124 into a single `REST_FRAMEWORK = { ... }` dict containing both the auth/permission config and the throttle keys.

### Step 1.4: Fix migration 0003 for PostgreSQL

**File:** [migrations/0003_optimize_indexes.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastRESTAPI/migrations/0003_optimize_indexes.py)

Replace the `RunSQL` block with Postgres-compatible SQL:

```python
migrations.RunSQL(
    sql="""CREATE INDEX IF NOT EXISTS emission_region_date_hour_idx
           ON "CarbonCastRESTAPI_emissionactual"
           (region, (ts::date), EXTRACT(HOUR FROM ts));""",
    reverse_sql="DROP INDEX IF EXISTS emission_region_date_hour_idx;",
),
```

### Step 1.5: Switch to PostgreSQL

**File:** [settings.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastAPI/settings.py)

Procedure: (a) `python manage.py dumpdata --natural-foreign --natural-primary -o backup.json` on SQLite, (b) change `DATABASES` engine to `django.db.backends.postgresql` with env-var-driven config, (c) `python manage.py migrate`, (d) `python manage.py loaddata backup.json`, (e) compare API responses to a saved baseline.

### Step 1.6: Add Redis-backed cache

**File:** [settings.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastAPI/settings.py)

Per the [django-redis docs](https://github.com/jazzband/django-redis), the `OPTIONS.CLIENT_CLASS` is required:

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_CACHE_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
```

Use a separate env var `REDIS_CACHE_URL` (defaulting to DB index `/1`) to avoid collision with the Celery broker which uses `REDIS_URL` (DB index `/0`). If you only have one Redis instance, the DB index suffix (`/0` vs `/1`) keeps broker messages and cache data isolated. This makes `cache.get`/`cache.set` in `views.py` shared across processes with no code changes.

### Step 1.7: Wire Celery skeleton

Per the [Celery Django docs](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html), create `CarbonCastAPI/CarbonCastAPI/celery.py`:

```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CarbonCastAPI.settings')
app = Celery('CarbonCastAPI')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

The `namespace='CELERY'` means all Celery config keys in `settings.py` must use the `CELERY_` prefix. Update `CarbonCastAPI/CarbonCastAPI/__init__.py` (currently empty):

```python
from .celery import app as celery_app
__all__ = ('celery_app',)
```

Create `CarbonCastRESTAPI/tasks.py` with a single `heartbeat` shared_task.

Add to `settings.py`:

```python
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_RESULT_EXTENDED = True
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TIMEZONE = 'UTC'

INSTALLED_APPS += ['django_celery_beat', 'django_celery_results']
```

After adding, run `python manage.py migrate django_celery_beat` and `python manage.py migrate django_celery_results` to create the scheduler and results tables.

### Step 1.8: Unify frontend API_BASE

**Files:** [cache.ts](CarbonCastUI/web/src/hooks/cache.ts) (~line 49), [cache-optimized.ts](CarbonCastUI/web/src/hooks/cache-optimized.ts)

Replace the `window.location` derivation with `import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'` to match `useEnergyData.ts`. Per Vite 7 docs, `VITE`_-prefixed env vars are statically replaced at build time and exposed via `import.meta.env`. This is confirmed correct for the project's Vite 7.1.2 setup. Remove the `172.17.0.1` Docker fallback. Note: `.env.production` already sets `VITE_API_BASE_URL=http://carboncast.duckdns.org:8000`, so the production build will use that automatically.

### Phase 1 Acceptance Criteria

- `python manage.py migrate` succeeds against a fresh PostgreSQL database
- `python manage.py loaddata backup.json` restores all prior data
- Every `/v1/`* endpoint returns the same response shape as on SQLite
- `python manage.py shell -c "from django.conf import settings; print(settings.REST_FRAMEWORK)"` shows a single merged dict with both auth and throttle keys
- `celery -A CarbonCastAPI worker` starts without import errors
- `celery -A CarbonCastAPI beat` fires `heartbeat` at least once (visible in Django admin)
- `grep -r "CZdQs" .` returns 0 results (no plaintext API keys in tracked files)
- `npm run build` succeeds; `grep -r "window.location.hostname" dist/` returns 0
- RDA automation tool still works independently in its own venv

---

## Phase 2: Daily Energy Ingestion + Weather Bridge

**Goal:** Automate the two core data pipelines -- daily EIA energy data into the database, and the RDA automation tool's weather downloads ingested. When done, Historical and Real-Time modes show fresh data without manual scripts.

### Step 2.1: Create EIA ingestion service

**New file:** `CarbonCastRESTAPI/services/eia_service.py`

Extract from [eiaParser.py](UCSC_CarbonCast_API/CarbonCast/src/eiaParser.py): HTTP call logic (`getProductionDataBySourceTypeDataFromEIA`), parsing (`parseEIAProductionDataBySourceType`), cleaning (`cleanElectricityProductionDataFromEIA`). Read `EIA_API_KEY` from `os.environ`. Accept `date` parameter (default: yesterday). Return dicts ready for `EmissionActual.objects.update_or_create()`.

**Important (EIA API change):** Since EIA API v2.1.6 (January 2024), all data values are returned as **strings** in JSON responses. The parsing code must explicitly cast with `float(value)` and handle empty-string / null cases. Verify the existing `eiaParser.py` handles this correctly before extracting into the service module.

**New Celery task in `tasks.py`:** `fetch_daily_energy_data` with `autoretry_for=(RequestException,)`, `retry_backoff=60`, `max_retries=3`. Idempotent via `update_or_create` on `(region, ts)`.

### Step 2.2: Add WeatherForecast and ModelRun models

**File:** [models.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastRESTAPI/models.py)

Add only `WeatherForecast` (with `region`, `forecast_created`, `forecast_target`, `variable`, `value`, `source`, `data`) and `ModelRun` (with `region`, `model_name`, `run_started`, `run_completed`, `status`, `weather_source`, `config`, `metrics`, `model_artifact_path`). Do NOT add `EnergyDemand` or `ElectricityPrice` yet.

### Step 2.3: Build the RDA weather bridge

**New file:** `CarbonCastRESTAPI/management/commands/ingest_weather.py`

Same pattern as [import_csvs.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastRESTAPI/management/commands/import_csvs.py): `--path` arg pointing at automation tool's `downloaded_files/`. Walk `REGION/variable/` subdirectories. Parse with `cfgrib`/`xarray`. Write to `WeatherForecast` via `update_or_create` on `(region, forecast_created, forecast_target, variable)`. Maintain `processed_files.json` manifest. Do NOT delete source files.

**Dependency:** Add `cfgrib>=0.9` to requirements.txt. cfgrib also requires the **eccodes C library** as a system dependency -- on macOS: `brew install eccodes`, on Ubuntu/Debian: `apt-get install libeccodes-dev`. As of eccodes Python 2.43.0+, pip wheels may include binaries, but this is not guaranteed on all platforms. Run `python -m cfgrib selfcheck` after install to verify. If files turn out to be NetCDF rather than GRIB, use `netCDF4>=1.6` instead. Determine exact format by running the automation tool once for a single `.ctl` file and inspecting the downloaded file extensions.

**New Celery task:** `ingest_rda_weather_data`, runs every 2 hours.

### Step 2.4: Add `/v1/DataFreshness` endpoint

**Files:** [views.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastRESTAPI/views.py), [urls.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastRESTAPI/urls.py)

Query `MAX(ts)` from `EmissionActual` and `MAX(forecast_created)` from `WeatherForecast`, grouped by region. Returns JSON with last-updated timestamps per data type.

### Phase 2 Acceptance Criteria

- `fetch_daily_energy_data` runs for a past date and `EmissionActual.objects.filter(ts__date=that_date).count() > 0`
- Re-running for the same date produces identical row count (idempotent)
- `ingest_weather` pointed at a directory with real RDA downloads creates `WeatherForecast` rows
- Re-running on same directory creates no duplicates (checks `processed_files.json`)
- `/v1/DataFreshness` returns JSON with `last_emission_ts` and `last_weather_forecast_ts` per region
- Existing frontend Past/Now/Future modes still work (no regression)
- RDA automation tool still running independently; bridge is read-only against its downloads

---

## Phase 3: Weekly Retraining Loop

**Goal:** Close the loop -- weather + energy data flow into DB, weekly Celery task retrains models, fresh 168h forecasts appear in Future tab. System runs unattended week over week.

### Step 3.1: Weather freshness check with fallback

**New Celery task:** `check_weather_freshness_and_fallback`

1. Check `WeatherForecast.objects.filter(forecast_created__gte=one_week_ago).exists()`
2. If fresh data exists: log success, exit
3. If not: try NOMADS via [getRealTimeWeatherData.py](UCSC_CarbonCast_API/CarbonCast/src/weather/getRealTimeWeatherData.py) logic, store with `source='nomads'`
4. If NOMADS fails: copy 12-month-old same-week data with `source='historical_fallback'`
5. If nothing: log critical warning

Schedule: Monday 5 AM UTC.

### Step 3.2: Weekly `.ctl` file generation

**New Celery task:** `trigger_rda_control_files`

Read region bounding boxes from [automation_config.json](UCSC_OSRE_CC_automation_tool/CarbonCast/config/automation_config.json). For each region+variable, write `.ctl` file to `RDA_CONTROL_FILES_DIR` with dates covering the next 7 days. The automation tool auto-discovers new files.

Schedule: Monday 3 AM UTC.

### Step 3.3: Extend Forecast96 for 168h

**File:** [models.py](UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/CarbonCastRESTAPI/models.py)

Add `forecast_horizon = models.IntegerField(default=96)` and `batch_id = models.CharField(max_length=64, null=True, db_index=True)` to `Forecast96`. Backward-compatible: existing data keeps `forecast_horizon=96`.

### Step 3.4: Model retraining task

**New Celery task:** `retrain_models`

1. For each target region: query last 6 months of `EmissionActual`, latest `WeatherForecast` (note `source`)
2. Export to temp CSVs matching format expected by `firstTierForecasts.py`
3. Generate JSON config, call `runFirstTier(config)` and `runSecondTier(config, cefType, loadFromSavedModel=False)`
4. Save checkpoints to `saved_models/<region>/<date>/`
5. Run inference for 168h, write to `Forecast96` via `update_or_create` on `(region, ts, forecast_type)` with `forecast_horizon=168`
6. Create `ModelRun` record with status, metrics, weather source, artifact path
7. Clean up temp CSVs

Use `task_acks_late=True` and Redis distributed lock. Set `CELERY_TASK_TIME_LIMIT` to 4+ hours. Schedule: Monday 6 AM UTC.

### Phase 3 Acceptance Criteria

- `trigger_rda_control_files` generates `.ctl` files with correct date range in the target directory
- `check_weather_freshness_and_fallback` correctly falls back when WeatherForecast table is empty (test scenario)
- `retrain_models` produces a `ModelRun` record with `status='completed'` for at least one region
- `Forecast96.objects.filter(forecast_horizon=168).count() > 0` after retraining
- Running `retrain_models` twice does not corrupt data (new `ModelRun`, new `batch_id`)
- Full Monday sequence (3AM ctl gen -> 5AM freshness check -> 6AM retrain) completes end-to-end in a test environment without manual intervention

