# CarbonCast — Real-Time Integration Monorepo

A system to predict the **hourly carbon intensity** of electricity for ~58 grid
regions across the US and Europe using machine learning, and serve those
forecasts through an API and an interactive web map.

This repository is a **monorepo** that combines the three projects which together
make up the live, real-time product. For the full narrative overview of how they
fit together, read **[`HANDOFF.md`](HANDOFF.md)**.

---

## Repository layout

```
.
├── CarbonCastUI/                  # (1) React web app — the interactive carbon-intensity map
│   └── web/                       #     Vite + TypeScript + MapLibre frontend
│
├── UCSC_CarbonCast_API/           # (2) Django REST API + ML forecasting pipeline
│   └── CarbonCast/                #     Celery real-time ingestion & retraining, TensorFlow models
│
├── UCSC_OSRE_CC_automation_tool/  # (3) RDA weather-download automation tool
│   └── CarbonCast/                #     Fetches NCEP GFS weather from NCAR's Research Data Archive
│
├── docs/                          # Cross-project handoff documentation
└── HANDOFF.md                     # Start here — the big-picture guide
```

How they connect: **(3) downloads weather → (2) turns it into forecasts and serves
them over a REST API → (1) draws the map.** The three are loosely coupled and can
be developed independently.

---

## Quick start

Each sub-project has its own README with canonical instructions. The fast paths:

```bash
# (1) Frontend
cd CarbonCastUI/web && npm install && npm run dev

# (2) Backend API (easiest via Docker)
cd UCSC_CarbonCast_API/CarbonCast && docker compose up --build

# (3) Automation tool
cd UCSC_OSRE_CC_automation_tool/CarbonCast && pip install -r requirements.txt && pytest
```

See [`HANDOFF.md`](HANDOFF.md) and [`docs/`](docs/) for details.

---

## ⚠️ Data & large files are NOT in this repo

This repo tracks **source code, configuration, and docs only.** Large datasets,
trained ML models, downloaded weather files (`.grib2`/`.tar`), local databases,
virtual environments, and build artifacts are **kept local** and excluded via
[`.gitignore`](.gitignore).

A fresh `git clone` will **not** include that data — this is intentional (GitHub
rejects files >100 MB and the datasets are multi-GB and re-fetchable). For the
full list of what's excluded and **how to regenerate or fetch it**, read
**[`docs/05-data-and-large-files.md`](docs/05-data-and-large-files.md)**.

Secrets (`.env`, `rdams_token.txt`, keys) are never committed; `.env.example`
files document the variables each project needs.

---

## Documentation

| Doc | What it covers |
|-----|----------------|
| [`HANDOFF.md`](HANDOFF.md) | Big-picture overview & how the three projects connect. |
| [`docs/01-frontend-guide.md`](docs/01-frontend-guide.md) | The React web app. |
| [`docs/02-api-guide.md`](docs/02-api-guide.md) | The Django API & forecasting backend. |
| [`docs/03-automation-tool-guide.md`](docs/03-automation-tool-guide.md) | The RDA weather-download tool. |
| [`docs/04-reorganization-recommendations.md`](docs/04-reorganization-recommendations.md) | Safe refactoring plan. |
| [`docs/05-data-and-large-files.md`](docs/05-data-and-large-files.md) | Why data isn't in git & how to get it back. |

---

## License

See the `LICENSE` files within each sub-project (Apache-2.0).
