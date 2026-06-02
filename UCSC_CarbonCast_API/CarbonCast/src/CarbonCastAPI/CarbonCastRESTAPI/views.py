from django.shortcuts import render
import pyotp
import qrcode
import base64

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework import permissions
from rest_framework import status
from rest_framework import permissions, authentication
from django.contrib.auth import authenticate,login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.conf import settings
from django.core.cache import cache
from .models import UserModel, UserThrottleLimit, EmissionActual, Forecast96, Weather, WeatherForecast, ModelRun
from .serializers import UserSerializer
from .helper import (
    get_latest_csv_file,
    get_actual_value_file_by_date,
    get_CI_forecasts_csv_file,
    get_energy_forecasts_csv_file,
    get_actual_value_file_by_date_with_metadata,
    get_CI_forecasts_csv_file_with_metadata,
    get_energy_forecasts_csv_file_with_metadata
)
import os
from .consts import carbon_cast_version, authentication_classes, permission_classes, US_region_codes
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime
import time
def check_throttle_limit(user):
    # Rate limiting disabled - always allow requests
    return True

# 1: 
class CarbonIntensityApiView(APIView):
  
    print(authentication_classes, permission_classes)
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
                 "UTC time", "creation_time (UTC)", "version", "region_code", "carbon_intensity_avg_lifecycle", 
                 "carbon_intensity_avg_direct", "cabon_intensity_unit"
                 ]
        
            final_list=[]
        
            for region_code in regions:
                # Try cache first (short lived)
                cache_key = f"ci_latest_{region_code}"
                cached = cache.get(cache_key)
                if cached:
                    final_list.append(cached)
                    continue

                # Query latest emission row for region
                obj = EmissionActual.objects.filter(region=region_code).order_by('-ts').first()
                if not obj:
                    # fallback to CSV if DB has no data (preserve compatibility)
                    try:
                        csv_file1, csv_file2 = get_latest_csv_file(region_code)
                        with open(csv_file1) as f1:
                            last = None
                            for line in f1:
                                last = line
                            values_csv1 = last.split(',') if last else []
                        with open(csv_file2) as f2:
                            last = None
                            for line in f2:
                                last = line
                            values_csv2 = last.split(',') if last else []
                        temp_dict = {
                            fields[0]: values_csv1[1],
                            fields[1]: values_csv1[2],
                            fields[2]: values_csv1[3],
                            fields[3]: region_code,
                            fields[4]: float(values_csv1[4]) if len(values_csv1) > 4 else 0,
                            fields[5]: float(values_csv2[4]) if len(values_csv2) > 4 else 0,
                            fields[6]: "gCO2eg/kWh"
                        }
                        final_list.append(temp_dict)
                        cache.set(cache_key, temp_dict, 10)
                        continue
                    except Exception:
                        continue

                temp_dict = {
                    fields[0]: obj.ts.isoformat(),
                    fields[1]: obj.data.get("creation_time (UTC)") or obj.data.get("creation_time") or "",
                    fields[2]: obj.data.get("version") or "",
                    fields[3]: region_code,
                    fields[4]: float(obj.lifecycle) if obj.lifecycle is not None else float(
                        obj.data.get("carbon_intensity_avg_lifecycle")
                        or obj.data.get("carbon_intensity")
                        or obj.data.get("lifecycle")
                        or obj.data.get("value")
                        or 0
                    ),
                    fields[5]: float(obj.direct) if obj.direct is not None else float(
                        obj.data.get("carbon_intensity_avg_direct")
                        or obj.data.get("carbon_intensity")
                        or obj.data.get("direct")
                        or obj.data.get("value")
                        or 0
                    ),
                    fields[6]: obj.data.get("carbon_intensity_unit", "gCO2eg/kWh")
                }
                cache.set(cache_key, temp_dict, 10)
                final_list.append(temp_dict)
                
            response = {
                "data": final_list
            }
            return Response(response, status=status.HTTP_200_OK)
            final_list.append(temp_dict)
            
        response = {
            "data": final_list,
            "carbon_cast_version": carbon_cast_version
        }
        return Response(response, status=status.HTTP_200_OK)
        
#2    
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
            

#3 
class CarbonIntensityHistoryApiView(APIView):
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

    def get(self, request, *args, **kwargs): #TODO:#focus on this
        if permissions.AllowAny not in permission_classes:
            user = request.user
            print("User:",user)
            if not check_throttle_limit(user):
                return Response({
                    "status": "fail",
                    "message": "Throttle limit reached",
                    "carbon_cast_version": carbon_cast_version
                }, status=status.HTTP_429_TOO_MANY_REQUESTS, headers={'Retry-After': 86400})
        #from here
        class QueryParamsSerializer(serializers.Serializer):
            region_code = serializers.CharField(required=False)

        # Deserialize and validate query parameters
        query_params_serializer = QueryParamsSerializer(data=request.query_params)
        if query_params_serializer.is_valid():
            region_code = query_params_serializer.validated_data.get('region_code')
            
            if region_code == 'all':
                regions = US_region_codes
                print(f"[DEBUG] Requesting ALL regions. Total available: {len(US_region_codes)}")
                print(f"[DEBUG] All regions: {US_region_codes}")
            elif region_code in US_region_codes:
                regions = [region_code]
            else:
                return Response({"error": "Invalid region code parameter"}, status=status.HTTP_400_BAD_REQUEST)
        date = request.query_params.get('date', '')
        hour = request.query_params.get('hour', None)  # Get the hour parameter
        start_time = time.time()
        print(f"[PERF START] CarbonIntensityHistoryApiView for date: {date}, hour: {hour}, Requested regions: {len(regions)} regions")
                  

        field_names = [
                        "UTC time", "creation_time (UTC)", "version", "region_code", "carbon_intensity_avg_lifecycle",
                        "carbon_intensity_avg_direct", "carbon_intensity_unit"
        ]

        final_list =[]
        # Initialize metadata tracking for all regions
        overall_metadata = None
        regions_with_data = []
        regions_without_data = []
        regions_from_csv = []
        regions_from_db = []
        
        # Parse date once before the loop
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date, "%Y-%m-%d").date() if date else None
            print(f"[DEBUG] Successfully parsed date: {date_obj}")
        except Exception as e:
            print(f"[DEBUG] Failed to parse date '{date}': {e}, using default date")
            from datetime import datetime
            date_obj = datetime.now().date()  # Default to today
        
        # Prepare hour filter
        hour_int = None
        if hour is not None:
            try:
                hour_int = int(hour)
                print(f"[DEBUG] Hour filter: {hour_int}")
            except (ValueError, TypeError):
                print(f"[DEBUG] Invalid hour parameter: {hour}")
        
        # OPTIMIZATION: Batch query all regions at once when possible
        if len(regions) > 1 and date_obj:  # Batch for any multiple regions
            print(f"[DEBUG] Using OPTIMIZED BATCH QUERY for {len(regions)} regions")
            
            # Build optimized batch query - only fetch needed fields
            base_query = EmissionActual.objects.filter(
                region__in=regions,
                ts__date=date_obj
            ).only('region', 'ts', 'lifecycle', 'direct', 'data')  # Only fetch needed fields
            
            if hour_int is not None:
                base_query = base_query.filter(ts__hour=hour_int)
            
            # Use values_list with named=True for faster processing
            batch_results = base_query.order_by('region', 'ts').values_list(
                'region', 'ts', 'lifecycle', 'direct', 'data', named=True
            )
            
            # Group results by region using iterator for memory efficiency
            from collections import defaultdict
            region_data_map = defaultdict(list)
            
            # Process in chunks to avoid loading all into memory at once
            for row in batch_results.iterator(chunk_size=1000):
                region_data_map[row.region].append(row)
            
            print(f"[DEBUG] Batch query found data for {len(region_data_map)} regions")
            
            # Process each region's data
            for region_code in regions:
                # Check cache first
                if hour_int is not None:
                    cache_key = f"ci_history_{region_code}_{date}_hour_{hour}"
                else:
                    cache_key = f"ci_history_{region_code}_{date}"
                
                cached = cache.get(cache_key)
                if cached:
                    print(f"[DEBUG] Cache hit for {cache_key}, adding {len(cached)} items")
                    final_list.extend(cached)
                    regions_with_data.append(region_code)
                    continue
                
                # Use batch query results
                if region_code in region_data_map:
                    temp_batch = []
                    for row_data in region_data_map[region_code]:
                        # Faster processing with named tuple access
                        data_dict = row_data.data or {}
                        temp_dict = {
                            field_names[0]: row_data.ts.isoformat(),
                            field_names[1]: data_dict.get("creation_time (UTC)", "") or data_dict.get("creation_time", ""),
                            field_names[2]: data_dict.get("version", ""),
                            field_names[3]: region_code,
                            field_names[4]: float(row_data.lifecycle) if row_data.lifecycle is not None else 0.0,
                            field_names[5]: float(row_data.direct) if row_data.direct is not None else 0.0,
                            field_names[6]: data_dict.get("carbon_intensity_unit", "gCO2eg/kWh")
                        }
                        temp_batch.append(temp_dict)
                        final_list.append(temp_dict)
                    
                    cache.set(cache_key, temp_batch, 10)
                    print(f"[DEBUG] Batch processed {len(temp_batch)} items for region {region_code}")
                    if len(temp_batch) > 0:
                        regions_from_db.append(region_code)
                        regions_with_data.append(region_code)
                    else:
                        regions_without_data.append(region_code)
                else:
                    # No data in batch results, try CSV fallback
                    print(f"[DEBUG] No DB data for region {region_code}, trying CSV fallback")
                    regions_without_data.append(region_code)
                    # CSV fallback code will be same as before
                    result = get_actual_value_file_by_date_with_metadata(region_code, date)
                    csv_file_a = result["lifecycle_file"]
                    csv_file_b = result["direct_file"]
                    region_metadata = result["metadata"]
                    if region_metadata and region_metadata.get("overall_fallback"):
                        overall_metadata = region_metadata
                    try:
                        with open(csv_file_a) as file:
                            lines_csv1 = file.readlines()
                        with open(csv_file_b) as file:
                            lines_csv2 = file.readlines()
                        values_csv1 = [line.strip().split(',') for line in lines_csv1]
                        values_csv2 = [line.strip().split(',') for line in lines_csv2]
                        temp_batch = []
                        for i in range(1, len(values_csv1)):
                            if hour is not None:
                                try:
                                    hour_int = int(hour)
                                    csv_timestamp = values_csv1[i][1]
                                    if ' ' in csv_timestamp:
                                        csv_hour = int(csv_timestamp.split(' ')[1].split(':')[0])
                                        if csv_hour != hour_int:
                                            continue
                                except (ValueError, IndexError, TypeError):
                                    pass
                            
                            temp_dict= {}
                            temp_dict[field_names[0]] = values_csv1[i][1]
                            temp_dict[field_names[1]] = values_csv1[i][2]
                            temp_dict[field_names[2]] = values_csv1[i][3]
                            temp_dict[field_names[3]] = region_code
                            temp_dict[field_names[4]] = (values_csv1[i][4])
                            temp_dict[field_names[5]] = (values_csv2[i][4])
                            temp_dict[field_names[6]] = "gCO2eg/kWh"
                            temp_batch.append(temp_dict)
                            final_list.append(temp_dict)
                        cache.set(cache_key, temp_batch, 10)
                        if len(temp_batch) > 0:
                            regions_from_csv.append(region_code)
                    except Exception as e:
                        print(f"[DEBUG] Error reading CSV for region {region_code}: {e}")
        else:
            # Sequential processing for single region or when no date
            print(f"[DEBUG] Using SEQUENTIAL processing for {len(regions)} regions")
            for region_code in regions:
                # Include hour in cache key when hour parameter is provided
                if hour is not None:
                    cache_key = f"ci_history_{region_code}_{date}_hour_{hour}"
                else:
                    cache_key = f"ci_history_{region_code}_{date}"
                
                cached = cache.get(cache_key)
                if cached:
                    print(f"[DEBUG] Cache hit for {cache_key}, adding {len(cached)} items")
                    final_list.extend(cached)
                    continue

                if date_obj:
                    # Optimize query with only() to fetch needed fields
                    base_query = EmissionActual.objects.filter(
                        region=region_code,
                        ts__date=date_obj
                    ).only('ts', 'lifecycle', 'direct', 'data')
                    
                    # Check if hour parameter is provided
                    if hour_int is not None:
                        # Filter by both date AND hour when hour is provided
                        rows = base_query.filter(ts__hour=hour_int).order_by('ts')
                        print(f"[DEBUG] Querying for region {region_code} on date {date_obj} hour {hour_int}")
                    else:
                        # No hour parameter, return all hours for the date
                        rows = base_query.order_by('ts')
                        print(f"[DEBUG] Querying for region {region_code} on date {date_obj} (all hours)")
                else:
                    # Default to today's date if no date provided
                    from datetime import datetime
                    default_date = datetime.now().date()
                    print(f"[DEBUG] Using default date: {default_date}")
                    rows = EmissionActual.objects.filter(region=region_code, ts__date=default_date).order_by('ts')
                    print(f"[DEBUG] Found {rows.count()} rows for default date")

                # Initialize metadata for this region
                region_metadata = None
                
                if not rows.exists():
                    print(f"[DEBUG] No DB data for region {region_code} on {date_obj or 'no valid date'}")
                    regions_without_data.append(region_code)
                    # fallback to CSV-compatible behavior with metadata
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
                        values_csv2 = [line.strip().split(',') for line in lines_csv2]
                        # Create temp_batch for this region only
                        temp_batch = []
                        for i in range(1, len(values_csv1)):
                            # If hour parameter is specified, filter by hour
                            if hour is not None:
                                try:
                                    hour_int = int(hour)
                                    # Extract hour from CSV timestamp (format: "YYYY-MM-DD HH:MM:SS")
                                    csv_timestamp = values_csv1[i][1]
                                    if ' ' in csv_timestamp:
                                        csv_hour = int(csv_timestamp.split(' ')[1].split(':')[0])
                                        if csv_hour != hour_int:
                                            continue  # Skip this row if hour doesn't match
                                except (ValueError, IndexError, TypeError):
                                    pass  # If can't parse hour, include the row
                            
                            temp_dict= {}
                            temp_dict[field_names[0]] = values_csv1[i][1]
                            temp_dict[field_names[1]] = values_csv1[i][2]
                            temp_dict[field_names[2]] = values_csv1[i][3]
                            temp_dict[field_names[3]] = region_code
                            temp_dict[field_names[4]] = (values_csv1[i][4])
                            temp_dict[field_names[5]] = (values_csv2[i][4])
                            temp_dict[field_names[6]] = "gCO2eg/kWh"
                            temp_batch.append(temp_dict)
                            final_list.append(temp_dict)
                        # Cache only this region's data, not the entire final_list
                        cache.set(cache_key, temp_batch, 10)
                        print(f"[DEBUG] Added {len(temp_batch)} items from CSV for region {region_code} (hour filter: {hour})")
                        if len(temp_batch) > 0:
                            regions_from_csv.append(region_code)
                        continue
                    except Exception as e:
                        print(f"[DEBUG] Error reading CSV for region {region_code}: {e}")
                        continue

                temp_batch = []
                # Use iterator for memory efficiency
                for obj in rows.iterator(chunk_size=100):
                    data_dict = obj.data or {}
                    temp_dict = {
                        field_names[0]: obj.ts.isoformat(),
                        field_names[1]: data_dict.get("creation_time (UTC)", "") or data_dict.get("creation_time", ""),
                        field_names[2]: data_dict.get("version", ""),
                        field_names[3]: region_code,
                        field_names[4]: float(obj.lifecycle) if obj.lifecycle is not None else 0.0,
                        field_names[5]: float(obj.direct) if obj.direct is not None else 0.0,
                        field_names[6]: data_dict.get("carbon_intensity_unit", "gCO2eg/kWh")
                    }
                    temp_batch.append(temp_dict)
                    final_list.append(temp_dict)
                
                # Cache with hour-specific key when hour parameter is provided
                if hour is not None:
                    cache_key = f"ci_history_{region_code}_{date}_hour_{hour}"
                else:
                    cache_key = f"ci_history_{region_code}_{date}"
                
                cache.set(cache_key, temp_batch, 10)
                print(f"[DEBUG] Cached {len(temp_batch)} items for region {region_code} with key: {cache_key}")
                if len(temp_batch) > 0:
                    regions_from_db.append(region_code)
                    regions_with_data.append(region_code)
                else:
                    regions_without_data.append(region_code)
        
        total_time = (time.time() - start_time) * 1000
        expected_items = len(regions) * (1 if hour is not None else 24)
        regions_responded = len(set(regions_with_data + regions_from_csv))
        
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
        # overall_fallback = True only if more than 50% of regions needed fallback
        should_show_fallback_warning = fallback_percentage > 0.5
        
        print(f"[PERF END] Total API time: {total_time:.2f}ms for {len(final_list)} items")
        print(f"[PERF] Expected {expected_items} items (from {len(regions)} regions), got {len(final_list)} items")
        print(f"[DEBUG] REGION SUMMARY:")
        print(f"  - Requested regions: {total_regions_requested}")
        print(f"  - Regions with data: {regions_responded} ({db_count} from DB, {fallback_count} from CSV)")
        print(f"  - Regions without any data: {len(regions_without_data)}")
        print(f"  - Fallback percentage: {fallback_percentage:.1%} ({fallback_count}/{regions_with_any_data})")
        print(f"  - Should show fallback warning: {should_show_fallback_warning}")
        if len(regions_without_data) > 0:
            print(f"  - Missing regions: {regions_without_data[:10]}{'...' if len(regions_without_data) > 10 else ''}")
        if total_time > 5000:
            print(f"[PERF ALERT] 🔴 API response time exceeded 5 seconds: {total_time:.2f}ms")
        elif total_time > 1000:
            print(f"[PERF WARNING] 🟡 API response time exceeded 1 second: {total_time:.2f}ms")
        
        # Build response with metadata if fallback was used
        response = {
            "data": final_list,
            "carbon_cast_version": carbon_cast_version,
        }
        
        # Only add fallback_metadata if MAJORITY of regions needed fallback
        # This prevents misleading warnings when only 1-2 out of 58 regions use fallback
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

#4  
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
                    temp_dict[field_names[4]] = float(CI_lifecycle_filtered[i][3])
                    temp_dict[field_names[5]] = float(CI_direct_filtered[i][3])
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
            # Initialize metadata
            energy_metadata = None
            
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
    

class UserAuthenticationEnforcedView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        responses={
            200: 'HTTP 200 OK - Success response description',
        }
    )

    def get(self, request, *args, **kwargs):
        response = {
            "Authentication required": settings.REQUIRES_AUTH,
            "carbon_cast_version": carbon_cast_version
        }
        return Response(response, status=status.HTTP_200_OK)
    

class LogoutAPIView(APIView):
    permission_classes = permission_classes
    throttle_classes = []

    @swagger_auto_schema(
        responses={
            200: 'HTTP 200 OK - Success response description',
        }
    )

    def post(self, request, *args, **kwargs):
        logout(request)
        response = {
            "logged_out": True,
            "carbon_cast_version": carbon_cast_version
        }
        return Response(response, status=status.HTTP_200_OK)


class SignUpApiView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer
    queryset = UserModel.objects.all()
    throttle_classes = []

    print(settings.DEFAULT_THROTTLE_LIMIT, settings.EXTENDED_THROTTLE_LIMIT)

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={
            201: 'HTTP 201 Created - User successfully registered',
            400: 'HTTP 400 Bad Request - Invalid input data',
            409: 'HTTP 409 Conflict - User with the same email already exists',
        },
    )

    def post(self, request):
        """
        Register a new user.

        :param request: The HTTP POST request with user registration data.
        :return: User registration response.
        """
        serializer = self.serializer_class(data=request.data)
        
        if serializer.is_valid():
            # serializer = self.serializer_class(data=request.data)
            try:
                user = serializer.save()            
                username = request.data.get('username')
                user.username = username
                user.save()

                if username.startswith('Test'):
                    throttle_limit_value = settings.EXTENDED_THROTTLE_LIMIT
                    throttle_limit = UserThrottleLimit(user=user, throttle_limit=throttle_limit_value)
                    throttle_limit.save()
                else:
                    throttle_limit_value = settings.DEFAULT_THROTTLE_LIMIT
                    throttle_limit = UserThrottleLimit(user=user, throttle_limit=throttle_limit_value)
                    throttle_limit.save()
                    
                print(f"Username: {user.username}")
                print(f"Throttle Limit: {throttle_limit.throttle_limit}")

                otp_base32 = pyotp.random_base32()
                email = request.data.get('email').lower()
                # username = request.data.get('username')
                password = request.data.get('password')
                otp_auth_url = pyotp.totp.TOTP(otp_base32).provisioning_uri(
                    name=email, issuer_name="carboncast.com")
                user = authenticate(username=username, password=password)
                user.email = email
                user.otp_auth_url = otp_auth_url
                user.otp_base32 = otp_base32
                user.otp_verified = False
                user.password_checked = True
                
                qrcode_filename = "qr_auth.png"
                qrcode.make(user.otp_auth_url).save(qrcode_filename)
                with open(qrcode_filename, "rb") as image_file:
                    qrcode_image = base64.b64encode(image_file.read()).decode('utf-8')

                user.otp_qrcode_image = qrcode_image
                user.save()

                # code to unpack the image on the frontend
                # from PIL import Image
                # from io import BytesIO
                # im = Image.open(BytesIO(base64.b64decode(qrcode_image.encode('utf-8'))))
                # print(im)
                # im.save('image1.png', 'PNG')

                return Response({
                    "status": "success", 
                    'base32': otp_base32, 
                    "otpauth_url": otp_auth_url, 
                    "otp_qrcode_image": qrcode_image,
                    "carbon_cast_version": carbon_cast_version
                    }, 
                    status=status.HTTP_201_CREATED
                )
                
            except Exception as e:
                print(f"{e}")
                return Response({
                    "status": "fail", 
                    "message": "User with that email already exists", 
                    "carbon_cast_version": carbon_cast_version
                    }, 
                    status=status.HTTP_409_CONFLICT
                )
        else:
            return Response({
                "status": "fail", 
                "message": serializer.errors, 
                "carbon_cast_version": carbon_cast_version
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )


class SignInApiView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer
    # queryset = UserModel.objects.all()
    throttle_classes=[]

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={
            200: 'HTTP 200 OK - User successfully authenticated',
            400: 'HTTP 400 Bad Request - Incorrect email or password',
        },
    )

    def post(self, request):
        """
        Authenticate a user.

        :param request: The HTTP POST request with user authentication data.
        :return: User authentication response.
        """
        # print("Request data: ", request.data)
        data = request.data
        # email = data.get('email')
        username = data.get('username')
        password = data.get('password')

        user = authenticate(username=username, password=password)
        # print(user, username, email, password)
        if user is None:
            return Response({
                "status": "fail", 
                "message": "Incorrect email or password"
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(password):
            return Response({
                "status": "fail", 
                "message": "Incorrect email or password"
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(user)
        user.otp_verified = False
        user.password_checked = True
        
        qrcode_filename = "qr_auth.png"
        qrcode.make(user.otp_auth_url).save(qrcode_filename)
        with open(qrcode_filename, "rb") as image_file:
            qrcode_image = base64.b64encode(image_file.read()).decode('utf-8')
        user.otp_qrcode_image = qrcode_image

        return Response({
            "status": "success", 
            "user": serializer.data, 
            "otp_qrcode_image": qrcode_image,
            "carbon_cast_version": carbon_cast_version
        })


class VerifyOTP(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer
    queryset = UserModel.objects.all()
    throttle_classes=[]

    @swagger_auto_schema(
        request_body=serializers.Serializer(
            {
                "username": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="The username of the user to verify OTP for.",
                ),
                "token": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="The OTP token to be verified.",
                ),
            }
        ),
        responses={
            200: 'HTTP 200 OK - OTP verification successful',
            400: 'HTTP 400 Bad Request - OTP verification failed',
            403: 'HTTP 403 Forbidden - User needs to log in first',
            404: 'HTTP 404 Not Found - User with the given username not found',
        },
    )

    def post(self, request):
        """
        Verify OTP for a user.

        :param request: The HTTP POST request with OTP verification data.
        :return: OTP verification response.
        """
        message = "Token is invalid or user doesn't exist"
        data = request.data
        username = data.get('username', None)
        otp_token = data.get('token', None)
        user = UserModel.objects.filter(username=username).first()
        if user == None:
            return Response({
                "status": "fail", 
                "message": f"No user with username: {username} found"
                }, 
                status=status.HTTP_404_NOT_FOUND
            )

        if not user.password_checked:
            return Response({
                "status": "fail", 
                "message": f"You need to login first"
                }, 
                status=status.HTTP_403_FORBIDDEN
            )

        totp = pyotp.TOTP(user.otp_base32)
        if not totp.verify(otp_token):
            return Response({
                "status": "fail", 
                "message": message, 
                "carbon_cast_version": carbon_cast_version
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
        user.otp_enabled = True
        user.otp_verified = True
        user.save()
        login(request, user)
        
        serializer = self.serializer_class(user)

        return Response({
            'otp_verified': True,
            "user": serializer.data,
            "carbon_cast_version": carbon_cast_version
        })


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

