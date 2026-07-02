from ._base import *


class EnergySourcesApiView(APIView):
    authentication_classes = authentication_classes
    permission_classes = permission_classes

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('region_code', openapi.IN_QUERY, description="Region code parameter (e.g., 'AECI').", type=openapi.TYPE_STRING),
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

        # Define the serializer for validating query parameters
        class QueryParamsSerializer(serializers.Serializer):
            region_code = serializers.CharField(required=False)

        # Deserialize and validate query parameters
        query_params_serializer = QueryParamsSerializer(data=request.query_params)
        if query_params_serializer.is_valid():
            region_code = query_params_serializer.validated_data.get('region_code')
            
            if region_code == 'all':
                regions = US_region_codes
            elif region_code in US_region_codes:
                regions = [region_code]
            else:
                return Response({"error": "Invalid region code parameter"}, status=status.HTTP_400_BAD_REQUEST)

            fields = [
                    "UTC time", "creation_time (UTC)", "version", "region_code", "coal", "nat_gas", "nuclear",
                    "oil", "hydro", "solar", "wind", "other"
                ]

            response = {"data": [], "carbon_cast_version": carbon_cast_version}  

            for region_code in regions:
                cache_key = f"energy_latest_{region_code}"
                cached = cache.get(cache_key)
                if cached:
                    response["data"].append(cached)
                    continue

                obj = EmissionActual.objects.filter(region=region_code).order_by('-ts').first()
                if not obj:
                    # fallback to CSV
                    try:
                        csv_file1, csv_file2 = get_latest_csv_file(region_code)
                        with open(csv_file1) as file:
                            header = file.readline().strip()
                            columns = header.split(',')
                            line = None
                            for row in file:
                                line = row.strip().split(',')
                        response_data = {}
                        for field in fields:
                            if field in columns:
                                index = columns.index(field)
                                value = line[index].strip() if index < len(line) else "0"
                                response_data[field] = value
                            elif field == "region_code":
                                response_data[field] = region_code
                            else:
                                response_data[field] = "0"
                        response["data"].append(response_data)
                        cache.set(cache_key, response_data, 10)
                        continue
                    except Exception:
                        continue

                # Use stored JSON data for energy breakdown when available
                response_data = {}
                for field in fields:
                    if field == "UTC time":
                        response_data[field] = obj.ts.isoformat()
                    elif field == "creation_time (UTC)":
                        response_data[field] = obj.data.get("creation_time (UTC)") or obj.data.get("creation_time") or ""
                    elif field == "version":
                        response_data[field] = obj.data.get("version") or ""
                    elif field == "region_code":
                        response_data[field] = region_code
                    else:
                        # try to read energy source fields from stored JSON
                        response_data[field] = obj.data.get(field, "0")
                cache.set(cache_key, response_data, 10)
                response["data"].append(response_data)

            return Response(response, status=status.HTTP_200_OK)

        # invalid query params (e.g. blank region_code): without this branch
        # the view returns None and Django raises a 500
        return Response({"error": "Invalid region code parameter"}, status=status.HTTP_400_BAD_REQUEST)


#3 
class EnergySourcesHistoryApiView(APIView):
    authentication_classes = authentication_classes
    permission_classes = permission_classes

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('region_code', openapi.IN_QUERY, description="Region code parameter (e.g., 'AECI').", type=openapi.TYPE_STRING),
            openapi.Parameter('date', openapi.IN_QUERY, description="Date parameter (in the format: 'YYYY-MM-DD').", type=openapi.TYPE_STRING),
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
        
        query_params_serializer = QueryParamsSerializer(data=request.query_params)
        if query_params_serializer.is_valid():
            region_code = query_params_serializer.validated_data.get('region_code')
            
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
        print(f"[EnergySourcesHistoryApiView] Requested date: {date}, hour: {hour}, Regions: {regions}")
        
        fields = [
            "UTC time", "creation_time (UTC)", "version", "region_code", "coal", "nat_gas", "nuclear",
            "oil", "hydro", "solar", "wind", "other"
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
                print(f"[DEBUG EnergySourcesHistory] Hour filter: {hour_int}")
            except (ValueError, TypeError):
                print(f"[DEBUG EnergySourcesHistory] Invalid hour parameter: {hour}")
        
        for region_code in regions:
            # Include hour in cache key when hour parameter is provided
            if hour is not None:
                cache_key = f"energy_history_{region_code}_{date}_hour_{hour}"
            else:
                cache_key = f"energy_history_{region_code}_{date}"
            cached = cache.get(cache_key)
            if cached:
                final_list.extend(cached)
                regions_from_db.append(region_code)  # Cached data was originally from DB
                continue

            try:
                from datetime import datetime
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                print(f"[DEBUG EnergySourcesHistory] Successfully parsed date: {date_obj} for region: {region_code}")
            except Exception as e:
                print(f"[DEBUG EnergySourcesHistory] Failed to parse date '{date}': {e}")
                date_obj = None

            if date_obj:
                # Build base query
                base_query = EmissionActual.objects.filter(region=region_code, ts__date=date_obj)
                
                # Apply hour filter if provided
                if hour_int is not None:
                    rows = base_query.filter(ts__hour=hour_int).order_by('ts')
                    print(f"[DEBUG EnergySourcesHistory] Found {rows.count()} rows for {region_code} on {date_obj} hour {hour_int}")
                else:
                    rows = base_query.order_by('ts')
                    print(f"[DEBUG EnergySourcesHistory] Found {rows.count()} rows for {region_code} on {date_obj} (all hours)")
            else:
                # Fix: Use default date instead of returning all data
                from datetime import datetime
                default_date = datetime.now().date()
                print(f"[DEBUG EnergySourcesHistory] Using default date: {default_date}")
                base_query = EmissionActual.objects.filter(region=region_code, ts__date=default_date)
                
                # Apply hour filter if provided
                if hour_int is not None:
                    rows = base_query.filter(ts__hour=hour_int).order_by('ts')
                else:
                    rows = base_query.order_by('ts')
                print(f"[DEBUG EnergySourcesHistory] Found {rows.count()} rows for default date")

            # Initialize metadata for this region
            region_metadata = None
            
            if not rows.exists():
                # fallback to CSV behavior with metadata
                result = get_actual_value_file_by_date_with_metadata(region_code, date)
                csv_file_a = result["lifecycle_file"]
                csv_file_b = result["direct_file"]
                region_metadata = result["metadata"]
                # Track overall metadata across all regions
                if region_metadata and region_metadata.get("overall_fallback"):
                    overall_metadata = region_metadata
                try:
                    with open(csv_file_a) as file:
                        lines_csv1 = file.readlines()
                    with open(csv_file_b) as file:
                        lines_csv2 = file.readlines()
                    values_csv1 = [line.strip().split(',') for line in lines_csv1]
                    temp_batch = []
                    for i in range(1, len(values_csv1)):
                        # If hour parameter is specified, filter by hour
                        if hour is not None:
                            try:
                                # Extract hour from CSV timestamp (format: "YYYY-MM-DD HH:MM:SS")
                                csv_timestamp = values_csv1[i][1]
                                if ' ' in csv_timestamp:
                                    csv_hour = int(csv_timestamp.split(' ')[1].split(':')[0])
                                    if csv_hour != hour_int:
                                        continue  # Skip this row if hour doesn't match
                            except (ValueError, IndexError, TypeError):
                                pass  # If can't parse hour, include the row
                        
                        temp_dict = {field: "0" for field in fields}
                        temp_dict["UTC time"] = values_csv1[i][1]
                        temp_dict["creation_time (UTC)"] = values_csv1[i][2]
                        temp_dict["version"] = values_csv1[i][3]
                        temp_dict["region_code"] = region_code

                        for field in fields[2:]:
                            if field in values_csv1[0]:
                                index = values_csv1[0].index(field)
                                temp_dict[field] = values_csv1[i][index]

                        temp_batch.append(temp_dict)
                        final_list.append(temp_dict)
                    cache.set(cache_key, temp_batch, 10)
                    if len(temp_batch) > 0:
                        regions_from_csv.append(region_code)
                    continue
                except Exception:
                    continue

            temp_batch = []
            for obj in rows:
                temp_dict = {field: "0" for field in fields}
                temp_dict["UTC time"] = obj.ts.isoformat()
                temp_dict["creation_time (UTC)"] = obj.data.get("creation_time (UTC)") or obj.data.get("creation_time") or ""
                temp_dict["version"] = obj.data.get("version") or ""
                temp_dict["region_code"] = region_code
                for field in fields[4:]:
                    temp_dict[field] = obj.data.get(field, "0")
                temp_batch.append(temp_dict)
                final_list.append(temp_dict)
            cache.set(cache_key, temp_batch, 10)
            if len(temp_batch) > 0:
                regions_from_db.append(region_code)

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
        
        print(f"[DEBUG EnergySourcesHistory] REGION SUMMARY:")
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
                "message": "Fallback date was used for majority of regions",
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

#5
