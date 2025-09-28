# Generated migration for performance optimization

from django.db import migrations, models


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
        # Add index for hour-specific queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS emission_region_date_hour_idx ON CarbonCastRESTAPI_emissionactual (region, date(ts), strftime('%H', ts));",
            reverse_sql="DROP INDEX IF EXISTS emission_region_date_hour_idx;"
        ),
        # Optimize Forecast96 indexes
        migrations.AddIndex(
            model_name='forecast96',
            index=models.Index(fields=['region', 'forecast_type', 'ts'], name='forecast_region_type_ts_idx'),
        ),
    ]