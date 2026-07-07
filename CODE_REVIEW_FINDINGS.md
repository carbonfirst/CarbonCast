# CarbonCast Monorepo — Full Code Review Findings (2026-07-02)

Scope: entire monorepo — `CarbonCastUI/web` (React), `UCSC_CarbonCast_API/CarbonCast`
(Django + Celery + ML), `UCSC_OSRE_CC_automation_tool/CarbonCast` (RDA downloader),
plus every integration seam between them. All findings below were verified against
the actual code (file:line given); the highest-severity ones were re-verified
independently by a second pass.

**Bottom line: the end-to-end automation (RDA weather → ingestion → ML retraining →
API → map) cannot work today.** Each hop has at least one independent blocker.
See §0 for the blocker list, then per-component details.

---

## 0. End-to-end blockers (fix these first, in order)

### B1. `docker compose up --build` fails, and even fixed, no worker/beat/db/redis exists
- `UCSC_CarbonCast_API/CarbonCast/docker-compose.yml` (10 lines total) defines only a
  `web` service and references `src/CarbonCastAPI/dockerfile` — **that file does not
  exist** (the only Dockerfile in the repo is the docs-site image at `src/slate/Dockerfile`).
- The compose file mounts `db.sqlite3`, but `settings.py:109-118` is hardcoded to
  PostgreSQL, and `settings.py:126-134` uses django-redis as the default cache —
  every data view calls `cache.get()` first, so without Redis every endpoint 500s.
- There are no `db`, `redis`, `celery worker`, or `celery beat` services, so **no
  scheduled task can ever fire** in the documented deployment. `HANDOFF.md` and
  `docs/02-api-guide.md` claim compose brings up "web, Postgres, Redis, celery
  worker/beat" — false.

### B2. The RDA tool's output cannot be ingested by the pipeline (4 independent breaks)
1. **File format**: the tool's real output is `downloaded_files/<REGION>/<variable>/gfs.0p25.*.grib2.tar`
   (verified on disk). `ingest_weather.py:167-189` dispatches on suffix — `.tar` matches
   nothing, cfgrib/netCDF fallbacks fail on a tar archive, the file returns 0 rows and
   is then **permanently blacklisted** in `processed_files.json` (`ingest_weather.py:97`).
   No `tarfile`/extraction code exists anywhere in either project.
2. **Region names**: tool uses `ERCOT`, `NYISO`, `BANC`, `PNM`, `TEPC`, `SCL`… ;
   `ingest_weather._infer_region` (`:110-122`) only accepts codes in
   `consts.US_region_codes`, which has `ERCO`/`NYIS` and lacks ~15 tool regions.
   `"ERCOT".split('_')[0]` is still `ERCOT` → no match → skipped forever.
3. **CTL generation reads wrong config keys**: `services/ctl_generator.py:60-63` reads
   `bbox.get('nlat')` etc., but the tool's `config/automation_config.json` stores
   `"coordinates": [42, 32, -124.75, -113.5]`. Result: every generated `.ctl` gets
   `nlat=0 slat=0 wlon=0 elon=0` — useless RDA requests. Only the 5-region hardcoded
   fallback has real boxes (and uses `ERCO` naming while the tool uses `ERCOT`).
4. **No glue at all**: `RDA_DOWNLOAD_DIR`, `RDA_CONTROL_FILES_DIR`, `RDA_CONFIG_PATH`
   are blank in `.env.example`; `tasks.py:60-63,75-78` skip with a warning when unset.
   No cron/script/volume connects the two repos.

### B3. The RDA tool itself can run "green" while downloading nothing
(details in §4) — empty download treated as success **then the RDA request is purged**
(data loss); completed-request scanner queries lowercase statuses that RDA never
returns; the tuned `config/automation_config.json` is never actually loaded (CWD
mismatch, silent default fallback); crash mid-submit/mid-download wedges requests
forever.

### B4. The real ML retraining path is broken end-to-end; only a naive baseline runs
- `retraining_service.py:237-238`: `from firstTierForecasts import …` — module lives in
  `src/`, Django runs from `src/CarbonCastAPI/`, no `sys.path` setup, package not
  installed (verified: `ModuleNotFoundError`). With `CARBONCAST_RUN_ML=true` every
  region fails with ImportError, is caught, and silently logged.
- Even with imports fixed: `runSecondTierInRealTime` selects the lifecycle model only
  when `cefType == "-l"` (`secondTierForecasts.py:281`) but the service passes
  `"lifecycle"`/`"direct"` — **both runs would use the direct model**. And
  `runFirstTierInRealTime` returns a dict keyed by region (`firstTierForecasts.py:257`)
  but the service does `first_tier_files[0]` → `KeyError`.
- `firstTierConfig.json`/`secondTierConfig.json` use CWD-relative model paths
  (`../saved_first_tier_models/`) that only resolve if the worker's CWD is exactly `src/`.
- `firstTierForecasts.py:269-270` expects `real_time/<REGION>/<REGION>_<date>.csv` and a
  `fuel_forecast/` output dir that doesn't exist; the service's artifact dir contains
  neither, and the path is concatenated without a trailing slash (`…/CISOCISO_….csv`).
- Consequence: what actually populates `Forecast96` is the "CarbonCast baseline" in
  `model_runners.py` — an **hourly-average of history**, not the neural pipeline.

### B5. Ingestion misconfiguration silently drops the biggest regions
- `services/eia_service.py:59-61` uses `"ERCOT"` and `"NYISO"`; the API/DB/CSVs use
  `ERCO`/`NYIS` everywhere (verified: `real_time/ERCO`, `real_time/NYIS`). Texas and
  New York either ingest zero rows or ingest under codes no endpoint can serve.
- `services/entsoe_service.py:144` reads `ENTSOE_API_KEY`; `.env.example:24` documents
  `ENTSOE_API_TOKEN`. Filling the template → all EU ingestion silently skipped, task
  still reports SUCCESS. (`ENTSOE_ENDPOINT_URL` in the template is read by nothing.)
- Per-BA `except Exception` swallowing in both services defeats the tasks'
  `autoretry_for` — an expired API key produces `{'errors': 32}` with task state SUCCESS.

---

## 1. Django REST API layer

Prefix `API/` = `UCSC_CarbonCast_API/CarbonCast/src/CarbonCastAPI/`.

### Critical
1. **`API/CarbonCastRESTAPI/models.py:16`** — `password = models.CharField(max_length=32)`.
   Django's PBKDF2 hash is 88 chars. On Postgres, `SignUp`, `createsuperuser`, and the
   test suite all raise `DataError: value too long for varchar(32)`. **Auth is
   inoperable on the runtime DB** (it only ever worked on SQLite, which ignores lengths).
2. **`API/CarbonCastRESTAPI/views/forecasts.py:106-107`** — CSV fallback of
   `CarbonIntensityForecasts` reads column index 3 = `carbon_intensity_actual` instead
   of index 4 = `avg_carbon_intensity_forecast` (verified against the real CSV header).
   The flagship forecast endpoint serves **actuals labeled as forecasts** whenever the
   DB is empty for a region. (The sibling history endpoint correctly reads `[i][4]`.)

### High
3. `forecasts.py:474-476,561` — `EnergySourcesForecastsHistory` crashes with
   `UnboundLocalError` on **every cache hit** (`energy_metadata` only assigned in the
   cache-miss branch; 10s TTL means the second identical request within 10s 500s).
4. `carbon_intensity.py:37/162`, `energy_sources.py:36/139`, `forecasts.py:191` —
   `if serializer.is_valid():` with no `else`: a blank `?region_code=` fails validation
   (verified) and falls through to undefined names → 500s (`regions`/`final_list`
   UnboundLocalError, or view returns `None`).
5. `forecasts.py:31,443` + `helper.py:97,110` — `regionCode` is used unvalidated in
   `os.path.join(base_dir, 'real_time', region_code)` + `os.listdir` **outside** the
   try block: unknown region → `FileNotFoundError` 500; `../../` → **path traversal**.
6. `views/auth.py:188-203` — `SignIn` never calls `user.save()` (so `password_checked`
   isn't persisted and `VerifyOTP` 403s), never calls `login()`, and crashes with 500
   for any user whose `otp_auth_url` is None (e.g. admin-created).
7. `views/auth.py:69-81,124-132` — SignUp: `UserThrottleLimit(throttle_limit=None)`
   (from `settings.DEFAULT_THROTTLE_LIMIT = None`) → IntegrityError, swallowed and
   reported as 409 "email already exists", leaving a half-created user that can never
   retry. `user.throttle_limit` OneToOne is never assigned.
8. `management/commands/import_csvs.py:38-51` — file discovery uses
   `f.endswith(patterns)` with three **infix** patterns (`'_96hr_forecasts_'` etc.);
   real names end with a date + `.csv`, so **no forecast CSV is ever imported**
   (verified programmatically). The entire `_import_forecast_file` path is dead code.
9. `import_csvs.py:273-299` — the generic `carbon_intensity` header matches both the
   lifecycle and direct key lists, so after a full import
   `EmissionActual.lifecycle == EmissionActual.direct` for every row.

### Medium
10. `settings.py:22` — `SECRET_KEY` falls back to `get_random_secret_key()` **per
    process**: sessions/signed cookies break on every restart and immediately under
    multi-worker gunicorn.
11. `settings.py:60` — `CORS_ORIGIN_ALLOW_ALL = True` (fine for a public read-only API,
    dangerous combined with SessionAuthentication when `REQUIRES_AUTH=True`).
12. `manage.py:21` sets `REQUIRES_AUTH` default `'True'`, but `wsgi.py`/`asgi.py` don't
    and `settings.py:123` defaults `'False'` — auth appears enforced under `runserver`
    but is silently off under gunicorn/uWSGI.
13. `forecasts.py:115-127,277-295` — lifecycle/direct rows paired **by list position**,
    not timestamp; partial batches mis-pair values across hours. Same positional bug in
    the CSV fallback (`carbon_intensity.py:315-316`), which also IndexErrors (swallowed)
    when the direct file is shorter.
14. `carbon_intensity.py:50,118-128` — response key typo `"cabon_intensity_unit"`, and
    the code adding `carbon_cast_version` sits after the `return` (unreachable).
15. Models/migrations drift: migration 0006 named the metric-type indexes, `models.py`
    declares them unnamed → `makemigrations --check` fails today.
16. `migrations/0003_optimize_indexes.py:19-24` — raw Postgres-only SQL (`ts::date`)
    breaks migrate on SQLite; worse, with `USE_TZ=True` Django compiles `ts__date` as
    `(ts AT TIME ZONE 'UTC')::date`, which does **not match** the index expression, so
    the hot history queries seq-scan anyway.
17. `forecasts.py:35,450` — `?forecastPeriod=abc` → unhandled ValueError → 500; the
    energy variant also never clamps to 168.
18. `views/regions.py:27-34` — `SupportedRegions` has no CSV/static fallback: fresh DB →
    empty region list (UI picker blank) even though every other endpoint would serve CSV
    data; the key `US_supported_regions` also contains the EU codes.
19. Forecast history semantics: `Forecast96` unique on `(region, ts, forecast_type)` and
    everything upserts on that key — each new batch **overwrites** prior forecasts for
    the same target hour, so "forecast history for backtesting" returns the newest batch,
    not what was forecast at the time.
20. `views/auth.py:99-101,192-195` — shared `qr_auth.png` temp file in CWD: two
    concurrent signups can each receive the **other user's TOTP QR** (permanent 2FA
    lockout).
21. `views/auth.py:261` — `pyotp.TOTP(None)` for accounts without `otp_base32` → 500.

### Low
22. `management/commands/refresh_limits.py:5` — imports `SimpleRateThrottle` from
    `throttling.py`, which only defines `MyViewRateThrottle` → ImportError on run.
23. `?hour=abc` leaves `hour_int=None` while the CSV filter still compares → silently
    empty response (`energy_sources.py:239-246`, `forecasts.py:332-333`).
24. Cache hits are always counted as `regions_from_db`, under-reporting fallback
    (`energy_sources.py:182`, `forecasts.py:234`).
25. `views_optimized.py` — dead code, unrouted; also builds naive datetimes.
26. `DataFreshness` does ~58 N+1 queries for the per-region weather source;
    `RetrainingStatus` loads the entire `ModelRun` table.
27. `helper.py:21` — `max()` on empty list when a region dir has no CSVs → swallowed →
    region silently dropped.
28. Debug `print()` everywhere (~90 in views alone), incl. `consts.py:16-20` printing at
    import time; module-level import-time evaluation of `REQUIRES_AUTH` means the flag
    can't change without a process restart.

---

## 2. Celery pipeline / services / management commands

(Besides B1, B4, B5 above.)

1. **HIGH** `ingest_weather.py:65,97` — `forecast_created` is stamped with ingestion
   wall-clock time, not the GFS init time. Re-ingesting the same stale file creates a
   "fresh" batch, so `check_weather_freshness_and_fallback` reports
   `fresh_data_available` even when RDA has been down for weeks, and
   `_latest_weather_rows` picks stale data as latest.
2. **MEDIUM** `retraining_service.py:294-331` — the 504-row forecast upsert loop has no
   `transaction.atomic()`; a crash / hard time-limit kill mid-loop leaves a spliced
   batch (half new `batch_id`, half last week's) that the API serves as-is.
3. **MEDIUM** `tasks.py:129-140` — the 12-month historical fallback copies rows to
   `forecast_target + 365d` under a new `forecast_created`, which the next weekly
   freshness check counts as fresh → fallback data silently self-perpetuates. Day-of-week
   alignment is also off by one/two days (365 ≠ 52 weeks).
4. **LOW** `eia_service.py:178-181` — `_interpolate_value` is dead code; the original
   EIA gap-filling was never ported, so missing hours are just absent.
5. **LOW** docs claim a **daily** forecast job; none exists — forecasts are only
   written inside weekly `retrain_models`, so one failed Monday = up to a 7-day hole.
6. Verified OK: task registration/autodiscovery, all-UTC crontabs and `CELERY_TIMEZONE`,
   EIA pagination logic, ENTSO-E timestamp normalization, Redis-lock usage,
   `requirements.txt` coverage of actual imports.

---

## 3. React frontend (`CarbonCastUI/web`)

`tsc --noEmit` and `vite build` pass **with the currently-installed node_modules** — but:

### High
1. **`package.json` vs `package-lock.json` out of sync — `npm ci` fails** (verified via
   `npm ci --dry-run`: removes `leaflet`, `react-leaflet`, `mapbox-choropleth`, …).
   Additionally `Choropleth.tsx`, `DynamicTileLayer.tsx`, `MapEventBridge.tsx` still
   import `react-leaflet`/`leaflet`, which are no longer in `package.json` — they only
   compile because stale packages are physically present. **The next clean
   `npm install && npm run build` fails** (`build` runs `tsc -b`).
2. `hooks/useEnergyData.ts:62-67` + `App.tsx:41` — mixed UTC/local time: initial date
   uses `toISOString()` (UTC) but hour uses `getHours()` (local). Users west of UTC get
   the wrong hour (off by the UTC offset) on history/priority fetches; near local
   midnight the date is even "tomorrow".
3. `hooks/cache.ts:1245-1316` — the background full-day fetch isn't cancelled and slices
   with the **closure-captured hour**; guard checks date only. Select date D at hour 5,
   slide to hour 20 while the ~seconds-long fetch is in flight → map repaints with
   hour-5 colors under an hour-20 slider.
4. `hooks/cache.ts:395-405` — `fetchWithDeduplication` aborts by **endpoint** only:
   switching region quickly aborts the other region's still-wanted request → spurious
   "Unknown error" panels.
5. `utils/regionMapping.ts:194,204,212` — API `DK/IT/SE` are mapped to a single sub-zone
   (`DK-DK1`, `IT-CNO`, `SE-SE1`). Painting works via group propagation, but
   `InfoPopover.tsx:132-137` reverse-lookup fails for the sibling zones → stale/"No data"
   tooltips on SE-SE2/3/4, IT-CSO, DK-DK2 while the map shows them colored.
6. **~19 clickable map zones return HTTP 400**: `regionMapping.ts` emits codes
   (`BANC, CHPD, CPLE, CPLW, DOPD, FMPP, GCPD, GVL, JEA, LGEE, PGE, PNM, SCL, TAL, TEC,
   TEPC, TPWR, RO, CA-ON`) that are not in the API's `consts.US_region_codes` — clicking
   e.g. Seattle shows "Unable to load energy data (400)".

### Medium
7. `useEnergyData.ts:427-470` — background hour fetch ignores its AbortController and
   writes stale results over fresh data after a date change.
8. `useEnergyData.ts:512-514,721-724` — `clearRegionCache` uses substring matching
   (`key.includes('SC')` also evicts `SCEG`, `PSCO`).
9. Two divergent cache envelope conventions between `cache.ts` and `useEnergyData.ts`;
   one branch can run `processEnergyData` over a metadata object, summing numeric
   metadata fields into the energy mix.
10. `useEnergyData.ts:572-589` — priority-hour path replaces the whole 24h chart with
    23 zero entries + 1 real hour; if the background fetch fails, fake zeros persist.
11. `MapEM.tsx:703-711,745-751` — bounds computed as `feature.geometry.coordinates[0]`
    assumes simple Polygon; MultiPolygon regions zoom to garbage extents (or silently
    fail).
12. `MapEM.tsx:394-431` — zone colors are never cleared when a region drops out of the
    data (e.g. switching to a future hour with no forecast keeps the old color instead
    of gray).
13. `cache.ts:659-705` — cache-update subscription hardcodes `region_code: 'all'` and
    matches keys by date substring: never fires in 'now' mode; can resurrect
    stale-but-within-TTL data as a "fresh" update.
14. `index.html` — render-blocking unpkg Leaflet CSS/JS for a map the app doesn't use
    (MapLibre is the live map); third-party availability risk.
15. `.env` / `.env.production` — `http://carboncast.duckdns.org:8000` plain-HTTP: if the
    UI is served over HTTPS all fetches are blocked as mixed content.
16. Falsy-zero bugs: a legitimate intensity of `0` renders as "No data"/"Loading…"
    (`InfoPopover.tsx:139-142`, `LeftPanelEM.tsx:46-53,965-972`,
    `useEnergyData.ts:794-806,852-856`).
17. `cache.ts:996-1033` — early fallback detection only handles `T`-separated
    timestamps; space-separated history rows miss the fallback banner.
18. Fallback metadata normalization (`fallback_metadata` → `metadata`) is done in
    `cache.ts` but **not** on the raw `fetch()` paths in `useEnergyData.ts:397,560,838` —
    banner missing on first fetch, appears after a cache round-trip.

### Low
19. `LegendGlass.tsx:42-60` vs `MapEM.tsx:33-57` — legend gradient stops don't align
    with `getColor` breakpoints (label "300" sits at 25% but the >300 color sits at 56%).
20. `warmCache()` (`cache.ts:473-493`) omits `region_code` → always 400s → silent no-op.
21. Window-size values read at render with no resize listener (`App.tsx:286`,
    `Timeline.tsx:384-388`, `LeftPanelEM.tsx:138-150`).
22. Module-level `isInitialLoad` flag shared/never reset across hook instances.
23. Duplicated nested `if (intensityValue !== lastValueRef.current)`
    (`useEnergyData.ts:799-806`).

---

## 4. RDA automation tool (`UCSC_OSRE_CC_automation_tool/CarbonCast`)

### Critical
1. `src/python/rdams_client.py:811-813` + `src/python/batch_automation.py:424-441` —
   empty download filelist returns a truthy dict → marked `downloaded` → **auto-purged
   at RDA**. Data permanently lost while state says success.
2. `src/python/automation/data_sync.py:428-437` vs `src/python/fix_completed_requests.py:111`
   — DB stores raw RDA statuses (`'Completed'`); the scanner queries
   `IN ('completed','ready','finished')` case-sensitively → the completed-request loop
   **never downloads anything**.
3. `src/python/batch_automation.py:88-108` — `automation_config.json` is loaded from CWD
   with a **silent** default fallback; the real config is at `config/automation_config.json`.
   Combined with the hardcoded `src/python/data/automation_state.db` path
   (`batch_automation_integrated.py:79`), there is **no working CWD**: from `src/python`
   the DB path is wrong, from repo root the config is missing. The tuned config is dead
   weight. (Corroborated by the shipped state files: 278 requests stuck in
   `queue_state.json`, empty `batch_automation_state.json`.)
4. `batch_automation.py:286,413,918` — `submitting`/`downloading` states have no exit
   transition and are missing from the completion check: crash mid-submit wedges the
   file forever; the main loop can declare completion while downloads are in flight.

### High
5. Non-atomic JSON state writes (`batch_automation.py:169`, `batch_queue_manager.py:138`,
   `batch_monitor.py:96`) — crash mid-write truncates; loader resets state to `{}`,
   orphaning live RDA requests that still hold quota slots.
6. `batch_automation.py:391` — status matching misses `"Queued for Processing"`
   (RDA's real string) → requests silently stay `submitted`.
7. `batch_automation_integrated.py:347-357,449-458` — auto-upload and queue manager
   both submit the same pending control files → double requests, quota burned,
   "crisis mode" triggered by the tool itself.
8. `upload_files.py:285-288` + `batch_automation_integrated.py:498-507` —
   request IDs and submitted files zipped by index; one ID-less success shifts every
   subsequent ID onto the wrong file → downloads land in wrong region/variable folders.
9. Two variable-naming conventions (`temp/wind/rain` vs `tmp_dpt/ugrd_vgrd/apcp`)
   split the output tree (`batch_automation.py:217` vs `region_detection_utils.py:281`);
   `fix_completed_requests.py:193` additionally defaults to `./downloads` with no region
   organization.
10. `rdams_client.py:554-577` — no request timeouts (stalled download hangs the thread
    forever), `Content-Length` KeyError when absent, no size verification → truncated
    tars reported as success then purged (compounds #1).
11. `batch_automation_integrated.py:627` — Flask dashboard on a **non-daemon** thread:
    the "completed" process never exits; cron/systemd wrappers hang.

### Medium
12. Errored RDA requests count against the 10-slot limit until max_retries purge
    (`batch_automation.py:521,846-864`).
13. `retry_count` stored as an ad-hoc attribute dropped by `asdict()` on save →
    retries reset on every restart → effectively unbounded requeueing.
14. `automation/date_manager.py:123,383` — "last N days" computed in **local time**;
    GFS cycles are UTC → edge days dropped/doubled.
15. `rdams_client.py:436` — `li.split('=', 2)` should be `maxsplit=1`; crashes on any
    value containing `=`.
16. `rdams_client.py:231` — `getattr(e,'response',{}).get(...)` raises its own
    AttributeError when `e.response` is a real Response, masking the original error.
17. Three incompatible expectations of the status response shape
    (`data_sync.py:213`, `batch_automation.py:377` vs `:516`); the `status == 'ok'`
    check makes `fetch_live_data()` a permanent no-op.

### Low
18. `upload_files.py:528` — FileHandler created before the logs dir → crash on fresh clone.
19. `download_files.py:241` — legacy path writes into never-created dirs; calls
    `rc.get_status()` at import time.

---

## 5. Other seam / docs mismatches

- `HANDOFF.md` + `docs/02-api-guide.md` reference `/carboncastapi/v1/...`; the actual
  mount is `/v1/` (`CarbonCastAPI/urls.py:45`). The UI correctly calls `/v1/`.
- `CarbonCastUI/REMOTE_SERVER_DEPLOYMENT.md` targets the retired SQLite stack, tests a
  nonexistent `/api/` route, and never sets `DJANGO_ALLOWED_HOSTS` (default allows only
  localhost → `DisallowedHost` 400 on the real domain once `DJANGO_DEBUG=False`).
- UI ↔ API endpoint contract otherwise checks out endpoint-by-endpoint (paths, casing —
  including the deliberate `regionCode` camelCase on the two forecast endpoints —,
  response shapes, CORS, `VITE_API_BASE_URL` usage).
- `/v1/SupportedRegions`, `/v1/DataFreshness`, `/v1/RetrainingStatus` exist but are
  consumed by nothing in the UI.

## Verified working
- `manage.py check` passes (with stray debug prints); all pipeline service modules
  import cleanly; Django system checks clean.
- `tsc --noEmit` clean; `vite build` succeeds (1.27 MB bundle, worth code-splitting) —
  both only with the current stale `node_modules` (see Frontend #1).
- All 58 `US_region_codes` have matching `real_time/` CSV directories; CSV fallback
  keeps the map usable with an empty DB (modulo the wrong-column bug).
- Timezone handling in the API/DB is consistently tz-aware UTC.
- No secrets tracked in git (`rdams_token.txt`, `.env`s untracked; only `.env.example`s committed).

## Suggested fix order
1. **B1** — write a real `docker-compose.yml` (+ Dockerfile) with db/redis/web/worker/beat.
2. **API criticals** — password column length; forecast-CSV column index; cache-hit
   UnboundLocalError; blank-region 500s; path traversal; `import_csvs` endswith bug.
3. **B5** — `ERCOT→ERCO`, `NYISO→NYIS` in `eia_service.py`; `ENTSOE_API_KEY` ↔ env template.
4. **B2** — tar extraction (or tar support in `ingest_weather`), shared region-code map,
   coordinate-array support in `ctl_generator`, populated `RDA_*` env defaults.
5. **RDA tool criticals** — #1–#4 in §4 (empty-download purge, scanner status,
   config loading, wedged states) before trusting any unattended run.
6. **B4** — decide whether the neural pipeline should run in-service; if yes, fix
   imports/CWD/signatures; if no, remove the dead path and document the baseline.
7. **Frontend** — regenerate `package-lock.json` and delete the leaflet-importing dead
   components (or reinstate the deps); fix UTC/local hour mixing; then the map-race and
   cache bugs.
