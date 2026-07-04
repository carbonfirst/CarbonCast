from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def _sqlite_pragmas(sender, connection, **kwargs):
    # WAL journal lets the API serve reads while a Celery worker writes;
    # only relevant when running with DB_ENGINE=sqlite.
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA busy_timeout=30000;')


class CarboncastrestapiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'CarbonCastRESTAPI'
