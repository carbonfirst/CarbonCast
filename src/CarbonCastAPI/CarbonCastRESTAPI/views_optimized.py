# Optimized API view for sub-second carbon intensity loading
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from django.core.cache import cache
from .models import EmissionActual
from .consts import US_region_codes
import time

class CarbonIntensityHistoryOptimizedView(APIView):
    """
    Optimized API for single-hour carbon intensity data
    Target: <500ms response time for 58 regions
    """
    
    def get(self, request, *args, **kwargs):
        start_time = time.time()
        
        # Parse parameters
        region_code = request.query_params.get('region_code', 'all')
        date = request.query_params.get('date', '')
        hour = request.query_params.get('hour')
        
        print(f"[PERF START] Optimized API: date={date}, hour={hour}, regions={region_code}")
        
        if region_code == 'all':
            regions = US_region_codes
        elif region_code in US_region_codes:
            regions = [region_code]
        else:
            return Response({"error": "Invalid region code"}, status=status.HTTP_400_BAD_REQUEST)
        
        # OPTIMIZATION 1: Single database query instead of 58
        if hour is not None:
            cache_key = f"ci_optimized_{date}_{hour}_all"
            cached = cache.get(cache_key)
            
            if cached:
                print(f"[PERF] Cache hit: {(time.time() - start_time)*1000:.2f}ms")
                return Response({"data": cached}, status=status.HTTP_200_OK)
            
            try:
                # Parse date and hour
                from datetime import datetime, timedelta
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                hour_int = int(hour)
                
                # Single optimized query for all regions at specific hour
                start_datetime = datetime.combine(date_obj, datetime.min.time()) + timedelta(hours=hour_int)
                end_datetime = start_datetime + timedelta(hours=1)
                
                query_start = time.time()
                
                # CRITICAL: Single query for all regions and specific hour
                rows = EmissionActual.objects.filter(
                    region__in=regions,
                    ts__gte=start_datetime,
                    ts__lt=end_datetime
                ).select_related().order_by('region', 'ts')
                
                query_time = (time.time() - query_start) * 1000
                print(f"[PERF DB] Single query: {query_time:.2f}ms for {rows.count()} rows")
                
                # Build response efficiently
                final_list = []
                for obj in rows:
                    final_list.append({
                        "UTC time": obj.ts.isoformat(),
                        "creation_time (UTC)": obj.data.get("creation_time (UTC)", ""),
                        "version": obj.data.get("version", ""),
                        "region_code": obj.region,
                        "carbon_intensity_avg_lifecycle": obj.lifecycle or 0,
                        "carbon_intensity_avg_direct": obj.direct or 0,
                        "carbon_intensity_unit": "gCO2eg/kWh"
                    })
                
                # Cache for 5 minutes (historical data doesn't change)
                cache.set(cache_key, final_list, 300)
                
                total_time = (time.time() - start_time) * 1000
                print(f"[PERF END] Optimized API: {total_time:.2f}ms for {len(final_list)} items")
                
                return Response({
                    "data": final_list,
                    "metadata": {
                        "optimized": True,
                        "query_time_ms": query_time,
                        "total_time_ms": total_time,
                        "cache_key": cache_key
                    }
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                print(f"[PERF ERROR] Optimized query failed: {e}")
                # Fallback to original implementation
                pass
        
        # If no hour specified or optimization failed, return error
        return Response(
            {"error": "Hour parameter required for optimized endpoint"}, 
            status=status.HTTP_400_BAD_REQUEST
        )


class CarbonIntensityBulkOptimizedView(APIView):
    """
    Optimized bulk API for all 24 hours
    Used for background loading after initial hour loads
    """
    
    def get(self, request, *args, **kwargs):
        start_time = time.time()
        
        region_code = request.query_params.get('region_code', 'all')
        date = request.query_params.get('date', '')
        
        if region_code == 'all':
            regions = US_region_codes
        else:
            return Response({"error": "Bulk endpoint only supports region_code=all"}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        cache_key = f"ci_bulk_{date}_all"
        cached = cache.get(cache_key)
        
        if cached:
            print(f"[PERF] Bulk cache hit: {(time.time() - start_time)*1000:.2f}ms")
            return Response({"data": cached}, status=status.HTTP_200_OK)
        
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            
            # OPTIMIZATION 2: Single query for entire day
            query_start = time.time()
            rows = EmissionActual.objects.filter(
                region__in=regions,
                ts__date=date_obj
            ).select_related().order_by('region', 'ts')
            
            query_time = (time.time() - query_start) * 1000
            print(f"[PERF DB] Bulk query: {query_time:.2f}ms for {rows.count()} rows")
            
            # Group by hour for efficient access
            final_list = []
            for obj in rows:
                final_list.append({
                    "UTC time": obj.ts.isoformat(),
                    "creation_time (UTC)": obj.data.get("creation_time (UTC)", ""),
                    "version": obj.data.get("version", ""),
                    "region_code": obj.region,
                    "carbon_intensity_avg_lifecycle": obj.lifecycle or 0,
                    "carbon_intensity_avg_direct": obj.direct or 0,
                    "carbon_intensity_unit": "gCO2eg/kWh"
                })
            
            # Cache for longer (10 minutes for bulk)
            cache.set(cache_key, final_list, 600)
            
            total_time = (time.time() - start_time) * 1000
            print(f"[PERF END] Bulk API: {total_time:.2f}ms for {len(final_list)} items")
            
            return Response({
                "data": final_list,
                "metadata": {
                    "bulk_optimized": True,
                    "query_time_ms": query_time,
                    "total_time_ms": total_time
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"[PERF ERROR] Bulk query failed: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)