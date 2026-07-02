from ._base import *


class CarbonIntensityForecastsApiView(APIView):
    authentication_classes = authentication_classes
    permission_classes = permission_classes

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('regionCode', openapi.IN_QUERY, description="Region code parameter (e.g., 'AECI').", type=openapi.TYPE_STRING),
            openapi.Parameter('forecastPeriod', openapi.IN_QUERY, description="Forecast period in hours ('24h', '48h', '96h', '168h').", type=openapi.TYPE_STRING, default='24h'),
        ],
        responses={
            200: 'HTTP 200 OK - Success response description',
            400: 'HTTP 400 Bad Request - Description of possible error responses',
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

        region_code = request.query_params.get('regionCode', '')
        # Validate against known regions: region_code is used to build
        # filesystem paths in the CSV fallback, so arbitrary values are unsafe
        if region_code not in US_region_codes:
            return Response({"error": "Invalid region code parameter"}, status=status.HTTP_400_BAD_REQUEST)
        f = request.query_params.get('forecastPeriod', '24h')

        f_value = str(f)
        final_interval = int(f_value[:-1] if f_value.endswith('h') else f_value)
        forecastPeriod = min(int(final_interval), 168)

        # Get the current date instead of using hardcoded date
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
        print(f"[CarbonIntensityForecastsApiView] Using date: {date} (was previously hardcoded as 2023-09-17)")

        # Try to read forecasts from DB first
        field_names = [
                        "UTC time", "creation_time (UTC)", "version", "region_code", "carbon_intensity_avg_lifecycle",
                        "carbon_intensity_avg_direct", "carbon_intensity_unit"
        ]
        cache_key = f"ci_forecast_{region_code}_{forecastPeriod}"
        cached = cache.get(cache_key)
        if cached:
            return Response({"data": cached, "carbon_cast_version": carbon_cast_version}, status=status.HTTP_200_OK)

        from datetime import timedelta
        from django.utils import timezone

        forecast_floor = timezone.now() - timedelta(hours=1)
        lifecycle_base = Forecast96.objects.filter(
            region=region_code,
            forecast_type__icontains='lifecycle',
            forecast_horizon__gte=forecastPeriod,
            ts__gte=forecast_floor,
        )
        latest_batch = (
            lifecycle_base.exclude(batch_id__isnull=True)
            .exclude(batch_id='')
            .order_by('-id')
            .values_list('batch_id', flat=True)
            .first()
        )
        direct_base = Forecast96.objects.filter(
            region=region_code,
            forecast_type__icontains='direct',
            forecast_horizon__gte=forecastPeriod,
            ts__gte=forecast_floor,
        )
        if latest_batch:
            lifecycle_base = lifecycle_base.filter(batch_id=latest_batch)
            direct_base = direct_base.filter(batch_id=latest_batch)

        lifecycle_qs = lifecycle_base.order_by('ts')[:forecastPeriod]
        direct_qs = direct_base.order_by('ts')[:forecastPeriod]

        final_list = []
        # Initialize metadata
        forecast_metadata = None
        
        # If DB has no forecasts, fallback to CSV behavior with metadata
        if not lifecycle_qs.exists() or not direct_qs.exists():
            result = get_CI_forecasts_csv_file_with_metadata(region_code, date)
            CI_lifecycle = result["lifecycle_file"]
            CI_direct = result["direct_file"]
            forecast_metadata = result["metadata"]
            try:
                with open(CI_lifecycle) as file:
                    lines_CI_lifecycle = file.readlines()
                with open(CI_direct) as file:
                    lines_CI_direct = file.readlines()
                CI_lifecycle_filtered = [line.split(',') for i, line in enumerate(lines_CI_lifecycle) if i>0 and i<=forecastPeriod]
                CI_direct_filtered = [line.split(',') for i, line in enumerate(lines_CI_direct) if i>0 and i<= forecastPeriod]
                for i in range(0,len(CI_lifecycle_filtered)):
                    temp_dict= {}
                    temp_dict[field_names[0]] = CI_lifecycle_filtered[i][0]
                    temp_dict[field_names[1]] = CI_lifecycle_filtered[i][1]
                    temp_dict[field_names[2]] = CI_lifecycle_filtered[i][2]
                    temp_dict[field_names[3]] = region_code
                    # CSV columns: [3]=carbon_intensity_actual, [4]=avg_carbon_intensity_forecast
                    temp_dict[field_names[4]] = float(CI_lifecycle_filtered[i][4])
                    temp_dict[field_names[5]] = float(CI_direct_filtered[i][4])
                    temp_dict[field_names[6]] = "gCO2eg/kWh"
                    final_list.append(temp_dict)
                cache.set(cache_key, final_list, 10)
            except Exception:
                final_list = []
        else:
            # build by pairing lifecycle and direct by position
            lifecycle_list = list(lifecycle_qs)
            direct_list = list(direct_qs)
            count = min(len(lifecycle_list), len(direct_list))
            for i in range(count):
                l = lifecycle_list[i]
                d = direct_list[i]
                temp_dict = {
                    field_names[0]: l.ts.isoformat(),
                    field_names[1]: (l.data or {}).get("creation_time (UTC)") or (l.data or {}).get("creation_time") or "",
                    field_names[2]: (l.data or {}).get("version") or "",
                    field_names[3]: region_code,
                    field_names[4]: float(l.value),
                    field_names[5]: float(d.value),
                    field_names[6]: (l.data or {}).get("carbon_intensity_unit", "gCO2eg/kWh")
                }
                final_list.append(temp_dict)
            cache.set(cache_key, final_list, 10)

        response = {
            "data": final_list,
            "carbon_cast_version": carbon_cast_version
        }
        
        # Add metadata if fallback was used
        if forecast_metadata and forecast_metadata.get("overall_fallback"):
            response["fallback_metadata"] = {
                "message": "Fallback date was used for one or more forecast files",
                "requested_date": date,
                "lifecycle_actual_date": forecast_metadata.get("lifecycle_actual_date"),
                "direct_actual_date": forecast_metadata.get("direct_actual_date"),
                "lifecycle_fallback": forecast_metadata.get("lifecycle_fallback"),
                "direct_fallback": forecast_metadata.get("direct_fallback")
            }
        
        # Create response with appropriate headers
        http_response = Response(response, status=status.HTTP_200_OK)
        if forecast_metadata and forecast_metadata.get("overall_fallback"):
            http_response["X-Fallback-Used"] = "true"
            http_response["X-Actual-Date-Lifecycle"] = forecast_metadata.get("lifecycle_actual_date", date)
            http_response["X-Actual-Date-Direct"] = forecast_metadata.get("direct_actual_date", date)
            
        return http_response

#6
class CarbonIntensityForecastsHistoryApiView(APIView):
    authentication_classes = authentication_classes
    permission_classes = permission_classes

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('region_code', openapi.IN_QUERY, description="Region code parameter (e.g., 'AECI').", type=openapi.TYPE_STRING),
            openapi.Parameter('date', openapi.IN_QUERY, description="Date parameter (in the format: 'YYYY-MM-DD').", type=openapi.TYPE_STRING),
            openapi.Parameter('hour', openapi.IN_QUERY, description="Hour parameter (0-23).", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: 'HTTP 200 OK - Success response description',
            400: 'HTTP 400 Bad Request - Description of possible error responses',
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
        class QueryParamsSerializer(serializers.Serializer):
            region_code = serializers.CharField(required=False)
            
        # Deserialize and validate query parameters
        query_params_serializer = QueryParamsSerializer(data=request.query_params)
        if query_params_serializer.is_valid():
            region_code = query_params_serializer.validated_data.get('region_code')
            print("printing region code", region_code)
            if region_code == 'all':
                regions = US_region_codes
            elif region_code in US_region_codes:
                regions = [region_code]
            else:
                return Response({"error": "Invalid region code parameter"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # e.g. blank region_code fails CharField validation; without this
            # branch `regions` is unbound below and the view 500s
            return Response({"error": "Invalid region code parameter"}, status=status.HTTP_400_BAD_REQUEST)
        date = request.query_params.get('date', '')
        hour = request.query_params.get('hour', None)  # Get the hour parameter
        print(f"[CarbonIntensityForecastsHistoryApiView] Requested date: {date}, hour: {hour}, Regions: {regions}")

        field_names = [
                        "UTC time", "creation_time (UTC)", "version", "region_code", "forecasted_avg_carbon_intensity_lifecycle",
                        "forecasted_avg_carbon_intensity_direct", "carbon_intensity_unit"
        ]

        final_list =[]
        # Initialize metadata tracking for all regions
        overall_metadata = None
        # Track which regions came from DB vs CSV for fallback percentage calculation
        regions_from_db = []
        regions_from_csv = []
        
        # Parse hour parameter once before the loop
        hour_int = None
        if hour is not None:
            try:
                hour_int = int(hour)
                print(f"[DEBUG CI Forecasts History] Hour filter: {hour_int}")
            except (ValueError, TypeError):
                print(f"[DEBUG CI Forecasts History] Invalid hour parameter: {hour}")
        
        for region_code in regions:
            # Include hour in cache key when hour parameter is provided
            if hour is not None:
                cache_key = f"ci_forecast_history_{region_code}_{date}_hour_{hour}"
            else:
                cache_key = f"ci_forecast_history_{region_code}_{date}"
            cached = cache.get(cache_key)
            if cached:
                final_list.extend(cached)
                regions_from_db.append(region_code)  # Cached data was originally from DB
                continue

            # filter Forecast96 by date prefix
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                print(f"[DEBUG CI Forecasts History] Successfully parsed date: {date_obj} for region: {region_code}")
            except Exception as e:
                print(f"[DEBUG CI Forecasts History] Failed to parse date '{date}': {e}")
                date_obj = None

            if date_obj:
                # Build base queries filtered by date
                lifecycle_rows = Forecast96.objects.filter(region=region_code, forecast_type__icontains='lifecycle', ts__date=date_obj)
                direct_rows = Forecast96.objects.filter(region=region_code, forecast_type__icontains='direct', ts__date=date_obj)
                
                # Apply hour filter if provided
                if hour_int is not None:
                    lifecycle_rows = lifecycle_rows.filter(ts__hour=hour_int)
                    direct_rows = direct_rows.filter(ts__hour=hour_int)
                    print(f"[DEBUG CI Forecasts History] Filtering by hour {hour_int} for region {region_code}")
                
                lifecycle_rows = lifecycle_rows.order_by('ts')
                direct_rows = direct_rows.order_by('ts')
                print(f"[DEBUG CI Forecasts History] Found {lifecycle_rows.count()} lifecycle and {direct_rows.count()} direct rows")
            else:
                # Fix: Use default date instead of returning all data
                from datetime import datetime
                default_date = datetime.now().date()
                print(f"[DEBUG CI Forecasts History] Using default date: {default_date}")
                lifecycle_rows = Forecast96.objects.filter(region=region_code, forecast_type__icontains='lifecycle', ts__date=default_date)
                direct_rows = Forecast96.objects.filter(region=region_code, forecast_type__icontains='direct', ts__date=default_date)
                
                # Apply hour filter if provided
                if hour_int is not None:
                    lifecycle_rows = lifecycle_rows.filter(ts__hour=hour_int)
                    direct_rows = direct_rows.filter(ts__hour=hour_int)
                
                lifecycle_rows = lifecycle_rows.order_by('ts')
                direct_rows = direct_rows.order_by('ts')
                print(f"[DEBUG CI Forecasts History] Found {lifecycle_rows.count()} lifecycle and {direct_rows.count()} direct rows for default date")

            if lifecycle_rows.exists() and direct_rows.exists():
                lifecycle_list = list(lifecycle_rows)
                direct_list = list(direct_rows)
                count = min(len(lifecycle_list), len(direct_list))
                temp_batch = []
                for i in range(count):
                    l = lifecycle_list[i]
                    d = direct_list[i]
                    temp_dict = {
                        field_names[0]: l.ts.isoformat(),
                        field_names[1]: l.data.get("creation_time (UTC)") or l.data.get("creation_time") or "",
                        field_names[2]: l.data.get("version") or "",
                        field_names[3]: region_code,
                        field_names[4]: l.value if hasattr(l, 'value') else None,
                        field_names[5]: d.value if hasattr(d, 'value') else None,
                        field_names[6]: l.data.get("carbon_intensity_unit", "gCO2eg/kWh")
                    }
                    temp_batch.append(temp_dict)
                    final_list.append(temp_dict)
                cache.set(cache_key, temp_batch, 10)
                if len(temp_batch) > 0:
                    regions_from_db.append(region_code)
                continue

            # Initialize metadata for this region
            region_metadata = None
            
            # fallback to CSV-based behavior if DB not populated with metadata
            result = get_CI_forecasts_csv_file_with_metadata(region_code, date)
            csv_file_l = result["lifecycle_file"]
            csv_file_d = result["direct_file"]
            region_metadata = result["metadata"]
            # Track overall metadata across all regions
            if region_metadata and region_metadata.get("overall_fallback"):
                overall_metadata = region_metadata
            try:
                with open(csv_file_l) as file:
                    lines_csv1 = file.readlines()
                with open(csv_file_d) as file:
                    lines_csv2 = file.readlines()
                filtered_data_by_date_csv1 = [line.strip().split(',') for line in lines_csv1 if line.startswith(date)]
                filtered_data_by_date_csv2 = [line.strip().split(',') for line in lines_csv2 if line.startswith(date)]
                temp_batch = []
                for i in range(0,len(filtered_data_by_date_csv1)):
                    # If hour parameter is specified, filter by hour
                    if hour is not None:
                        try:
                            # Extract hour from CSV timestamp (format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDTHH:MM:SS")
                            csv_timestamp = filtered_data_by_date_csv1[i][0]
                            if 'T' in csv_timestamp:
                                csv_hour = int(csv_timestamp.split('T')[1].split(':')[0])
                            elif ' ' in csv_timestamp:
                                csv_hour = int(csv_timestamp.split(' ')[1].split(':')[0])
                            else:
                                csv_hour = -1  # Invalid format, include the row
                            if csv_hour != hour_int and csv_hour != -1:
                                continue  # Skip this row if hour doesn't match
                        except (ValueError, IndexError, TypeError):
                            pass  # If can't parse hour, include the row
                    
                    temp_dict= {}
                    temp_dict[field_names[0]] = filtered_data_by_date_csv1[i][0]
                    temp_dict[field_names[1]] = filtered_data_by_date_csv1[i][1]
                    temp_dict[field_names[2]] = filtered_data_by_date_csv1[i][2]
                    temp_dict[field_names[3]] = region_code
                    try:
                        temp_dict[field_names[4]] = filtered_data_by_date_csv1[i][4]
                    except:
                        temp_dict[field_names[4]] = 0
                    try:
                        temp_dict[field_names[5]] = filtered_data_by_date_csv2[i][4]
                    except:
                        temp_dict[field_names[5]] = 0
                    temp_dict[field_names[6]] = "gCO2eg/kWh"
                    temp_batch.append(temp_dict)
                    final_list.append(temp_dict)
                cache.set(cache_key, temp_batch, 10)
                if len(temp_batch) > 0:
                    regions_from_csv.append(region_code)
            except Exception:
                pass

        # Calculate fallback percentage to determine if overall_fallback should be True
        # Only set overall_fallback = True when MAJORITY (>50%) of regions needed fallback
        total_regions_requested = len(regions)
        fallback_count = len(regions_from_csv)
        db_count = len(regions_from_db)
        
        # Calculate fallback percentage (regions using CSV fallback / total regions with data)
        regions_with_any_data = fallback_count + db_count
        if regions_with_any_data > 0:
            fallback_percentage = fallback_count / regions_with_any_data
        else:
            fallback_percentage = 0.0
        
        # Determine if overall_fallback should be True based on majority threshold
        should_show_fallback_warning = fallback_percentage > 0.5
        
        print(f"[DEBUG CI Forecasts History] REGION SUMMARY:")
        print(f"  - Requested regions: {total_regions_requested}")
        print(f"  - Regions with data: {regions_with_any_data} ({db_count} from DB, {fallback_count} from CSV)")
        print(f"  - Fallback percentage: {fallback_percentage:.1%} ({fallback_count}/{regions_with_any_data})")
        print(f"  - Should show fallback warning: {should_show_fallback_warning}")

        response = {
            "data": final_list,
            "carbon_cast_version": carbon_cast_version
        }
        
        # Only add fallback_metadata if MAJORITY of regions needed fallback
        if should_show_fallback_warning and overall_metadata:
            response["fallback_metadata"] = {
                "message": "Fallback date was used for majority of forecast regions",
                "requested_date": date,
                "lifecycle_actual_date": overall_metadata.get("lifecycle_actual_date"),
                "direct_actual_date": overall_metadata.get("direct_actual_date"),
                "lifecycle_fallback": overall_metadata.get("lifecycle_fallback"),
                "direct_fallback": overall_metadata.get("direct_fallback"),
                "overall_fallback": True,
                "fallback_stats": {
                    "total_regions": total_regions_requested,
                    "regions_from_db": db_count,
                    "regions_from_csv": fallback_count,
                    "fallback_percentage": round(fallback_percentage * 100, 1)
                }
            }
        
        # Create response with appropriate headers
        http_response = Response(response, status=status.HTTP_200_OK)
        if should_show_fallback_warning and overall_metadata:
            http_response["X-Fallback-Used"] = "true"
            http_response["X-Actual-Date-Lifecycle"] = overall_metadata.get("lifecycle_actual_date", date)
            http_response["X-Actual-Date-Direct"] = overall_metadata.get("direct_actual_date", date)
            
        return http_response

#7
class EnergySourcesForecastsHistoryApiView(APIView):
    authentication_classes = authentication_classes
    permission_classes = permission_classes

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('regionCode', openapi.IN_QUERY, description="Region code parameter (e.g., 'AECI').", type=openapi.TYPE_STRING),
            openapi.Parameter('date', openapi.IN_QUERY, description="Date parameter (in the format: 'YYYY-MM-DD').", type=openapi.TYPE_STRING),
            openapi.Parameter('hour', openapi.IN_QUERY, description="Hour parameter (0-23).", type=openapi.TYPE_INTEGER),
            openapi.Parameter('forecastPeriod', openapi.IN_QUERY, description="Forecast period in hours ('24h', '48h', '96h', '168h').", type=openapi.TYPE_STRING, default='24h'),
        ],
        responses={
            200: 'HTTP 200 OK - Success response description',
            400: 'HTTP 400 Bad Request - Description of possible error responses',
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

        region_code = request.query_params.get('regionCode', '')
        # Validate against known regions: region_code is used to build
        # filesystem paths in the CSV fallback, so arbitrary values are unsafe
        if region_code not in US_region_codes:
            return Response({"error": "Invalid region code parameter"}, status=status.HTTP_400_BAD_REQUEST)
        date = request.query_params.get('date', '')
        hour = request.query_params.get('hour', None)  # Get the hour parameter
        print(f"[EnergySourcesForecastsHistoryApiView] Requested date: {date}, hour: {hour}, Region: {region_code}")
        f = request.query_params.get('forecastPeriod', '24h')

        f_value = str(f)
        final_interval = int(f_value[:-1] if f_value.endswith('h') else f_value)
        forecastPeriod = int(final_interval)
        
        # Parse date and hour parameters
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d").date() if date else None
            print(f"[DEBUG EnergySourcesForecastsHistory] Successfully parsed date: {date_obj}")
        except Exception as e:
            print(f"[DEBUG EnergySourcesForecastsHistory] Failed to parse date '{date}': {e}")
            date_obj = datetime.now().date()
            
        hour_int = None
        if hour is not None:
            try:
                hour_int = int(hour)
                print(f"[DEBUG EnergySourcesForecastsHistory] Hour filter: {hour_int}")
            except (ValueError, TypeError):
                print(f"[DEBUG EnergySourcesForecastsHistory] Invalid hour parameter: {hour}")

        # Include hour in cache key when hour parameter is provided
        if hour is not None:
            cache_key = f"energy_forecast_{region_code}_{forecastPeriod}_{date}_hour_{hour}"
        else:
            cache_key = f"energy_forecast_{region_code}_{forecastPeriod}_{date}"
        # energy_metadata must exist on every path: the response code below
        # references it even when the result comes from cache
        energy_metadata = None
        cached = cache.get(cache_key)
        if cached:
            final_list = cached
        else:
            # try DB queries for energy-type forecasts, filtered by date
            energy_qs = Forecast96.objects.filter(region=region_code, forecast_type__icontains='energy')
            
            # Apply date filter if we have a valid date
            if date_obj:
                energy_qs = energy_qs.filter(ts__date=date_obj)
            
            # Apply hour filter if provided
            if hour_int is not None:
                energy_qs = energy_qs.filter(ts__hour=hour_int)
                print(f"[DEBUG EnergySourcesForecastsHistory] Filtering by hour {hour_int}")
            
            energy_qs = energy_qs.order_by('ts')[:forecastPeriod]
            
            fields = [
                "UTC time", "creation_time (UTC)", "version","region_code", "avg_coal_production_forecast", "avg_nat_gas_production_forecast",
                "avg_nuclear_production_forecast", "avg_oil_production_forecast", "avg_hydro_production_forecast", "avg_solar_production_forecast",
                "avg_wind_production_forecast", "avg_other_production_forecast"
            ]
            final_list = []

            if energy_qs.exists():
                for obj in energy_qs:
                    temp_dict = {field: "0" for field in fields}
                    temp_dict["UTC time"] = obj.ts.isoformat()
                    temp_dict["creation_time (UTC)"] = obj.data.get("creation_time (UTC)") or obj.data.get("creation_time") or ""
                    temp_dict["version"] = obj.data.get("version") or ""
                    temp_dict["region_code"] = region_code
                    # attempt to map known energy fields from JSON payload
                    for field in fields[4:]:
                        temp_dict[field] = obj.data.get(field, "0")
                    final_list.append(temp_dict)
                cache.set(cache_key, final_list, 10)
            else:
                # fallback to CSV if DB not populated with metadata
                result = get_energy_forecasts_csv_file_with_metadata(region_code, date)
                energy_forecast_csv_file = result["file"]
                energy_metadata = result["metadata"]
                try:
                    with open(energy_forecast_csv_file) as file:
                        lines_csv = file.readlines()
                    energy_forecast_filtered_file = [line.split(',') for i, line in enumerate(lines_csv) if i>0 and i<=forecastPeriod]
                    for i in range(0, len(energy_forecast_filtered_file)):
                        # If hour parameter is specified, filter by hour
                        if hour is not None:
                            try:
                                # Extract hour from CSV timestamp (format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDTHH:MM:SS")
                                csv_timestamp = energy_forecast_filtered_file[i][0]
                                if 'T' in csv_timestamp:
                                    csv_hour = int(csv_timestamp.split('T')[1].split(':')[0])
                                elif ' ' in csv_timestamp:
                                    csv_hour = int(csv_timestamp.split(' ')[1].split(':')[0])
                                else:
                                    csv_hour = -1  # Invalid format, include the row
                                if csv_hour != hour_int and csv_hour != -1:
                                    continue  # Skip this row if hour doesn't match
                            except (ValueError, IndexError, TypeError):
                                pass  # If can't parse hour, include the row
                        
                        temp_dict = {field: "0" for field in fields}
                        temp_dict["UTC time"] = energy_forecast_filtered_file[i][0]
                        temp_dict["creation_time (UTC)"] = energy_forecast_filtered_file[i][1]
                        temp_dict["version"] = energy_forecast_filtered_file[i][2]
                        temp_dict["region_code"] = region_code
                        splitlines = lines_csv[0].split(",")
                        splitlines[-1] = splitlines[-1].rstrip("\n")
                        for field in fields[4:]:
                            if field in lines_csv[0]:
                                index1 = splitlines.index(field)
                                temp_dict[field] = energy_forecast_filtered_file[i][index1]
                        final_list.append(temp_dict)
                    cache.set(cache_key, final_list, 10)
                except Exception:
                    final_list = []

        response = {
                "data": final_list,
                "carbon_cast_version": carbon_cast_version
            }
        
        # Add metadata if fallback was used
        if energy_metadata and energy_metadata.get("fallback"):
            response["fallback_metadata"] = {
                "message": "Fallback date was used for energy forecast file",
                "requested_date": date,
                "actual_date": energy_metadata.get("actual_date"),
                "fallback": energy_metadata.get("fallback")
            }
            
        # Create response with appropriate headers
        http_response = Response(response, status=status.HTTP_200_OK)
        if energy_metadata and energy_metadata.get("fallback"):
            http_response["X-Fallback-Used"] = "true"
            http_response["X-Actual-Date"] = energy_metadata.get("actual_date", date)
            
        return http_response

#8
