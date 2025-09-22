#!/usr/bin/env python
"""
Test API endpoints to verify they're using SQLite and not CSV fallback
"""

import os
import sys
import django
import json
from datetime import datetime

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CarbonCastAPI.settings')
django.setup()

from django.test import Client
from django.db import connection
from django.conf import settings

def test_api_endpoints():
    print("=" * 80)
    print("API Endpoint Testing - Verifying SQLite Usage")
    print("=" * 80)
    
    # Enable SQL query logging
    settings.DEBUG = True
    
    client = Client()
    
    # Test endpoints - note the /v1/ prefix
    endpoints = [
        {
            'name': 'CarbonIntensity',
            'url': '/v1/CarbonIntensity',
            'params': {'region_code': 'GRID'}
        },
        {
            'name': 'CarbonIntensityHistory',
            'url': '/v1/CarbonIntensityHistory',
            'params': {'region_code': 'GRID'}
        },
        {
            'name': 'EnergySources',
            'url': '/v1/EnergySources',
            'params': {'region_code': 'GRID'}
        },
        {
            'name': 'CarbonIntensityForecasts',
            'url': '/v1/CarbonIntensityForecasts',
            'params': {'region_code': 'CISO'}
        },
        {
            'name': 'SupportedRegions',
            'url': '/v1/SupportedRegions',
            'params': {}
        }
    ]
    
    results = []
    
    for endpoint in endpoints:
        print(f"\n📍 Testing: {endpoint['name']}")
        print(f"   URL: {endpoint['url']}")
        print(f"   Params: {endpoint['params']}")
        print("-" * 60)
        
        # Clear query log
        connection.queries_log.clear()
        
        try:
            # Make the API request
            response = client.get(endpoint['url'], endpoint['params'])
            
            # Count database queries
            query_count = len(connection.queries)
            
            # Analyze response
            if response.status_code == 200:
                data = response.json()
                
                # Check if data was returned
                if 'data' in data:
                    records = data['data']
                    record_count = len(records) if isinstance(records, list) else 1
                else:
                    record_count = 0
                
                # Check for CSV fallback indicators
                csv_fallback = False
                if 'source' in data and 'csv' in str(data.get('source', '')).lower():
                    csv_fallback = True
                
                print(f"   ✅ Status: {response.status_code}")
                print(f"   📊 Records returned: {record_count}")
                print(f"   🔍 Database queries executed: {query_count}")
                
                if query_count > 0:
                    print(f"   ✅ SQLite database is being queried")
                    # Show sample query
                    if connection.queries:
                        sample_query = connection.queries[0]['sql'][:150]
                        print(f"   Query sample: {sample_query}...")
                else:
                    print(f"   ⚠️  No database queries detected")
                
                if csv_fallback:
                    print(f"   ⚠️  CSV fallback detected in response")
                else:
                    print(f"   ✅ No CSV fallback indicators found")
                
                results.append({
                    'endpoint': endpoint['name'],
                    'status': 'SUCCESS',
                    'using_sqlite': query_count > 0,
                    'csv_fallback': csv_fallback,
                    'records': record_count
                })
                
            else:
                print(f"   ⚠️  Status: {response.status_code}")
                error_msg = response.content.decode()[:200]
                print(f"   Error: {error_msg}...")
                
                results.append({
                    'endpoint': endpoint['name'],
                    'status': 'ERROR',
                    'error_code': response.status_code
                })
                
        except Exception as e:
            print(f"   ❌ Exception: {str(e)}")
            results.append({
                'endpoint': endpoint['name'],
                'status': 'EXCEPTION',
                'error': str(e)
            })
    
    # Disable debug mode
    settings.DEBUG = False
    
    # Final summary
    print("\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    
    sqlite_endpoints = sum(1 for r in results if r.get('using_sqlite', False))
    csv_fallback_endpoints = sum(1 for r in results if r.get('csv_fallback', False))
    error_endpoints = sum(1 for r in results if r.get('status') != 'SUCCESS')
    
    print(f"\n📊 Total endpoints tested: {len(endpoints)}")
    print(f"✅ Endpoints using SQLite: {sqlite_endpoints}")
    print(f"⚠️  Endpoints with CSV fallback: {csv_fallback_endpoints}")
    print(f"❌ Endpoints with errors: {error_endpoints}")
    
    if sqlite_endpoints > 0 and csv_fallback_endpoints == 0:
        print("\n🎉 SUCCESS: API is using SQLite database!")
        print("✅ No CSV fallback detected")
        print("✅ Database queries are being executed")
        print("✅ SQLite integration is working properly")
    elif sqlite_endpoints == 0:
        print("\n⚠️  WARNING: No SQLite queries detected!")
        print("The API might be falling back to CSV files")
    else:
        print("\n⚠️  MIXED: Some endpoints use SQLite, some may use CSV")
    
    # Save detailed results
    with open('api_endpoint_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: api_endpoint_test_results.json")
    
    return sqlite_endpoints > 0 and csv_fallback_endpoints == 0

if __name__ == "__main__":
    success = test_api_endpoints()
    sys.exit(0 if success else 1)