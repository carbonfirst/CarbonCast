from django.contrib import admin

from .models import EmissionActual, Forecast96, ModelRun, Weather, WeatherForecast


@admin.register(EmissionActual)
class EmissionActualAdmin(admin.ModelAdmin):
    list_display = ('region', 'ts', 'metric_type', 'lifecycle', 'direct', 'source_file')
    list_filter = ('region', 'metric_type')
    date_hierarchy = 'ts'
    search_fields = ('region', 'source_file')
    ordering = ('-ts',)


@admin.register(Forecast96)
class Forecast96Admin(admin.ModelAdmin):
    list_display = ('region', 'ts', 'forecast_type', 'value', 'forecast_horizon', 'batch_id')
    list_filter = ('region', 'forecast_type', 'forecast_horizon')
    date_hierarchy = 'ts'
    search_fields = ('region', 'batch_id')
    ordering = ('-ts',)


@admin.register(Weather)
class WeatherAdmin(admin.ModelAdmin):
    list_display = ('region', 'ts', 'temp')
    list_filter = ('region',)
    date_hierarchy = 'ts'
    ordering = ('-ts',)


@admin.register(WeatherForecast)
class WeatherForecastAdmin(admin.ModelAdmin):
    list_display = ('region', 'variable', 'forecast_created', 'forecast_target', 'value', 'source')
    list_filter = ('region', 'variable', 'source')
    date_hierarchy = 'forecast_created'
    ordering = ('-forecast_created',)


@admin.register(ModelRun)
class ModelRunAdmin(admin.ModelAdmin):
    list_display = ('region', 'model_name', 'status', 'weather_source', 'run_started', 'run_completed')
    list_filter = ('status', 'model_name', 'weather_source')
    date_hierarchy = 'run_started'
    search_fields = ('region',)
    ordering = ('-run_started',)
    readonly_fields = ('run_started',)
