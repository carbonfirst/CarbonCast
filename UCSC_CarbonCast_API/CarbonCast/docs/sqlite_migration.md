# SQLite Migration and CSV Import Guide

This document explains how to enable and use the new SQLite-backed runtime storage for CarbonCast.

Overview
- New Django models (in `CarbonCastRESTAPI.models`) store runtime CSV data.
- Views read from the database first and fall back to CSV files if the DB is not populated.
- Short-lived caching (Django locmem) is used for read endpoints (default 10s).

Models (brief)
- EmissionActual: region, ts (datetime), lifecycle (float), direct (float), source_file, data (JSON)
- Forecast96: region, ts (datetime), value (float), forecast_type, data (JSON)
- Weather: region, ts (datetime), temp, data (JSON)

Migrations
1. Generate migrations:
   python manage.py makemigrations CarbonCastRESTAPI
2. Apply migrations:
   python manage.py migrate

Import CSVs into SQLite
- A management command was added: `import_csvs`.
- Usage (from project root):
  python manage.py import_csvs --path real_time
- Behavior:
  - Walks each region folder under the provided path.
  - Imports *_lifecycle_emissions.csv and *_direct_emissions.csv into EmissionActual.
  - Imports lifecycle/direct CI forecast CSVs and 96hr energy forecasts into Forecast96.
  - Uses ORM upserts (update_or_create) for idempotency and bulk_create in chunks for initial inserts.

Running the development server
1. python manage.py makemigrations CarbonCastRESTAPI
2. python manage.py migrate
3. python manage.py import_csvs --path real_time
4. python manage.py runserver

Switching back to CSV-only behavior
- The views will automatically fall back to the existing CSV files when no DB rows are present.
- To revert fully, remove the DB import and revert the code changes (keep a copy of the updated files).

Caching
- Implemented using Django's locmem cache via `django.core.cache.cache`.
- Default timeout used in views: 10 seconds.
- To tune caching, modify your Django `CACHES` setting and/or change the timeout values in the views.

Troubleshooting
- If migrations fail, ensure your Django version supports JSONField (Django 3.1+ or adjust).
- Ensure the `real_time/` path exists and CSVs follow expected formats (timestamp in first column).
- Check management command output for counts and parsing errors.