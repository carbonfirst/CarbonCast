import logging
import os
from datetime import date, timedelta

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task
def heartbeat():
    """Verify Celery is alive and can reach the Django ORM."""
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return 'ok'


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def fetch_daily_energy_data(self, target_date=None):
    """Pull yesterday's energy data from EIA (US) and store in EmissionActual."""
    from CarbonCastRESTAPI.services.eia_service import fetch_and_store_eia_data

    if target_date is None:
        target_date = (date.today() - timedelta(days=1)).isoformat()

    logger.info("fetch_daily_energy_data (EIA) for %s", target_date)
    result = fetch_and_store_eia_data(target_date)
    logger.info("fetch_daily_energy_data (EIA) done: %s", result)
    return result


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def fetch_daily_entsoe_data(self, target_date=None):
    """Pull yesterday's energy data from ENTSO-E (EU) and store in EmissionActual."""
    from CarbonCastRESTAPI.services.entsoe_service import fetch_and_store_entsoe_data

    if target_date is None:
        target_date = (date.today() - timedelta(days=1)).isoformat()

    logger.info("fetch_daily_entsoe_data (ENTSO-E) for %s", target_date)
    result = fetch_and_store_entsoe_data(target_date)
    logger.info("fetch_daily_entsoe_data (ENTSO-E) done: %s", result)
    return result


@shared_task
def ingest_rda_weather_data():
    """Scan the RDA automation tool's download directory and ingest new files."""
    from django.core.cache import cache as django_cache

    lock_key = 'ingest_rda_weather_data_lock'
    acquired = django_cache.add(lock_key, 'locked', timeout=7200)
    if not acquired:
        logger.warning("ingest_rda_weather_data already running, skipping")
        return 'already_running'

    try:
        download_dir = os.environ.get('RDA_DOWNLOAD_DIR', '')
        if not download_dir:
            logger.warning("RDA_DOWNLOAD_DIR not set, skipping weather ingestion")
            return 'skipped'
        call_command('ingest_weather', path=download_dir)
        return 'ok'
    finally:
        django_cache.delete(lock_key)


@shared_task
def cleanup_rda_downloads():
    """Reclaim disk from already-ingested RDA downloads past retention."""
    download_dir = os.environ.get('RDA_DOWNLOAD_DIR', '')
    if not download_dir:
        logger.warning("RDA_DOWNLOAD_DIR not set, skipping cleanup")
        return 'skipped'
    call_command('cleanup_rda_downloads')
    return 'ok'


@shared_task
def trigger_rda_control_files():
    """Generate fresh .ctl control files for the upcoming week."""
    from CarbonCastRESTAPI.services.ctl_generator import generate_weekly_ctl_files

    ctl_dir = os.environ.get('RDA_CONTROL_FILES_DIR', '')
    if not ctl_dir:
        logger.warning("RDA_CONTROL_FILES_DIR not set, skipping ctl generation")
        return 'skipped'
    generate_weekly_ctl_files(ctl_dir)
    return 'ok'


@shared_task
def check_weather_freshness_and_fallback():
    """Check if recent weather data exists; if not, attempt fallback sources."""
    from datetime import datetime, timezone
    from django.core.cache import cache as django_cache
    from CarbonCastRESTAPI.models import WeatherForecast

    lock_key = 'check_weather_freshness_and_fallback_lock'
    acquired = django_cache.add(lock_key, 'locked', timeout=3600)
    if not acquired:
        logger.warning("check_weather_freshness_and_fallback already running, skipping")
        return 'already_running'

    try:
        return _check_weather_freshness_and_fallback(WeatherForecast)
    finally:
        django_cache.delete(lock_key)


def _check_weather_freshness_and_fallback(WeatherForecast):
    """Implementation split out so tests can exercise fallback behavior directly."""
    from datetime import datetime, timezone

    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    has_fresh = WeatherForecast.objects.filter(
        forecast_created__gte=one_week_ago
    ).exists()

    if has_fresh:
        logger.info("Fresh RDA weather data available")
        return 'fresh_data_available'

    logger.warning("No fresh RDA weather data found, attempting fallback")

    # Tier 2: try 12-month historical
    twelve_months_ago_start = one_week_ago - timedelta(days=365)
    twelve_months_ago_end = twelve_months_ago_start + timedelta(days=7)
    historical_qs = WeatherForecast.objects.filter(
        forecast_created__gte=twelve_months_ago_start,
        forecast_created__lt=twelve_months_ago_end,
    )
    if historical_qs.exists():
        from django.utils import timezone as tz
        now = tz.now()
        count = 0
        for row in historical_qs.iterator():
            WeatherForecast.objects.update_or_create(
                region=row.region,
                forecast_created=now,
                forecast_target=row.forecast_target + timedelta(days=365),
                variable=row.variable,
                defaults={
                    'value': row.value,
                    'source': 'historical_fallback',
                    'data': row.data,
                },
            )
            count += 1
        logger.info("Copied %d historical fallback rows", count)
        return f'historical_fallback:{count}'

    logger.critical("No weather data available at all — retraining will use stale data")
    return 'no_data'


@shared_task(bind=True, time_limit=14400, soft_time_limit=13800)
def retrain_models(self):
    """Weekly model retraining: export DB data, run ML pipeline, store forecasts."""
    from django.core.cache import cache as django_cache

    lock_key = 'retrain_models_lock'
    acquired = django_cache.add(lock_key, 'locked', timeout=14400)
    if not acquired:
        logger.warning("retrain_models already running, skipping")
        return 'already_running'

    try:
        from CarbonCastRESTAPI.services.retraining_service import run_retraining
        result = run_retraining()
        logger.info("retrain_models done: %s", result)
        return result
    finally:
        django_cache.delete(lock_key)
