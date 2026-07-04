import json
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django_celery_beat.models import CrontabSchedule, PeriodicTask, PeriodicTasks


class Command(BaseCommand):
    help = "Idempotently create or update CarbonCast pipeline Celery Beat schedules."

    TASKS = [
        {
            'name': 'carboncast.heartbeat',
            'task': 'CarbonCastRESTAPI.tasks.heartbeat',
            'minute': '*/5',
            'hour': '*',
            'day_of_week': '*',
            'description': 'Worker liveness heartbeat every 5 minutes (read by /v1/PipelineHealth).',
        },
        {
            'name': 'carboncast.daily_rda_cleanup',
            'task': 'CarbonCastRESTAPI.tasks.cleanup_rda_downloads',
            'minute': '0',
            'hour': '4',
            'day_of_week': '*',
            'description': 'Reclaim disk from ingested RDA downloads daily at 04:00 UTC.',
        },
        {
            'name': 'carboncast.daily_eia_ingestion',
            'task': 'CarbonCastRESTAPI.tasks.fetch_daily_energy_data',
            'minute': '0',
            'hour': '6',
            'day_of_week': '*',
            'description': 'Daily EIA (US) ingestion for yesterday at 06:00 UTC.',
        },
        {
            'name': 'carboncast.daily_entsoe_ingestion',
            'task': 'CarbonCastRESTAPI.tasks.fetch_daily_entsoe_data',
            'minute': '30',
            'hour': '6',
            'day_of_week': '*',
            'description': 'Daily ENTSO-E (EU) ingestion for yesterday at 06:30 UTC.',
        },
        {
            'name': 'carboncast.rda_weather_ingestion',
            'task': 'CarbonCastRESTAPI.tasks.ingest_rda_weather_data',
            'minute': '0',
            'hour': '*/2',
            'day_of_week': '*',
            'description': 'Scan RDA weather downloads every 2 hours.',
        },
        {
            'name': 'carboncast.weekly_ctl_generation',
            'task': 'CarbonCastRESTAPI.tasks.trigger_rda_control_files',
            'minute': '0',
            'hour': '3',
            'day_of_week': '1',
            'description': 'Generate weekly RDA CTL files Monday 03:00 UTC.',
        },
        {
            'name': 'carboncast.weekly_weather_fallback_check',
            'task': 'CarbonCastRESTAPI.tasks.check_weather_freshness_and_fallback',
            'minute': '0',
            'hour': '5',
            'day_of_week': '1',
            'description': 'Verify weekly weather availability Monday 05:00 UTC.',
        },
        {
            'name': 'carboncast.weekly_retraining',
            'task': 'CarbonCastRESTAPI.tasks.retrain_models',
            'minute': '0',
            'hour': '6',
            'day_of_week': '1',
            'description': 'Run weekly CarbonCast retraining Monday 06:00 UTC.',
        },
    ]

    def handle(self, *args, **options):
        updated = 0
        created = 0
        tz = ZoneInfo('UTC')

        with transaction.atomic():
            for task_def in self.TASKS:
                schedule, _ = CrontabSchedule.objects.get_or_create(
                    minute=task_def['minute'],
                    hour=task_def['hour'],
                    day_of_week=task_def['day_of_week'],
                    day_of_month='*',
                    month_of_year='*',
                    timezone=tz,
                )

                _, was_created = PeriodicTask.objects.update_or_create(
                    name=task_def['name'],
                    defaults={
                        'task': task_def['task'],
                        'crontab': schedule,
                        'interval': None,
                        'solar': None,
                        'clocked': None,
                        'args': json.dumps([]),
                        'kwargs': json.dumps({}),
                        'enabled': True,
                        'description': task_def['description'],
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        PeriodicTasks.update_changed()
        self.stdout.write(f"created: {created}")
        self.stdout.write(f"updated: {updated}")
