# CarbonCast — Project Handoff Guide

> Hey there 👋 — if you're reading this, you're probably the next person taking
> over (or just trying to make sense of) this repo. This document is the thing I
> wish I'd had on day one. It explains what's here, how the pieces fit together,
> and where to go next. I've tried to keep it honest about the rough edges too,
> so you don't waste a week rediscovering them.

Last meaningful update: see `git log`. If something below feels stale, trust the
code over the docs and then please fix the docs.

---

## The 30-second version

CarbonCast is a research system that **forecasts the carbon intensity of
electricity** (how many grams of CO₂ are emitted per kWh) for ~58 grid regions
across the US and Europe. This workspace holds **three separate projects** that
together make up the live product:

| # | Folder | What it is | Language / Stack |
|---|--------|------------|------------------|
| 1 | `CarbonCastUI/` | The web app users actually look at — an interactive world map colored by carbon intensity, with history/now/forecast timelines and per-region detail panels. | React 19 + TypeScript + Vite + MapLibre |
| 2 | `UCSC_CarbonCast_API/` | The backend brain — a Django REST API that serves carbon/energy data, plus the ML forecasting pipeline and a Celery-based real-time data ingestion + retraining system. | Django 4.2 + DRF + Celery + PostgreSQL + TensorFlow/Keras |
| 3 | `UCSC_OSRE_CC_automation_tool/` | A standalone automation tool that downloads weather data (NCEP GFS forecasts) from NCAR's Research Data Archive so the pipeline has fresh inputs to forecast with. | Python + Flask dashboard |

Think of it as: **(3) feeds weather data → (2) turns it into forecasts and serves
them over an API → (1) draws the pretty map.**

---

## How the three projects talk to each other

```
                         ┌──────────────────────────────────────┐
                         │   NCAR RDA (ds084.1 GFS weather)       │
                         └───────────────────┬────────────────────┘
                                             │ downloads .grib weather files
                                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │  (3) UCSC_OSRE_CC_automation_tool                            │
        │      submit → monitor → download → organize by region        │
        └───────────────────────────┬─────────────────────────────────┘
                                     │ weather files land where the pipeline reads them
                                     ▼
        ┌────────────────────────────────────────────────────────────┐
        │  (2) UCSC_CarbonCast_API (Django + Celery + ML)              │
        │      - daily ingestion of grid + weather data                │
        │      - two-tier ML forecast (sources → carbon intensity)     │
        │      - weekly model retraining                               │
        │      - stores results in PostgreSQL                          │
        │      - serves everything over a REST API                     │
        └───────────────────────────┬─────────────────────────────────┘
                                     │ HTTP/JSON  (e.g. /carboncastapi/v1/CarbonIntensity)
                                     ▼
        ┌────────────────────────────────────────────────────────────┐
        │  (1) CarbonCastUI (React)                                    │
        │      fetches data, caches it, paints the choropleth map      │
        └────────────────────────────────────────────────────────────┘
```

The important thing to internalize: these are **loosely coupled**. The UI only
knows the API's HTTP endpoints. The API only knows where weather files show up on
disk. You can run and develop any one of them without the other two fully working
(the API even falls back to CSV files when the database is empty).

---

## Where to start depending on what you need to do

- **"I just want to change how the map looks."** → Go to
  [`docs/01-frontend-guide.md`](docs/01-frontend-guide.md). You mostly live in
  `CarbonCastUI/web/src/`.
- **"I need to add/fix an API endpoint or change forecasting."** → Go to
  [`docs/02-api-guide.md`](docs/02-api-guide.md). The Django app is under
  `UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/`.
- **"Weather data isn't coming in."** → Go to
  [`docs/03-automation-tool-guide.md`](docs/03-automation-tool-guide.md).
- **"I want to clean this code up without breaking it."** → Read
  [`docs/04-reorganization-recommendations.md`](docs/04-reorganization-recommendations.md).
  It's a prioritized, low-risk plan.

---

## Quick start (get all three running locally)

You don't usually need all three at once. But here's the fast path for each.

### 1. Frontend
```bash
cd CarbonCastUI/web
npm install
# Point it at an API. Create web/.env with:
#   VITE_API_BASE_URL=http://localhost:8000
npm run dev          # opens a Vite dev server, usually http://localhost:5173
```

### 2. Backend API
```bash
cd UCSC_CarbonCast_API/CarbonCast
# The easiest path is Docker (brings up Postgres, Redis, web, and Celery):
docker compose up --build
# Or run Django directly (you'll need Python + a local Postgres):
pip install -r requirements.txt
cd src/CarbonCastAPI
python manage.py migrate
python manage.py runserver
```
API docs (Swagger) are exposed by `drf_yasg` once the server is up.

### 3. Automation tool
```bash
cd UCSC_OSRE_CC_automation_tool/CarbonCast
pip install -r requirements.txt
# Needs RDA credentials + control files in control_files/. See the project guide.
pytest                # run the test suite first to confirm your env is sane
```

Each project has its own README with the canonical, most up-to-date instructions.
This guide is the map; those READMEs are the territory.

---

## A few honest notes before you dive in

- **There is duplication of the name "CarbonCast" everywhere.** All three folders
  contain a `CarbonCast/` subfolder. It's confusing at first. Just remember the
  *outer* folder name tells you which project you're in.
- **The backend repo also contains the original research pipeline** (standalone
  Python scripts in `src/`) alongside the Django app. They share lineage but the
  API is what's actually deployed. Don't confuse the two.
- **Lots of historical data folders** (`data_old (v2.1)`, `data_old(v3.1)`,
  `CI_forecast_data/`, `real_time/`) are committed to the repo. They're large and
  mostly reference/fallback data. Don't be alarmed by the file count.
- **The code works, but it grew organically.** Some files are very large (the
  Django `views.py` is ~1,900 lines; a few React components are 600+ lines).
  That's normal for a research project that turned into a product. The
  reorganization doc has a gentle plan to tame this without breaking anything.

Welcome aboard. The detailed guides are in `docs/`. Good luck, and leave the
campsite cleaner than you found it. 🌱
