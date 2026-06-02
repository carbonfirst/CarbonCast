# Real-Time CarbonCast Pipeline v1

This backend supports a real-time pipeline for hourly actual energy data
(US via EIA, EU via ENTSO-E), RDA weather forecasts, weekly model retraining
(CarbonCast + LiteCast) orchestration, and 168-hour future forecasts.

The platform is organized around three UI views that map directly onto the
data it stores:

- **Historical** (`mode=past`): actual observed values plus the forecast that
  had been made for that past day, so users can judge forecast accuracy.
- **Real-Time** (`mode=now`): the most recent observed values.
- **Future** (`mode=future`): the latest 168-hour forecast batch.

## Runtime Services

- PostgreSQL is the supported runtime database.
- Redis is used for Celery broker/cache locks.
- Django serves the existing public `/v1` API endpoints.
- Celery worker runs ingestion and retraining tasks.
- Celery Beat runs recurring schedules stored in the database.
- The RDA automation tool remains separate; Django reads its download/control
  directories through environment variables.

## Setup

Install from the backend canonical requirements file:

```bash
pip install -r UCSC_CarbonCast_API/CarbonCast/requirements.txt
```

The nested `src/CarbonCastAPI/requirements.txt` delegates to that file.

Create `src/CarbonCastAPI/.env` or export environment variables directly.
Exported values override `.env`.

Required runtime variables:

- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `REDIS_URL`
- `REDIS_CACHE_URL`
- `EIA_API_KEY` (US ingestion)
- `ENTSOE_API_KEY` (EU ingestion; optional — ENTSO-E ingestion is skipped if unset)
- `RDA_DOWNLOAD_DIR`
- `RDA_CONTROL_FILES_DIR`

Optional pipeline variables:

- `PIPELINE_REGIONS`: comma-separated region allowlist.
- `PIPELINE_DEFAULT_MODEL`: force `carboncast` or `litecast` for all regions.
- `PIPELINE_MODEL_<REGION>`: force a specific model for one region (e.g.
  `PIPELINE_MODEL_CISO=litecast`).
- `CARBONCAST_ARTIFACT_DIR`: where retraining exports artifacts.
- `CARBONCAST_RUN_ML=true`: enable calls into existing CarbonCast scripts.
- `CARBONCAST_CONFIG_FILE`: existing CarbonCast config used when ML execution is enabled.
- `CARBONCAST_REAL_TIME_DIR`, `CARBONCAST_REAL_TIME_WEATHER_DIR`
- `CARBONCAST_FORECAST_HORIZON_HOURS`: defaults to `168`.

## Database

Run migrations from `src/CarbonCastAPI`:

```bash
python manage.py migrate
```

Migrations add:

- `WeatherForecast`
- `ModelRun`
- `Forecast96.forecast_horizon`, `Forecast96.batch_id`
- `EmissionActual.metric_type` and `Forecast96.metric_type` (default `carbon`),
  so demand and electricity-price data can share the same tables and endpoints
  in future without a redesign.

## Daily Ingestion

Energy actuals are accumulated daily so the Historical and Real-Time views stay
current and so retraining always has fresh inputs:

- `fetch_daily_energy_data` (EIA, US) — `06:00 UTC` daily.
- `fetch_daily_entsoe_data` (ENTSO-E, EU) — `06:30 UTC` daily.

Both upsert hourly rows into `EmissionActual` keyed by `(region, ts, metric_type)`.

Backfill existing `real_time/` CSVs:

```bash
python manage.py import_csvs --path /path/to/real_time
```

## Weather Ingestion And Fallback

Ingest RDA automation downloads:

```bash
python manage.py ingest_weather --path "$RDA_DOWNLOAD_DIR"
```

The command parses GRIB, NetCDF, and CSV files and writes normalized hourly
`WeatherForecast` rows tagged with `source='rda'`.

If fresh RDA weather is missing, the weekly fallback task copies matching rows
from the same week 12 months earlier and tags them `source='historical_fallback'`.
This keeps weekly retraining functional when the RDAMS API is unstable.

## Schedules

Register or update Celery Beat rows idempotently:

```bash
python manage.py setup_pipeline_schedules
```

Created schedules:

- Daily EIA (US) ingestion: `06:00 UTC`
- Daily ENTSO-E (EU) ingestion: `06:30 UTC`
- RDA weather ingestion: every 2 hours
- Weekly CTL generation: Monday `03:00 UTC`
- Weekly weather fallback check: Monday `05:00 UTC`
- Weekly retraining: Monday `06:00 UTC`

Weather ingestion and retraining use Redis-backed locks. Overlapping runs are
skipped cleanly.

## Retraining And Forecasts

`CarbonCastRESTAPI.tasks.retrain_models` calls
`services.retraining_service.run_retraining`. Retraining runs weekly because
forecasters predict up to 168 hours (one week) ahead.

For each region with actuals, the service:

1. Loads up to 180 days of `EmissionActual`.
2. Selects a model runner via `services.model_runners.select_runner_for_region`:
   - **CarbonCast** — 180-day lookback, used when >= 60 days of history exist.
   - **LiteCast** — 14-day lookback, used for sparse/new regions.
   The choice can be overridden with `PIPELINE_DEFAULT_MODEL` /
   `PIPELINE_MODEL_<REGION>`.
3. Pulls the latest 168-hour `WeatherForecast` window (live RDA or 12-month
   fallback) and aligns it to each forecast hour.
4. Optionally calls existing `firstTierForecasts` / `secondTierForecasts`
   real-time functions when `CARBONCAST_RUN_ML=true`.
5. Writes a complete `Forecast96` batch for `lifecycle`, `direct`, and `energy`
   with `forecast_horizon=168` and a shared `batch_id`.
6. Records model name, status, weather source, row counts, artifact paths, and
   failures in `ModelRun`.

The runner output is the source of truth for the forecast batch; it never
deletes prior forecasts, so service continuity is preserved if weather or legacy
ML artifacts are unavailable.

## API/UI Contract

Existing endpoint names remain stable.

- Current forecast endpoints read the latest DB-backed 168-hour batch first.
- Historical/future forecast endpoints read `Forecast96` by requested date.
- CSV fallback remains only for legacy data gaps.
- `/v1/DataFreshness` returns latest actual/weather/forecast timestamps plus
  `actuals_stale`, `weather_stale`, `forecast_missing_or_short`, and the
  per-region `weather_source` / `weather_is_fallback` flags so the UI can show
  when a forecast is backed by 12-month fallback weather.
- `/v1/RetrainingStatus` reports the most recent retraining run per region:
  model used (CarbonCast/LiteCast), weather source, status, timing, and batch.
- The React timeline allows future dates up to 7 days ahead and labels the three
  views Historical / Real-Time / Future.
