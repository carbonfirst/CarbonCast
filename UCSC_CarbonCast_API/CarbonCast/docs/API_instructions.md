# CarbonCastAPI - Run & DB Integration Instructions

This document contains tested commands to run the Django API with the SQLite DB ingestion in this repo.

Prerequisites:
- Python 3.9+ and pip installed
- Virtualenv recommended

Quick setup (no docker)

1. Create and activate a virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
python src/CarbonCastAPI/manage.py makemigrations CarbonCastRESTAPI
python src/CarbonCastAPI/manage.py migrate
```

4. Import CSVs into SQLite (one-time; path is relative to repo):

```bash
python src/CarbonCastAPI/manage.py import_csvs --path real_time
```

Importer notes: The importer now makes parsed datetimes timezone-aware and heuristically populates EmissionActual.lifecycle and EmissionActual.direct from CSV headers when present while still storing the full row in EmissionActual.data. See [`src/CarbonCastAPI/CarbonCastRESTAPI/management/commands/import_csvs.py`](src/CarbonCastAPI/CarbonCastRESTAPI/management/commands/import_csvs.py:1).

5. Run integration tests:

```bash
python src/CarbonCastAPI/manage.py test CarbonCastRESTAPI.tests.test_db_integration
```

6. Start dev server:

```bash
python src/CarbonCastAPI/manage.py runserver
```

7. API endpoints (examples):

- Latest carbon intensity (requires auth by default):

```bash
curl -i -u apitest:s3cret -H "Accept: application/json" "http://127.0.0.1:8000/v1/CarbonIntensity?region_code=PJM"
```

- Supported regions:

```bash
curl -i -u apitest:s3cret "http://127.0.0.1:8000/v1/SupportedRegions"
```

Troubleshooting/Notes:

- If you see carbon_intensity values being returned when lifecycle/direct are 0, the view now falls back to values in the stored JSON (see [`src/CarbonCastAPI/CarbonCastRESTAPI/views.py`](src/CarbonCastAPI/CarbonCastRESTAPI/views.py:136)).
- If running into timezone warnings, ensure migrations ran and importer was executed; importer now stores tz-aware datetimes.
- To inspect counts:

```bash
python src/CarbonCastAPI/manage.py shell -c "from CarbonCastRESTAPI.models import EmissionActual; print('EmissionActual count=', EmissionActual.objects.count())"
```

- To view latest PJM row:

```bash
python src/CarbonCastAPI/manage.py shell -c "from CarbonCastRESTAPI.models import EmissionActual; o=EmissionActual.objects.filter(region='PJM').order_by('-ts').first(); print(o, o.lifecycle, o.direct, o.data)"
```

Files changed during DB integration work:

- [`src/CarbonCastAPI/CarbonCastRESTAPI/management/commands/import_csvs.py`](src/CarbonCastAPI/CarbonCastRESTAPI/management/commands/import_csvs.py:1) — tz-aware datetimes, lifecycle/direct extraction, summary logging.
- [`src/CarbonCastAPI/CarbonCastRESTAPI/views.py`](src/CarbonCastAPI/CarbonCastRESTAPI/views.py:136) — fallback to JSON carbon_intensity when lifecycle/direct missing.

Last verified results:
- Import summary: files_processed=41922, rows_updated=1006128, errors=0
- Integration test: passed
- Example API curl returns numeric carbon intensity for PJM

End.
