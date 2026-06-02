from ._base import *


class SupportedRegionsApiView(APIView):
    authentication_classes = authentication_classes
    permission_classes = permission_classes

    @swagger_auto_schema(
        responses={
            200: 'HTTP 200 OK - Success response description',
        }
    )

    def get(self, request, *args, **kwargs):

        if permissions.AllowAny not in permission_classes:
            user = request.user
            print("User:",user)
            if not check_throttle_limit(user):
                return Response({
                    "status": "fail",
                    "message": "Throttle limit reached",
                    "carbon_cast_version": carbon_cast_version
                }, status=status.HTTP_429_TOO_MANY_REQUESTS, headers={'Retry-After': 86400})

        # Try to discover supported regions from DB first
        regions = list(EmissionActual.objects.order_by('region').values_list('region', flat=True).distinct())
        # include any regions from forecasts and weather as well
        regions = sorted(
            set(regions)
            | set(Forecast96.objects.order_by('region').values_list('region', flat=True).distinct())
            | set(Weather.objects.order_by('region').values_list('region', flat=True).distinct())
            | set(WeatherForecast.objects.order_by('region').values_list('region', flat=True).distinct())
        )
        response = {
            "US_supported_regions": regions,
            "carbon_cast_version": carbon_cast_version
        }
        return Response(response, status=status.HTTP_200_OK)
    
class DataFreshnessApiView(APIView):
    """Returns the latest timestamp per data type per region."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request, version=None):
        from django.db.models import Max
        from datetime import timedelta
        from django.utils import timezone

        region_code = request.query_params.get('region_code')
        now = timezone.now()

        emission_qs = EmissionActual.objects.all()
        weather_qs = WeatherForecast.objects.all()
        forecast_qs = Forecast96.objects.all()

        if region_code and region_code != 'all':
            emission_qs = emission_qs.filter(region=region_code)
            weather_qs = weather_qs.filter(region=region_code)
            forecast_qs = forecast_qs.filter(region=region_code)

        emission_freshness = (
            emission_qs
            .values('region')
            .annotate(last_ts=Max('ts'))
            .order_by('region')
        )
        weather_freshness = (
            weather_qs
            .values('region')
            .annotate(last_forecast_created=Max('forecast_created'))
            .order_by('region')
        )
        forecast_freshness = (
            forecast_qs
            .values('region')
            .annotate(last_ts=Max('ts'))
            .order_by('region')
        )

        emissions = list(emission_freshness)
        weather = list(weather_freshness)
        forecasts = list(forecast_freshness)
        emission_by_region = {row['region']: row['last_ts'] for row in emissions}
        weather_by_region = {row['region']: row['last_forecast_created'] for row in weather}
        forecast_by_region = {row['region']: row['last_ts'] for row in forecasts}
        regions = sorted(set(emission_by_region) | set(weather_by_region) | set(forecast_by_region))

        # Surface the weather *source* per region (rda vs historical_fallback vs
        # nomads) so the UI can tell users whether the forecast they're seeing
        # is backed by live weather or a 12-month-old fallback.
        latest_weather_source = {}
        for region in regions:
            src_row = (
                weather_qs.filter(region=region)
                .order_by('-forecast_created')
                .values('source')
                .first()
            )
            if src_row:
                latest_weather_source[region] = src_row['source']

        status_rows = []
        for region in regions:
            latest_actual = emission_by_region.get(region)
            latest_weather = weather_by_region.get(region)
            latest_forecast = forecast_by_region.get(region)
            weather_source = latest_weather_source.get(region)
            status_rows.append({
                'region': region,
                'latest_actual_ts': latest_actual,
                'latest_weather_created': latest_weather,
                'latest_forecast_ts': latest_forecast,
                'weather_source': weather_source,
                'weather_is_fallback': weather_source == 'historical_fallback',
                'actuals_stale': latest_actual is None or latest_actual < now - timedelta(days=2),
                'weather_stale': latest_weather is None or latest_weather < now - timedelta(hours=6),
                'forecast_missing_or_short': latest_forecast is None or latest_forecast < now + timedelta(hours=160),
            })

        return Response({
            'emissions': emissions,
            'weather_forecasts': weather,
            'forecasts': forecasts,
            'status': status_rows,
            'carbon_cast_version': carbon_cast_version,
        })
