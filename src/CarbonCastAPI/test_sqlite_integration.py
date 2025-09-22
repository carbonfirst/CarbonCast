#!/usr/bin/env python
"""
Comprehensive SQLite Integration Test for CarbonCast API
This script verifies that the API is using SQLite database and not falling back to CSV files.
"""

import os
import sys
import django
import json
from datetime import datetime
import sqlite3
from pathlib import Path

# Setup Django environment
sys.path.insert(0, '/Users/tanushsavadi/Documents/Research/UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CarbonCastAPI.settings')
django.setup()

from django.db import connection
from django.test import TestCase, Client
from CarbonCastRESTAPI.models import (
    Forecast96, Weather, EmissionActual, UserModel, UserThrottleLimit
)
from django.db.models import Count
import logging

# Setup logging to capture database queries
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SQLiteIntegrationTest:
    def __init__(self):
        self.client = Client()
        self.results = {}
        self.db_path = 'db.sqlite3'
        
    def check_database_exists(self):
        """Check if the SQLite database file exists"""
        logger.info("=" * 80)
        logger.info("STEP 1: Checking SQLite Database File")
        logger.info("=" * 80)
        
        if os.path.exists(self.db_path):
            size = os.path.getsize(self.db_path) / (1024 * 1024)  # Size in MB
            logger.info(f"✅ Database file exists at: {self.db_path}")
            logger.info(f"   Size: {size:.2f} MB")
            self.results['database_exists'] = True
            self.results['database_size_mb'] = size
        else:
            logger.error(f"❌ Database file not found at: {self.db_path}")
            self.results['database_exists'] = False
        return self.results['database_exists']
    
    def check_database_tables(self):
        """Check what tables exist in the database"""
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Checking Database Tables")
        logger.info("=" * 80)
        
        with connection.cursor() as cursor:
            # Get list of tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name;
            """)
            tables = cursor.fetchall()
            table_names = [t[0] for t in tables]
            
            logger.info(f"Found {len(table_names)} tables in database:")
            for table in table_names:
                logger.info(f"  - {table}")
            
            self.results['tables'] = table_names
            self.results['table_count'] = len(table_names)
            
            # Check if Django models tables exist
            expected_tables = [
                'CarbonCastRESTAPI_forecast96',
                'CarbonCastRESTAPI_weather',
                'CarbonCastRESTAPI_emissionactual',
                'CarbonCastRESTAPI_usermodel',
                'CarbonCastRESTAPI_userthrottlelimit'
            ]
            
            logger.info("\nChecking for expected model tables:")
            for expected in expected_tables:
                if expected in table_names:
                    logger.info(f"  ✅ {expected} exists")
                else:
                    logger.warning(f"  ⚠️ {expected} not found")
            
        return len(table_names) > 0
    
    def count_records_in_tables(self):
        """Count records in each table"""
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Counting Records in Database Tables")
        logger.info("=" * 80)
        
        models = [
            ('Forecast96', Forecast96),
            ('Weather', Weather),
            ('EmissionActual', EmissionActual),
            ('UserModel', UserModel),
            ('UserThrottleLimit', UserThrottleLimit)
        ]
        
        self.results['record_counts'] = {}
        total_records = 0
        
        for name, model in models:
            try:
                count = model.objects.count()
                self.results['record_counts'][name] = count
                total_records += count
                logger.info(f"  {name}: {count} records")
            except Exception as e:
                logger.error(f"  {name}: Error counting - {e}")
                self.results['record_counts'][name] = 'error'
        
        logger.info(f"\n  Total records across all tables: {total_records}")
        self.results['total_records'] = total_records
        return total_records
    
    def test_api_endpoints(self):
        """Test API endpoints to verify they're using SQLite"""
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Testing API Endpoints (verifying SQLite usage)")
        logger.info("=" * 80)
        
        # Enable SQL query logging
        from django.db import connection
        from django.conf import settings
        settings.DEBUG = True
        
        endpoints = [
            ('/CarbonIntensity', {'region_code': 'CISO'}),
            ('/Weather', {'region_code': 'CISO'}),
            ('/CarbonIntensityForecasts', {'region_code': 'CISO'}),
            ('/CarbonIntensityForecasts96Hour', {'region_code': 'CISO'}),
            ('/CarbonIntensityForecastsHistory', {'region_code': 'CISO', 'start_date': '2024-01-01', 'end_date': '2024-01-02'}),
            ('/SupplyForecasts', {'region_code': 'CISO'}),
        ]
        
        self.results['endpoint_tests'] = {}
        
        for endpoint, params in endpoints:
            logger.info(f"\nTesting endpoint: {endpoint}")
            logger.info(f"  Parameters: {params}")
            
            # Reset query log
            connection.queries_log.clear()
            
            try:
                response = self.client.get(endpoint, params)
                query_count = len(connection.queries)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data:
                        record_count = len(data['data']) if isinstance(data['data'], list) else 1
                    else:
                        record_count = 0
                    
                    logger.info(f"  ✅ Status: {response.status_code}")
                    logger.info(f"  📊 Records returned: {record_count}")
                    logger.info(f"  🔍 Database queries executed: {query_count}")
                    
                    # Check if queries were made (indicates SQLite usage)
                    if query_count > 0:
                        logger.info(f"  ✅ SQLite database is being queried")
                        # Show first query for verification
                        if connection.queries:
                            first_query = connection.queries[0]['sql'][:200]
                            logger.info(f"  Sample query: {first_query}...")
                    else:
                        logger.warning(f"  ⚠️ No database queries detected - might be using CSV fallback")
                    
                    self.results['endpoint_tests'][endpoint] = {
                        'status': response.status_code,
                        'records': record_count,
                        'queries': query_count,
                        'using_sqlite': query_count > 0
                    }
                else:
                    logger.warning(f"  ⚠️ Status: {response.status_code}")
                    logger.warning(f"  Response: {response.content.decode()[:200]}...")
                    self.results['endpoint_tests'][endpoint] = {
                        'status': response.status_code,
                        'error': True
                    }
                    
            except Exception as e:
                logger.error(f"  ❌ Error: {e}")
                self.results['endpoint_tests'][endpoint] = {'error': str(e)}
        
        # Disable debug mode
        settings.DEBUG = False
    
    def verify_no_csv_fallback(self):
        """Verify that CSV fallback is not being triggered"""
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: Verifying CSV Fallback is NOT Active")
        logger.info("=" * 80)
        
        # Check if any endpoint is using SQLite
        using_sqlite = False
        for endpoint, result in self.results.get('endpoint_tests', {}).items():
            if result.get('using_sqlite', False):
                using_sqlite = True
                break
        
        if using_sqlite:
            logger.info("✅ SQLite database is the active data source")
            logger.info("✅ CSV fallback is NOT being triggered")
            self.results['csv_fallback_active'] = False
        else:
            logger.warning("⚠️ No SQLite queries detected")
            logger.warning("⚠️ CSV fallback might be active")
            self.results['csv_fallback_active'] = True
        
        return not self.results['csv_fallback_active']
    
    def generate_report(self):
        """Generate final report"""
        logger.info("\n" + "=" * 80)
        logger.info("FINAL REPORT: SQLite Integration Status")
        logger.info("=" * 80)
        
        # Overall status
        all_good = (
            self.results.get('database_exists', False) and
            self.results.get('table_count', 0) > 0 and
            self.results.get('total_records', 0) > 0 and
            not self.results.get('csv_fallback_active', True)
        )
        
        if all_good:
            logger.info("\n🎉 SUCCESS: SQLite integration is working properly!")
        else:
            logger.warning("\n⚠️ ISSUES DETECTED: SQLite integration needs attention")
        
        # Summary
        logger.info("\nSUMMARY:")
        logger.info(f"  - Database exists: {self.results.get('database_exists', False)}")
        logger.info(f"  - Database size: {self.results.get('database_size_mb', 0):.2f} MB")
        logger.info(f"  - Tables found: {self.results.get('table_count', 0)}")
        logger.info(f"  - Total records: {self.results.get('total_records', 0)}")
        logger.info(f"  - CSV fallback active: {self.results.get('csv_fallback_active', 'unknown')}")
        
        # Table record counts
        logger.info("\nRECORD COUNTS BY TABLE:")
        for table, count in self.results.get('record_counts', {}).items():
            logger.info(f"  - {table}: {count}")
        
        # Endpoint results
        logger.info("\nENDPOINT TEST RESULTS:")
        for endpoint, result in self.results.get('endpoint_tests', {}).items():
            if 'error' not in result:
                logger.info(f"  - {endpoint}:")
                logger.info(f"      Status: {result.get('status')}")
                logger.info(f"      Records: {result.get('records', 'N/A')}")
                logger.info(f"      Using SQLite: {result.get('using_sqlite', False)}")
            else:
                logger.info(f"  - {endpoint}: ERROR")
        
        return all_good
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        logger.info("Starting Comprehensive SQLite Integration Tests")
        logger.info("=" * 80)
        
        # Run tests
        if not self.check_database_exists():
            logger.error("Database file not found. Aborting tests.")
            return False
        
        self.check_database_tables()
        self.count_records_in_tables()
        
        if self.results.get('total_records', 0) == 0:
            logger.info("\n" + "=" * 80)
            logger.info("No data in database. Importing sample CSV data...")
            logger.info("=" * 80)
            # Try to import data
            os.system('cd /Users/tanushsavadi/Documents/Research/UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI && python manage.py import_csvs --limit 100')
            # Recount after import
            self.count_records_in_tables()
        
        self.test_api_endpoints()
        self.verify_no_csv_fallback()
        
        # Generate final report
        success = self.generate_report()
        
        # Save results to JSON file
        with open('sqlite_test_results.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"\nTest results saved to: sqlite_test_results.json")
        
        return success


if __name__ == "__main__":
    tester = SQLiteIntegrationTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)