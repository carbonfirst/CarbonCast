from ._base import *


class RetrainingStatusApiView(APIView):
    """
    Reports the most recent weekly retraining run per region: which model was
    used (CarbonCast/LiteCast), the weather source (live RDA vs 12-month
    fallback), status, and timing. Powers operational visibility for the
    weekly retraining cycle described in the real-time service plan.
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        region_code = request.query_params.get('region_code')

        runs_qs = ModelRun.objects.all().order_by('region', '-run_started')
        if region_code and region_code != 'all':
            runs_qs = runs_qs.filter(region=region_code)

        # Keep only the latest run per region.
        latest_by_region = {}
        for run in runs_qs:
            if run.region not in latest_by_region:
                latest_by_region[run.region] = run

        rows = []
        for region in sorted(latest_by_region):
            run = latest_by_region[region]
            metrics = run.metrics or {}
            rows.append({
                'region': region,
                'model_name': run.model_name,
                'model_lookback_days': (run.config or {}).get('model_lookback_days'),
                'status': run.status,
                'weather_source': run.weather_source,
                'weather_is_fallback': run.weather_source == 'historical_fallback',
                'run_started': run.run_started,
                'run_completed': run.run_completed,
                'forecast_horizon': metrics.get('forecast_horizon') or (run.config or {}).get('forecast_horizon'),
                'batch_id': metrics.get('batch_id'),
                'forecast_rows': metrics.get('forecast_rows'),
                'error': metrics.get('error'),
            })

        return Response({
            'retraining_status': rows,
            'carbon_cast_version': carbon_cast_version,
        })
