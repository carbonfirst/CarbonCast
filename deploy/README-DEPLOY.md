# CarbonCast Deployment Runbook

Target: the asouza.io container (`ssh tanush@asouza.io -p 2222`).
Host routing already maps `carboncast.duckdns.org:8000` → API and `:8001` → UI.

The bootstrap script detects capabilities and adapts:
- **Docker available** → use the compose stack in `UCSC_CarbonCast_API/CarbonCast/`
- **No Docker** → user-space stack: supervisord manages redis, gunicorn (API),
  celery worker + beat, the RDA tool loop, and the static UI server.
  DB is system Postgres if present, else SQLite (WAL mode).

## 0. First login

```bash
ssh tanush@asouza.io -p 2222
passwd                          # change the default password immediately
```

Install prerequisites (user-space, no sudo needed):

```bash
# nvm + node (https://heynode.com/tutorial/install-nodejs-locally-nvm/)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install --lts

# check python (need 3.8–3.10 for the optional TF path; 3.10 ideal)
python3 --version
```

If python3.10 is missing and you have no sudo, ask the host admin for
`python3.10 python3.10-venv build-essential` (and optionally
`redis-server postgresql libeccodes0`).

## 1. Clone and bootstrap

```bash
git clone <repo-url> ~/UCSC_CarbonCast_UI
cd ~/UCSC_CarbonCast_UI
bash deploy/bootstrap.sh
```

The script creates:
- `.venv-api/` (Django/Celery, includes gunicorn + supervisor)
- `.venv-tool/` (RDA tool — separate on purpose; version pins conflict)
- `~/carboncast-runtime/` (logs, run, data, generated configs)
- `UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/.env` (from
  `deploy/env.api.template` with absolute `RDA_*` paths pre-filled)
- `~/carboncast-runtime/automation_config.json` (tool config with
  **absolute** control/download dirs — this resolves the tool's CWD
  ambiguity; canonical dirs are the `src/python/` copies)
- `~/carboncast-runtime/supervisord.conf`

## 2. Credentials

```bash
# NCAR RDA token (required for live weather) — from your rda.ucar.edu profile
echo '<YOUR_TOKEN>' > ~/UCSC_CarbonCast_UI/UCSC_OSRE_CC_automation_tool/CarbonCast/src/python/rdams_token.txt
chmod 600 .../rdams_token.txt

# EIA / ENTSO-E keys (later): edit the .env, then restart the workers:
#   supervisorctl -c ~/carboncast-runtime/supervisord.conf restart carboncast:celery-worker
# The /status page flips those stages from "Needs credential" automatically.
```

## 3. Database + seed

```bash
cd ~/UCSC_CarbonCast_UI/UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI
source ~/UCSC_CarbonCast_UI/.venv-api/bin/activate
set -a; source .env; set +a

python manage.py migrate
python manage.py setup_pipeline_schedules      # seeds the 8 beat schedules

# Seed historical data from the bundled CSVs (~107k files — run in tmux, takes hours)
tmux new -s seed
python manage.py import_csvs --path ../../real_time
```

If using system Postgres instead of SQLite: `createdb carboncast`,
create the `carboncast` user, put the password in `.env`, set
`DB_ENGINE=postgres`.

## 4. Build the UI

```bash
cd ~/UCSC_CarbonCast_UI/CarbonCastUI/web
echo 'VITE_API_BASE_URL=http://carboncast.duckdns.org:8000' > .env.production
npm ci && npm run build
```

## 5. Start everything

```bash
~/UCSC_CarbonCast_UI/.venv-api/bin/supervisord -c ~/carboncast-runtime/supervisord.conf
~/UCSC_CarbonCast_UI/.venv-api/bin/supervisorctl -c ~/carboncast-runtime/supervisord.conf status
```

Expected: `redis`, `api`, `celery-worker`, `celery-beat`, `rda-tool`, `ui`
all RUNNING.

## 6. Smoke tests

```bash
curl -s localhost:8000/v1/PipelineHealth | python3 -m json.tool
#   database/redis/worker/beat should flip to ok within ~5 min (first heartbeat)

curl -s localhost:8000/v1/PipelineStatus | python3 -m json.tool | head -50
curl -s localhost:8000/v1/CarbonIntensity?region_code=CISO | head -c 300
# Browser: http://carboncast.duckdns.org:8001/status
```

Kick the pipeline without waiting for the schedules:

```bash
cd ~/UCSC_CarbonCast_UI/UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI
source ~/UCSC_CarbonCast_UI/.venv-api/bin/activate
set -a; source .env; set +a
python - <<'EOF'
from CarbonCastRESTAPI import tasks
tasks.trigger_rda_control_files.delay()      # writes 288 ctl files
tasks.fetch_daily_energy_data.delay()        # 'waiting_on_credential' until EIA key
tasks.check_weather_freshness_and_fallback.delay()
EOF
```

Once ctl files exist, the `rda-tool` program detects them (≤15 min poll)
and starts submitting to NCAR. Watch `~/carboncast-runtime/logs/rda-tool.log`
and the `/status` page's "RDA download tool" stage.

## 7. Ongoing operation (all automatic)

| When (UTC) | What |
|---|---|
| every 5 min | heartbeat (worker liveness for /status) |
| every 2 h | ingest new RDA downloads → WeatherForecast |
| daily 04:00 | delete ingested downloads older than 14 d |
| daily 06:00 / 06:30 | EIA / ENTSO-E energy ingestion |
| Mon 03:00 | regenerate weekly ctl files (all 72 regions) |
| Mon 05:00 | weather freshness check → historical fallback if needed |
| Mon 06:00 | retrain models, write 168 h forecast batches |
| continuous | rda-tool loop: submit/poll/download/purge, re-runs on new ctl files |

## Troubleshooting

- **TF install fails** (wrong python / platform): the ML extras are only
  needed for `CARBONCAST_RUN_ML=true`. Install everything else from
  `requirements.txt` by commenting out the `# ML / Data` block; the
  baseline forecast pipeline runs without TF.
- **`/status` shows "tool may not be running"**: check
  `supervisorctl status carboncast:rda-tool` and its log; the state-file
  age heuristic fires when the tool hasn't written for 30+ min with work
  pending.
- **Stage "Needs config"**: an `RDA_*` env var is unset in `.env` (the
  worker also needs a restart after `.env` edits).
- **Disk filling**: confirm `RDA_CLEANUP_ENABLED=true`; run
  `python manage.py cleanup_rda_downloads --dry-run` to inspect.
- **Deep-debug the tool**: its own Flask dashboards still exist —
  `python batch_monitor.py` (:5000) from `src/python/` in the tool venv.
