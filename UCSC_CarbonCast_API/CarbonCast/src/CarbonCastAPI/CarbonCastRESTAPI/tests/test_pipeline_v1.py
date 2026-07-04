from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from CarbonCastRESTAPI.models import EmissionActual, Forecast96, ModelRun, WeatherForecast
from CarbonCastRESTAPI.services.eia_service import _parse_hourly_records
from CarbonCastRESTAPI.services.retraining_service import run_retraining


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class PipelineV1Test(TestCase):
    def test_eia_parser_computes_direct_and_lifecycle_ci(self):
        rows = [
            {'period': '2026-05-01T00', 'fueltype': 'COL', 'value': '100'},
            {'period': '2026-05-01T00', 'fueltype': 'NG', 'value': '100'},
        ]

        records = _parse_hourly_records(rows, 'PJM')

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['data']['coal'], 100.0)
        self.assertEqual(records[0]['data']['nat_gas'], 100.0)
        self.assertAlmostEqual(records[0]['direct'], 565.0)
        self.assertAlmostEqual(records[0]['lifecycle'], 655.0)

    def test_weather_ingestion_parses_csv_and_preserves_source(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'PJM' / 'dswrf'
            path.mkdir(parents=True)
            (path / 'forecast.csv').write_text('timestamp,value\n2026-05-05T00:00:00+00:00,12.5\n')

            call_command('ingest_weather', path=tmpdir)

        row = WeatherForecast.objects.get(region='PJM', variable='dswrf')
        self.assertEqual(row.source, 'rda')
        self.assertEqual(row.value, 12.5)

    def test_weather_ingestion_infers_flat_layout(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'PJM_dswrf_forecast.csv'
            path.write_text('timestamp,value\n2026-05-05T00:00:00+00:00,9.5\n')

            call_command('ingest_weather', path=tmpdir)

        row = WeatherForecast.objects.get(region='PJM', variable='dswrf')
        self.assertEqual(row.value, 9.5)

    def test_retraining_writes_168h_forecast_batch_and_model_run(self):
        base = timezone.now() - timedelta(days=7)
        for i in range(48):
            EmissionActual.objects.create(
                region='PJM',
                ts=base + timedelta(hours=i),
                lifecycle=400 + i,
                direct=300 + i,
                data={
                    'coal': 10,
                    'nat_gas': 20,
                    'nuclear': 30,
                    'oil': 1,
                    'hydro': 2,
                    'solar': 3,
                    'wind': 4,
                    'other': 5,
                },
            )

        result = run_retraining()

        self.assertEqual(result['regions_processed'], 1)
        self.assertEqual(ModelRun.objects.filter(region='PJM', status='completed').count(), 1)
        self.assertEqual(
            Forecast96.objects.filter(region='PJM', forecast_horizon=168, forecast_type='lifecycle').count(),
            168,
        )
        self.assertEqual(
            Forecast96.objects.filter(region='PJM', forecast_horizon=168, forecast_type='direct').count(),
            168,
        )
        self.assertEqual(
            Forecast96.objects.filter(region='PJM', forecast_horizon=168, forecast_type='energy').count(),
            168,
        )

    def test_setup_pipeline_schedules_is_idempotent(self):
        from django_celery_beat.models import PeriodicTask

        from CarbonCastRESTAPI.management.commands.setup_pipeline_schedules import Command

        call_command('setup_pipeline_schedules')
        call_command('setup_pipeline_schedules')

        self.assertEqual(
            PeriodicTask.objects.filter(name='carboncast.weekly_retraining').count(),
            1,
        )
        # Compare against the command's own task list so adding a schedule
        # doesn't silently break this test
        self.assertEqual(
            PeriodicTask.objects.filter(name__startswith='carboncast.').count(),
            len(Command.TASKS),
        )


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class PipelineStatusTest(TestCase):
    def test_pipeline_status_returns_all_stages(self):
        response = self.client.get('/v1/PipelineStatus')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        stage_keys = [s['key'] for s in payload['stages']]
        self.assertEqual(stage_keys, [
            'ctl_generation', 'rda_tool', 'weather_ingestion',
            'energy_eia', 'energy_entsoe', 'freshness_fallback',
            'retraining', 'forecast_serving',
        ])
        for stage in payload['stages']:
            self.assertIn(stage['status'], {
                'ok', 'degraded', 'failed', 'stale',
                'waiting_on_credential', 'waiting_on_config', 'never_ran',
            })
        self.assertIn('overall', payload)

    def test_pipeline_status_reflects_retraining_failures(self):
        ModelRun.objects.create(
            region='CISO', model_name='litecast', status='failed',
            metrics={'error': 'boom'},
        )
        ModelRun.objects.create(
            region='PJM', model_name='litecast', status='completed',
            run_completed=timezone.now(),
        )

        response = self.client.get('/v1/PipelineStatus')
        retraining = next(
            s for s in response.json()['stages'] if s['key'] == 'retraining'
        )
        self.assertEqual(retraining['status'], 'degraded')
        self.assertEqual(retraining['metrics']['counts']['failed'], 1)
        self.assertEqual(
            retraining['metrics']['failed_regions'][0]['region'], 'CISO')

    def test_pipeline_health_reports_components(self):
        response = self.client.get('/v1/PipelineHealth')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            set(payload['checks'].keys()),
            {'database', 'redis_cache', 'celery_worker', 'celery_beat'},
        )
        # DB and (locmem) cache must pass in tests; worker/beat won't be
        # running, so overall ok must be False
        self.assertTrue(payload['checks']['database']['ok'])
        self.assertTrue(payload['checks']['redis_cache']['ok'])
        self.assertFalse(payload['checks']['celery_worker']['ok'])
        self.assertFalse(payload['ok'])
