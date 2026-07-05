"""
Consolidated pipeline observability endpoints.

/v1/PipelineStatus models the end-to-end chain as ordered stages and computes
each stage's health from data the pipeline already records:
- Celery task outcomes from django-celery-results (TaskResult rows)
- The RDA automation tool's state file (RDA_STATE_FILE ->
  batch_automation_state.json) and the ingestion manifest
- Pipeline tables: WeatherForecast, EmissionActual, Forecast96, ModelRun

/v1/PipelineHealth is a cheap liveness probe: DB, Redis cache, Celery worker
(recency of the scheduled heartbeat task's result), and Celery beat
(recency of any PeriodicTask.last_run_at).

Stage status vocabulary (shared with the React dashboard):
  ok | degraded | failed | stale | waiting_on_credential | waiting_on_config | never_ran
"""

import json
import os
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Max
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..consts import carbon_cast_version
from ..models import EmissionActual, Forecast96, ModelRun, WeatherForecast

# Fully-qualified Celery task names as stored by django-celery-results
TASK_NAMES = {
    'heartbeat': 'CarbonCastRESTAPI.tasks.heartbeat',
    'eia': 'CarbonCastRESTAPI.tasks.fetch_daily_energy_data',
    'entsoe': 'CarbonCastRESTAPI.tasks.fetch_daily_entsoe_data',
    'weather_ingest': 'CarbonCastRESTAPI.tasks.ingest_rda_weather_data',
    'ctl_generation': 'CarbonCastRESTAPI.tasks.trigger_rda_control_files',
    'fallback_check': 'CarbonCastRESTAPI.tasks.check_weather_freshness_and_fallback',
    'retraining': 'CarbonCastRESTAPI.tasks.retrain_models',
    'cleanup': 'CarbonCastRESTAPI.tasks.cleanup_rda_downloads',
}

# RDA tool state statuses that mean "work still pending"
RDA_INCOMPLETE_STATUSES = {
    'pending', 'submitting', 'submitted', 'processing', 'ready_for_download', 'downloading',
}


def _latest_task_results(task_name, limit=5):
    """Most recent TaskResult rows for a task, newest first."""
    from django_celery_results.models import TaskResult

    return list(
        TaskResult.objects.filter(task_name=task_name)
        .order_by('-date_done')[:limit]
    )


def _parse_result(task_result):
    """TaskResult.result is a JSON string (or repr); decode best-effort."""
    if task_result is None or task_result.result is None:
        return None
    try:
        return json.loads(task_result.result)
    except (ValueError, TypeError):
        return task_result.result


def _task_summary(task_name, history_limit=5):
    """Common task-derived fields: last run/success + recent failures."""
    results = _latest_task_results(task_name, history_limit)
    last = results[0] if results else None
    last_success = next((r for r in results if r.status == 'SUCCESS'), None)
    recent_errors = [
        {
            'when': r.date_done.isoformat() if r.date_done else None,
            'error': (r.result or '')[:500],
            'traceback_tail': (r.traceback or '')[-500:] if r.traceback else None,
        }
        for r in results if r.status == 'FAILURE'
    ]
    return {
        'last': last,
        'last_run': last.date_done.isoformat() if last and last.date_done else None,
        'last_status': last.status if last else None,
        'last_result': _parse_result(last),
        'last_success': last_success.date_done.isoformat() if last_success and last_success.date_done else None,
        'recent_errors': recent_errors,
        'history': [
            {
                'when': r.date_done.isoformat() if r.date_done else None,
                'status': r.status,
                'result': _parse_result(r),
            }
            for r in results
        ],
    }


def _stage(key, label, status_value, message, task_info=None, metrics=None):
    stage = {
        'key': key,
        'label': label,
        'status': status_value,
        'message': message,
        'last_run': None,
        'last_success': None,
        'metrics': metrics or {},
        'recent_errors': [],
        'history': [],
    }
    if task_info:
        stage['last_run'] = task_info['last_run']
        stage['last_success'] = task_info['last_success']
        stage['recent_errors'] = task_info['recent_errors']
        stage['history'] = task_info['history']
    return stage


def _load_rda_state():
    """Parse the automation tool's state file if RDA_STATE_FILE is set."""
    state_path = os.environ.get('RDA_STATE_FILE', '')
    if not state_path:
        return None, None, 'RDA_STATE_FILE not set'
    if not os.path.exists(state_path):
        # the tool creates this on its first run — absence means "hasn't
        # run yet", not "broken"
        return None, None, 'never_ran'
    try:
        with open(state_path) as f:
            state = json.load(f)
        mtime = os.path.getmtime(state_path)
        return state, mtime, None
    except Exception as exc:
        return None, None, f'state file unreadable: {exc}'


class PipelineStatusApiView(APIView):
    """Aggregated per-stage view of the whole ingestion/forecast pipeline."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        stages = [
            self._ctl_generation_stage(now),
            self._rda_tool_stage(now),
            self._weather_ingestion_stage(now),
            self._energy_stage(now, 'energy_eia', 'Energy ingestion (EIA / US)', TASK_NAMES['eia'], 'EIA_API_KEY'),
            self._energy_stage(now, 'energy_entsoe', 'Energy ingestion (ENTSO-E / EU)', TASK_NAMES['entsoe'], 'ENTSOE_API_TOKEN'),
            self._fallback_stage(now),
            self._retraining_stage(now),
            self._forecast_serving_stage(now),
        ]

        worst = 'ok'
        severity = {'ok': 0, 'never_ran': 1, 'waiting_on_config': 2, 'waiting_on_credential': 2,
                    'stale': 3, 'degraded': 4, 'failed': 5}
        for s in stages:
            if severity.get(s['status'], 0) > severity.get(worst, 0):
                worst = s['status']

        return Response({
            'generated_at': now.isoformat(),
            'overall': worst,
            'stages': stages,
            'carbon_cast_version': carbon_cast_version,
        }, status=status.HTTP_200_OK)

    # ── stage builders ────────────────────────────────────────────────

    def _ctl_generation_stage(self, now):
        info = _task_summary(TASK_NAMES['ctl_generation'])
        ctl_dir = os.environ.get('RDA_CONTROL_FILES_DIR', '')

        metrics = {'ctl_dir': ctl_dir or None, 'ctl_files': None}
        if ctl_dir and os.path.isdir(ctl_dir):
            ctl_files = [f for f in os.listdir(ctl_dir) if f.endswith('.ctl')]
            metrics['ctl_files'] = len(ctl_files)

        if not ctl_dir:
            return _stage('ctl_generation', 'Control file generation', 'waiting_on_config',
                          'RDA_CONTROL_FILES_DIR not set — weekly ctl generation is skipped',
                          info, metrics)
        if info['last_run'] is None:
            return _stage('ctl_generation', 'Control file generation', 'never_ran',
                          'No task run recorded yet', info, metrics)
        if info['last_status'] == 'FAILURE':
            return _stage('ctl_generation', 'Control file generation', 'failed',
                          'Last run failed', info, metrics)
        if info['last_result'] == 'skipped':
            return _stage('ctl_generation', 'Control file generation', 'waiting_on_config',
                          'Task ran but skipped (env unset in worker)', info, metrics)
        if info['last_success']:
            from datetime import datetime, timezone as dt_tz
            last_ok = datetime.fromisoformat(info['last_success'])
            if last_ok < now - timedelta(days=8):
                return _stage('ctl_generation', 'Control file generation', 'stale',
                              'Last successful generation more than 8 days ago', info, metrics)
        return _stage('ctl_generation', 'Control file generation', 'ok',
                      f"{metrics['ctl_files'] or 0} control files present", info, metrics)

    def _rda_tool_stage(self, now):
        state, mtime, err = _load_rda_state()
        if err == 'never_ran':
            return _stage('rda_tool', 'RDA download tool', 'never_ran',
                          'Tool has not run yet — no state file created')
        if err:
            status_value = 'waiting_on_config' if 'not set' in err else 'degraded'
            return _stage('rda_tool', 'RDA download tool', status_value, err)

        breakdown = {}
        per_region = {}
        for ctl_path, entry in (state or {}).items():
            st = entry.get('status', 'unknown')
            breakdown[st] = breakdown.get(st, 0) + 1
            region = os.path.basename(ctl_path).split('_')[0]
            region_counts = per_region.setdefault(region, {'done': 0, 'total': 0, 'failed': 0})
            region_counts['total'] += 1
            if st in ('downloaded', 'downloaded_purged'):
                region_counts['done'] += 1
            elif st in ('failed', 'failed_purged'):
                region_counts['failed'] += 1

        incomplete = sum(v for k, v in breakdown.items() if k in RDA_INCOMPLETE_STATUSES)
        failed = breakdown.get('failed', 0) + breakdown.get('failed_purged', 0)
        total = sum(breakdown.values())

        from datetime import datetime, timezone as dt_tz
        state_age_min = None
        if mtime:
            state_age_min = round((now.timestamp() - mtime) / 60, 1)

        metrics = {
            'requests_total': total,
            'status_breakdown': breakdown,
            'incomplete': incomplete,
            'failed': failed,
            'state_file_age_minutes': state_age_min,
            'regions': per_region,
        }

        if total == 0:
            return _stage('rda_tool', 'RDA download tool', 'never_ran',
                          'State file empty — tool has not processed any control files', metrics=metrics)
        if incomplete > 0 and state_age_min is not None and state_age_min > 30:
            return _stage('rda_tool', 'RDA download tool', 'degraded',
                          f'{incomplete} requests in flight but state file untouched for '
                          f'{state_age_min:.0f} min — tool may not be running', metrics=metrics)
        if failed == total:
            return _stage('rda_tool', 'RDA download tool', 'failed',
                          'All requests failed', metrics=metrics)
        if failed > 0:
            return _stage('rda_tool', 'RDA download tool', 'degraded',
                          f'{failed}/{total} requests failed', metrics=metrics)
        if incomplete > 0:
            return _stage('rda_tool', 'RDA download tool', 'ok',
                          f'{incomplete}/{total} requests in progress', metrics=metrics)
        return _stage('rda_tool', 'RDA download tool', 'ok',
                      f'All {total} requests completed', metrics=metrics)

    def _weather_ingestion_stage(self, now):
        info = _task_summary(TASK_NAMES['weather_ingest'])
        latest = WeatherForecast.objects.aggregate(latest=Max('forecast_created'))['latest']
        by_source = {}
        if latest:
            recent = WeatherForecast.objects.filter(forecast_created__gte=now - timedelta(days=7))
            for row in recent.values('source').distinct():
                by_source[row['source']] = recent.filter(source=row['source']).count()

        download_dir = os.environ.get('RDA_DOWNLOAD_DIR', '')
        manifest_count = None
        if download_dir:
            manifest_path = os.path.join(download_dir, 'processed_files.json')
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path) as f:
                        manifest_count = len(json.load(f))
                except Exception:
                    manifest_count = None

        metrics = {
            'latest_forecast_created': latest.isoformat() if latest else None,
            'rows_last_7d_by_source': by_source,
            'ingested_files_total': manifest_count,
            'download_dir': download_dir or None,
        }

        if not download_dir:
            return _stage('weather_ingestion', 'Weather ingestion', 'waiting_on_config',
                          'RDA_DOWNLOAD_DIR not set — 2-hourly ingestion is skipped', info, metrics)
        if info['last_run'] is None:
            return _stage('weather_ingestion', 'Weather ingestion', 'never_ran',
                          'No ingestion run recorded yet', info, metrics)
        if info['last_status'] == 'FAILURE':
            return _stage('weather_ingestion', 'Weather ingestion', 'failed',
                          'Last ingestion run failed', info, metrics)
        if latest is None:
            return _stage('weather_ingestion', 'Weather ingestion', 'degraded',
                          'Task runs but no WeatherForecast rows exist yet', info, metrics)
        if latest < now - timedelta(days=7):
            return _stage('weather_ingestion', 'Weather ingestion', 'stale',
                          f'Newest weather batch is from {latest.date().isoformat()}', info, metrics)
        return _stage('weather_ingestion', 'Weather ingestion', 'ok',
                      f'Latest weather batch {latest.date().isoformat()}', info, metrics)

    def _energy_stage(self, now, key, label, task_name, credential_env):
        info = _task_summary(task_name)
        result = info['last_result'] if isinstance(info['last_result'], dict) else {}

        metrics = {
            'inserted': result.get('inserted'),
            'updated': result.get('updated'),
            'regions_ok': result.get('regions_ok'),
            'regions_failed': result.get('regions_failed'),
            'region_errors': result.get('errors', [])[:10],
        }

        if not os.environ.get(credential_env, ''):
            return _stage(key, label, 'waiting_on_credential',
                          f'{credential_env} not set — ingestion runs but skips', info, metrics)
        if info['last_run'] is None:
            return _stage(key, label, 'never_ran', 'No run recorded yet', info, metrics)
        if info['last_status'] == 'FAILURE':
            return _stage(key, label, 'failed', 'Last run raised an exception', info, metrics)
        svc_status = result.get('status')
        if svc_status == 'waiting_on_credential':
            return _stage(key, label, 'waiting_on_credential',
                          f'{credential_env} was unset in the worker at last run', info, metrics)
        if svc_status == 'failed':
            return _stage(key, label, 'failed', 'All regions failed at last run', info, metrics)
        if svc_status == 'partial':
            return _stage(key, label, 'degraded',
                          f"{result.get('regions_failed', '?')} regions failed at last run", info, metrics)
        if info['last_success']:
            from datetime import datetime
            last_ok = datetime.fromisoformat(info['last_success'])
            if last_ok < now - timedelta(days=2):
                return _stage(key, label, 'stale', 'No successful run in 2+ days', info, metrics)
        return _stage(key, label, 'ok',
                      f"Last run inserted {result.get('inserted', '?')}, updated {result.get('updated', '?')}",
                      info, metrics)

    def _fallback_stage(self, now):
        info = _task_summary(TASK_NAMES['fallback_check'])
        result = info['last_result']
        metrics = {'last_outcome': result if isinstance(result, str) else None}

        if info['last_run'] is None:
            return _stage('freshness_fallback', 'Weather freshness / fallback', 'never_ran',
                          'No freshness check recorded yet', info, metrics)
        if info['last_status'] == 'FAILURE':
            return _stage('freshness_fallback', 'Weather freshness / fallback', 'failed',
                          'Last check failed', info, metrics)
        if isinstance(result, str):
            if result == 'fresh_data_available':
                return _stage('freshness_fallback', 'Weather freshness / fallback', 'ok',
                              'Fresh RDA weather available', info, metrics)
            if result.startswith('historical_fallback'):
                return _stage('freshness_fallback', 'Weather freshness / fallback', 'degraded',
                              'Running on 12-month-old historical weather fallback', info, metrics)
            if result == 'no_data':
                return _stage('freshness_fallback', 'Weather freshness / fallback', 'failed',
                              'No weather data available at all', info, metrics)
        return _stage('freshness_fallback', 'Weather freshness / fallback', 'ok',
                      'Check ran', info, metrics)

    def _retraining_stage(self, now):
        info = _task_summary(TASK_NAMES['retraining'])
        latest_by_region = {}
        for run in ModelRun.objects.order_by('region', '-run_started'):
            if run.region not in latest_by_region:
                latest_by_region[run.region] = run

        counts = {'completed': 0, 'failed': 0, 'running': 0}
        failed_regions = []
        last_completed = None
        for region, run in latest_by_region.items():
            counts[run.status] = counts.get(run.status, 0) + 1
            if run.status == 'failed':
                failed_regions.append({
                    'region': region,
                    'error': ((run.metrics or {}).get('error') or '')[:300],
                })
            if run.status == 'completed' and run.run_completed:
                if last_completed is None or run.run_completed > last_completed:
                    last_completed = run.run_completed

        metrics = {
            'regions_tracked': len(latest_by_region),
            'counts': counts,
            'failed_regions': failed_regions[:10],
            'last_completed': last_completed.isoformat() if last_completed else None,
        }

        if not latest_by_region:
            return _stage('retraining', 'Model retraining', 'never_ran',
                          'No ModelRun rows yet', info, metrics)
        if info['last_status'] == 'FAILURE':
            return _stage('retraining', 'Model retraining', 'failed',
                          'Last retraining task failed outright', info, metrics)
        if counts.get('failed') and counts['failed'] == len(latest_by_region):
            return _stage('retraining', 'Model retraining', 'failed',
                          'All regions failed their latest run', info, metrics)
        if counts.get('failed'):
            return _stage('retraining', 'Model retraining', 'degraded',
                          f"{counts['failed']}/{len(latest_by_region)} regions failed", info, metrics)
        if last_completed and last_completed < now - timedelta(days=8):
            return _stage('retraining', 'Model retraining', 'stale',
                          'No completed retraining in 8+ days', info, metrics)
        return _stage('retraining', 'Model retraining', 'ok',
                      f"{counts.get('completed', 0)} regions retrained", info, metrics)

    def _forecast_serving_stage(self, now):
        horizon_floor = now + timedelta(hours=24)
        regions_with_forecast = (
            Forecast96.objects.filter(ts__gte=horizon_floor)
            .values_list('region', flat=True).distinct()
        )
        regions_with_actuals = (
            EmissionActual.objects.values_list('region', flat=True).distinct()
        )
        covered = set(regions_with_forecast)
        expected = set(regions_with_actuals)
        missing = sorted(expected - covered)

        metrics = {
            'regions_with_24h_forecast': len(covered),
            'regions_with_actuals': len(expected),
            'regions_missing_forecast': missing[:20],
        }

        if not expected:
            return _stage('forecast_serving', 'Forecast serving', 'never_ran',
                          'No energy actuals in DB yet (seed with import_csvs)', metrics=metrics)
        if not covered:
            return _stage('forecast_serving', 'Forecast serving', 'failed',
                          'No region has forecasts beyond +24h', metrics=metrics)
        if missing:
            return _stage('forecast_serving', 'Forecast serving', 'degraded',
                          f'{len(missing)} regions lack +24h forecasts', metrics=metrics)
        return _stage('forecast_serving', 'Forecast serving', 'ok',
                      f'All {len(covered)} regions have 24h+ forecasts', metrics=metrics)


class PipelineHealthApiView(APIView):
    """Cheap liveness probe for the runtime components."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        checks = {}

        # Database
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks['database'] = {'ok': True}
        except Exception as exc:
            checks['database'] = {'ok': False, 'error': str(exc)[:200]}

        # Redis cache
        try:
            probe_key = 'pipeline_health_probe'
            cache.set(probe_key, 'ok', 30)
            checks['redis_cache'] = {'ok': cache.get(probe_key) == 'ok'}
        except Exception as exc:
            checks['redis_cache'] = {'ok': False, 'error': str(exc)[:200]}

        # Celery worker: recency of the scheduled heartbeat task's result
        try:
            from django_celery_results.models import TaskResult
            hb = (
                TaskResult.objects.filter(task_name=TASK_NAMES['heartbeat'])
                .order_by('-date_done').first()
            )
            if hb and hb.date_done and hb.date_done > now - timedelta(minutes=15):
                checks['celery_worker'] = {'ok': True, 'last_heartbeat': hb.date_done.isoformat()}
            else:
                checks['celery_worker'] = {
                    'ok': False,
                    'last_heartbeat': hb.date_done.isoformat() if hb and hb.date_done else None,
                    'error': 'no heartbeat result in the last 15 minutes',
                }
        except Exception as exc:
            checks['celery_worker'] = {'ok': False, 'error': str(exc)[:200]}

        # Celery beat: any schedule fired recently
        try:
            from django_celery_beat.models import PeriodicTask
            last_beat = (
                PeriodicTask.objects.filter(last_run_at__isnull=False)
                .aggregate(latest=Max('last_run_at'))['latest']
            )
            if last_beat and last_beat > now - timedelta(minutes=15):
                checks['celery_beat'] = {'ok': True, 'last_dispatch': last_beat.isoformat()}
            else:
                checks['celery_beat'] = {
                    'ok': False,
                    'last_dispatch': last_beat.isoformat() if last_beat else None,
                    'error': 'no schedule dispatched in the last 15 minutes',
                }
        except Exception as exc:
            checks['celery_beat'] = {'ok': False, 'error': str(exc)[:200]}

        all_ok = all(c.get('ok') for c in checks.values())
        return Response({
            'ok': all_ok,
            'checks': checks,
            'generated_at': now.isoformat(),
            'carbon_cast_version': carbon_cast_version,
        }, status=status.HTTP_200_OK)
