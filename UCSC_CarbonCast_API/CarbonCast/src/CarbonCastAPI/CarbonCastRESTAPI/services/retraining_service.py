"""
Weekly CarbonCast retraining orchestration.

This service prepares the database-backed inputs expected by the existing
CarbonCast scripts, optionally invokes those scripts when the runtime is
configured for full ML execution, and persists a complete 168-hour forecast
batch to Forecast96. The DB write path is deliberately independent of the ML
call so stale or missing script artifacts do not erase the last usable forecast.
"""

import csv
import logging
import os
import tempfile
import uuid
from datetime import timedelta, timezone
from pathlib import Path

from django.utils import timezone as tz

logger = logging.getLogger(__name__)

FORECAST_HORIZON_HOURS = int(os.environ.get("CARBONCAST_FORECAST_HORIZON_HOURS", "168"))
TRAINING_WINDOW_DAYS = int(os.environ.get("CARBONCAST_TRAINING_WINDOW_DAYS", "180"))
RECENT_AVERAGE_DAYS = int(os.environ.get("CARBONCAST_BASELINE_LOOKBACK_DAYS", "28"))
ENERGY_SOURCES = ("coal", "nat_gas", "nuclear", "oil", "hydro", "solar", "wind", "other")


def run_retraining() -> dict:
    """Execute the weekly pipeline for all configured regions with actuals."""
    from CarbonCastRESTAPI.models import EmissionActual, ModelRun

    configured_regions = {
        r.strip().upper()
        for r in os.environ.get("PIPELINE_REGIONS", "").split(",")
        if r.strip()
    }
    regions = list(
        EmissionActual.objects.values_list('region', flat=True).distinct().order_by('region')
    )
    if configured_regions:
        regions = [r for r in regions if r in configured_regions]

    results = {
        'regions_processed': 0,
        'regions_failed': 0,
        'forecast_horizon': FORECAST_HORIZON_HOURS,
    }

    for region in regions:
        run = ModelRun.objects.create(
            region=region,
            model_name='pending',
            status='running',
        )
        try:
            metrics = _retrain_region(region, run)
            run.status = 'completed'
            run.metrics = metrics
            run.run_completed = tz.now()
            run.save(update_fields=['status', 'metrics', 'run_completed'])
            results['regions_processed'] += 1
        except Exception as exc:
            logger.exception("Retraining failed for %s", region)
            run.status = 'failed'
            run.metrics = {'error': str(exc)}
            run.run_completed = tz.now()
            run.save(update_fields=['status', 'metrics', 'run_completed'])
            results['regions_failed'] += 1

    return results


def _retrain_region(region: str, model_run):
    """Prepare artifacts, pick a runner, invoke configured ML, write one batch."""
    from CarbonCastRESTAPI.models import EmissionActual
    from CarbonCastRESTAPI.services.model_runners import select_runner_for_region

    # Always pull the longest configured window — individual runners trim it down
    # to whatever lookback they need (CarbonCast: 180d, LiteCast: 14d).
    training_start = tz.now() - timedelta(days=TRAINING_WINDOW_DAYS)
    emissions = list(
        EmissionActual.objects.filter(region=region, ts__gte=training_start).order_by('ts')
    )
    if not emissions:
        raise ValueError(f"No EmissionActual rows available for {region}")

    runner = select_runner_for_region(region, emissions)
    model_run.model_name = runner.name
    model_run.save(update_fields=['model_name'])

    batch_id = uuid.uuid4().hex[:12]
    forecast_start = _next_utc_hour()
    artifact_dir = _artifact_dir(batch_id, region)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    weather_source, weather_rows = _latest_weather_rows(region, forecast_start)
    emissions_csv = _export_emissions_csv(artifact_dir, emissions)
    weather_csv = _export_weather_csv(artifact_dir, weather_rows)

    model_run.weather_source = weather_source
    model_run.config = {
        'region': region,
        'batch_id': batch_id,
        'forecast_horizon': FORECAST_HORIZON_HOURS,
        'training_window_days': TRAINING_WINDOW_DAYS,
        'model_name': runner.name,
        'model_lookback_days': runner.lookback_days,
        'emissions_csv': str(emissions_csv),
        'weather_csv': str(weather_csv) if weather_csv else None,
        'run_ml': _truthy(os.environ.get("CARBONCAST_RUN_ML")),
    }
    model_run.model_artifact_path = str(artifact_dir)
    model_run.save(update_fields=['weather_source', 'config', 'model_artifact_path'])

    ml_result = _try_run_existing_carboncast(region, forecast_start, artifact_dir)
    forecast_counts = _persist_baseline_forecast(
        region=region,
        emissions=emissions,
        batch_id=batch_id,
        forecast_start=forecast_start,
        weather_source=weather_source,
        artifact_dir=artifact_dir,
        runner=runner,
        weather_rows=weather_rows,
    )

    return {
        'method': f'{runner.name}_ml_plus_db_baseline' if ml_result.get('attempted') else f'{runner.name}_db_baseline',
        'model_name': runner.name,
        'model_lookback_days': runner.lookback_days,
        'batch_id': batch_id,
        'weather_source': weather_source,
        'weather_rows': len(weather_rows),
        'emission_rows': len(emissions),
        'forecast_rows': forecast_counts,
        'ml_result': ml_result,
    }


def _next_utc_hour():
    now = tz.now().astimezone(timezone.utc)
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def _artifact_dir(batch_id, region):
    root = Path(os.environ.get("CARBONCAST_ARTIFACT_DIR", tempfile.gettempdir()))
    return root / "carboncast_pipeline" / batch_id / region


def _latest_weather_rows(region, forecast_start):
    from CarbonCastRESTAPI.models import WeatherForecast

    latest = (
        WeatherForecast.objects.filter(region=region)
        .order_by('-forecast_created')
        .values('forecast_created', 'source')
        .first()
    )
    if not latest:
        return 'none', []

    rows = list(
        WeatherForecast.objects.filter(
            region=region,
            forecast_created=latest['forecast_created'],
            forecast_target__gte=forecast_start,
            forecast_target__lt=forecast_start + timedelta(hours=FORECAST_HORIZON_HOURS),
        ).order_by('forecast_target', 'variable')
    )
    return latest['source'], rows


def _export_emissions_csv(artifact_dir, emissions):
    path = artifact_dir / "emissions_training.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "UTC time",
            "creation_time (UTC)",
            "version",
            "region_code",
            "carbon_intensity_avg_lifecycle",
            "carbon_intensity_avg_direct",
            *ENERGY_SOURCES,
        ])
        for row in emissions:
            data = row.data or {}
            writer.writerow([
                row.ts.isoformat(),
                data.get("creation_time (UTC)") or data.get("creation_time") or "",
                data.get("version") or "",
                row.region,
                row.lifecycle if row.lifecycle is not None else "",
                row.direct if row.direct is not None else "",
                *[data.get(source, "") for source in ENERGY_SOURCES],
            ])
    return path


def _export_weather_csv(artifact_dir, weather_rows):
    if not weather_rows:
        return None

    path = artifact_dir / "weather_forecast_168h.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["forecast_created", "forecast_target", "region_code", "variable", "value", "source"])
        for row in weather_rows:
            writer.writerow([
                row.forecast_created.isoformat(),
                row.forecast_target.isoformat(),
                row.region,
                row.variable,
                row.value if row.value is not None else "",
                row.source,
            ])
    return path


def _try_run_existing_carboncast(region, forecast_start, artifact_dir):
    """
    Invoke existing real-time CarbonCast functions when explicitly configured.

    The historical scripts require saved models/config/min-max artifacts that
    differ by deployment, so v1 leaves this disabled unless CARBONCAST_RUN_ML is
    true and CARBONCAST_CONFIG_FILE points to a runtime config.
    """
    if not _truthy(os.environ.get("CARBONCAST_RUN_ML")):
        return {'attempted': False, 'status': 'disabled'}

    config_file = os.environ.get("CARBONCAST_CONFIG_FILE")
    if not config_file:
        return {'attempted': True, 'status': 'skipped_missing_config'}

    try:
        from firstTierForecasts import runFirstTierInRealTime
        from secondTierForecasts import runSecondTierInRealTime

        creation_time = tz.now().astimezone(timezone.utc).isoformat()
        start_date = forecast_start.date().isoformat()
        electricity_date = (forecast_start - timedelta(days=1)).date().isoformat()
        real_time_dir = os.environ.get("CARBONCAST_REAL_TIME_DIR", str(artifact_dir))
        weather_dir = os.environ.get("CARBONCAST_REAL_TIME_WEATHER_DIR", str(artifact_dir))
        version = os.environ.get("CARBONCAST_MODEL_VERSION", "db-pipeline-v1")

        first_tier_files = runFirstTierInRealTime(
            config_file,
            [region],
            start_date,
            electricity_date,
            None,
            real_time_dir,
            weather_dir,
            creation_time,
            version,
        )
        for cef_type in ("direct", "lifecycle"):
            runSecondTierInRealTime(
                config_file,
                [region],
                cef_type,
                start_date,
                electricity_date,
                real_time_dir,
                weather_dir,
                first_tier_files[0] if first_tier_files else "",
                creation_time,
                version,
            )
        return {'attempted': True, 'status': 'completed', 'first_tier_files': first_tier_files}
    except Exception as exc:
        logger.exception("Configured CarbonCast ML execution failed for %s", region)
        return {'attempted': True, 'status': 'failed', 'error': str(exc)}


def _persist_baseline_forecast(region, emissions, batch_id, forecast_start, weather_source, artifact_dir, runner=None, weather_rows=None):
    """
    Run the selected model runner (CarbonCast/LiteCast) to produce a full
    forecast batch and upsert it into Forecast96. The runner output is the
    single source of truth; weather rows are passed through so weather-aware
    runners can align variables to each forecast hour.
    """
    from CarbonCastRESTAPI.models import Forecast96
    from CarbonCastRESTAPI.services.model_runners import CarbonCastRunner

    if runner is None:
        runner = CarbonCastRunner()
    weather_rows = weather_rows or []

    creation_time = tz.now().astimezone(timezone.utc).isoformat()
    rows_written = {'lifecycle': 0, 'direct': 0, 'energy': 0}

    forecast_rows = runner.run(
        region=region,
        emissions=emissions,
        weather_rows=weather_rows,
        forecast_start=forecast_start,
        horizon=FORECAST_HORIZON_HOURS,
    )

    output_path = artifact_dir / "db_baseline_forecasts.csv"
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["UTC time", "forecast_type", "value", "batch_id", "model"])

        for fr in forecast_rows:
            data = {
                **fr.data,
                'creation_time (UTC)': creation_time,
                'batch_id': batch_id,
                'forecast_horizon': FORECAST_HORIZON_HOURS,
                'weather_source': weather_source,
                'model_name': runner.name,
            }
            Forecast96.objects.update_or_create(
                region=region,
                ts=fr.ts,
                forecast_type=fr.forecast_type,
                defaults={
                    'value': fr.value,
                    'forecast_horizon': FORECAST_HORIZON_HOURS,
                    'batch_id': batch_id,
                    'data': data,
                },
            )
            if fr.forecast_type in rows_written:
                rows_written[fr.forecast_type] += 1
            writer.writerow([fr.ts.isoformat(), fr.forecast_type, fr.value, batch_id, runner.name])

    return rows_written


def _average(values):
    numeric = [_coerce_float(value) for value in values]
    numeric = [value for value in numeric if value is not None]
    if not numeric:
        return 0.0
    return sum(numeric) / len(numeric)


def _average_source_mix(rows):
    averages = {}
    for source in ENERGY_SOURCES:
        values = []
        for row in rows:
            data = row.data or {}
            values.append(data.get(source))
        averages[source] = _average(values)
    return averages


def _coerce_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
