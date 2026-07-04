# Generated migration for performance optimization

from django.db import migrations, models


def _create_hour_index(apps, schema_editor):
    # ts::date / EXTRACT expression index is Postgres-only; SQLite deployments
    # rely on the plain (region, ts) index instead
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        """CREATE INDEX IF NOT EXISTS emission_region_date_hour_idx
           ON "CarbonCastRESTAPI_emissionactual"
           (region, (ts::date), EXTRACT(HOUR FROM ts));"""
    )


def _drop_hour_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute("DROP INDEX IF EXISTS emission_region_date_hour_idx;")


class Migration(migrations.Migration):

    dependencies = [
        ('CarbonCastRESTAPI', '0002_weather_forecast96_emissionactual'),
    ]

    operations = [
        # Add index for date queries (region + date part of timestamp)
        migrations.AddIndex(
            model_name='emissionactual',
            index=models.Index(fields=['region', 'ts'], name='emission_region_ts_idx'),
        ),
        # Add index for hour-specific queries (Postgres only)
        migrations.RunPython(_create_hour_index, _drop_hour_index),
        # Optimize Forecast96 indexes
        migrations.AddIndex(
            model_name='forecast96',
            index=models.Index(fields=['region', 'forecast_type', 'ts'], name='forecast_region_type_ts_idx'),
        ),
    ]