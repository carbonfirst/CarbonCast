from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('CarbonCastRESTAPI', '0004_remove_emissionactual_emission_region_ts_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='forecast96',
            name='forecast_horizon',
            field=models.IntegerField(default=96),
        ),
        migrations.AddField(
            model_name='forecast96',
            name='batch_id',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.CreateModel(
            name='ModelRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('region', models.CharField(db_index=True, max_length=32)),
                ('model_name', models.CharField(max_length=64)),
                ('run_started', models.DateTimeField(auto_now_add=True)),
                ('run_completed', models.DateTimeField(null=True)),
                ('status', models.CharField(default='running', max_length=16)),
                ('weather_source', models.CharField(default='rda', max_length=32)),
                ('config', models.JSONField(blank=True, null=True)),
                ('metrics', models.JSONField(blank=True, null=True)),
                ('model_artifact_path', models.CharField(max_length=512, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='WeatherForecast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('region', models.CharField(db_index=True, max_length=32)),
                ('forecast_created', models.DateTimeField(db_index=True)),
                ('forecast_target', models.DateTimeField(db_index=True)),
                ('variable', models.CharField(db_index=True, max_length=32)),
                ('value', models.FloatField(null=True)),
                ('source', models.CharField(default='rda', max_length=32)),
                ('data', models.JSONField(blank=True, null=True)),
            ],
            options={
                'unique_together': {('region', 'forecast_created', 'forecast_target', 'variable')},
                'indexes': [models.Index(fields=['region', 'forecast_created'], name='CarbonCastR_region_37aa4f_idx')],
            },
        ),
    ]
