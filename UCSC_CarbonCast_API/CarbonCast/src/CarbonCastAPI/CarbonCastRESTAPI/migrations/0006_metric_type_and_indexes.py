from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('CarbonCastRESTAPI', '0005_pipeline_models_and_forecast168'),
    ]

    operations = [
        # Add metric_type to EmissionActual (defaults to 'carbon' for existing rows).
        migrations.AddField(
            model_name='emissionactual',
            name='metric_type',
            field=models.CharField(
                choices=[
                    ('carbon', 'Carbon intensity'),
                    ('demand', 'Energy demand'),
                    ('price', 'Electricity price'),
                ],
                db_index=True,
                default='carbon',
                max_length=16,
            ),
        ),
        # Add metric_type to Forecast96 (defaults to 'carbon' for existing rows).
        migrations.AddField(
            model_name='forecast96',
            name='metric_type',
            field=models.CharField(
                choices=[
                    ('carbon', 'Carbon intensity'),
                    ('demand', 'Energy demand'),
                    ('price', 'Electricity price'),
                ],
                db_index=True,
                default='carbon',
                max_length=16,
            ),
        ),
        # Widen EmissionActual uniqueness to include metric_type so the same
        # region+hour can hold carbon, demand, and price rows side by side.
        migrations.AlterUniqueTogether(
            name='emissionactual',
            unique_together={('region', 'ts', 'metric_type')},
        ),
        migrations.AddIndex(
            model_name='emissionactual',
            index=models.Index(
                fields=['region', 'metric_type', 'ts'],
                name='emission_region_metric_ts_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='forecast96',
            index=models.Index(
                fields=['region', 'metric_type', 'ts'],
                name='forecast_region_metric_ts_idx',
            ),
        ),
    ]
