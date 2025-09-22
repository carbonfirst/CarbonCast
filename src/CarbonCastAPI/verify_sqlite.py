#!/usr/bin/env python
"""
Simple SQLite verification script for CarbonCast API
"""

import os
import sys
import django
import sqlite3

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CarbonCastAPI.settings')
django.setup()

from django.db import connection
from CarbonCastRESTAPI.models import (
    Forecast96, Weather, EmissionActual, UserModel, UserThrottleLimit
)

def main():
    print("=" * 80)
    print("CarbonCast API - SQLite Database Verification")
    print("=" * 80)
    
    # 1. Check database file
    db_path = 'db.sqlite3'
    print(f"\n1. Database File Check:")
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        print(f"   ✅ Database exists: {db_path}")
        print(f"   📊 Size: {size_mb:.2f} MB")
    else:
        print(f"   ❌ Database not found: {db_path}")
        return
    
    # 2. Check tables directly with SQLite
    print(f"\n2. Database Tables (via SQLite):")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cursor.fetchall()
    print(f"   Found {len(tables)} tables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"   - {table[0]}: {count} records")
    conn.close()
    
    # 3. Check using Django ORM
    print(f"\n3. Django Model Record Counts:")
    models = [
        ('Forecast96', Forecast96),
        ('Weather', Weather),
        ('EmissionActual', EmissionActual),
        ('UserModel', UserModel),
        ('UserThrottleLimit', UserThrottleLimit)
    ]
    
    total_records = 0
    for name, model in models:
        try:
            count = model.objects.count()
            total_records += count
            print(f"   - {name}: {count} records")
        except Exception as e:
            print(f"   - {name}: Error - {e}")
    
    print(f"\n   Total records in Django models: {total_records}")
    
    # 4. Test a sample query
    print(f"\n4. Sample Query Test:")
    try:
        # Try to get the latest emission actual
        latest = EmissionActual.objects.order_by('-ts').first()
        if latest:
            print(f"   ✅ Latest EmissionActual:")
            print(f"      - Region: {latest.region}")
            print(f"      - Timestamp: {latest.ts}")
            print(f"      - Lifecycle: {latest.lifecycle}")
            print(f"      - Direct: {latest.direct}")
        else:
            print(f"   ⚠️ No EmissionActual records found")
    except Exception as e:
        print(f"   ❌ Error querying: {e}")
    
    # 5. Summary
    print(f"\n" + "=" * 80)
    print("SUMMARY:")
    if total_records > 0:
        print("✅ SQLite database is configured and contains data")
        print("✅ Django ORM can successfully query the database")
        print(f"✅ Total of {total_records} records found in Django models")
    else:
        print("⚠️ SQLite database exists but contains no data")
        print("⚠️ Run 'python manage.py import_csvs' to import data")
    print("=" * 80)

if __name__ == "__main__":
    main()