# Frontend Guide — CarbonCastUI

> This is the React/TypeScript web app — the part users actually see. It draws a
> world map where each grid region is shaded by how "dirty" its electricity is
> right now (green = clean, dark red = carbon-heavy), and lets you scrub through
> time to see history, the current hour, or a forecast.

Code lives in `CarbonCastUI/web/`. Everything interesting is under `src/`.

---

## What it does, in plain English

1. On load, it fetches carbon-intensity data for all supported regions from the
   backend API.
2. It paints those regions onto a MapLibre map as a **choropleth** (colored
   shapes).
3. You can hover a region for a tooltip, or click it to zoom in and open a
   **detail panel** showing the energy mix (how much came from solar, gas, coal,
   etc.) and intensity-over-time charts.
4. A **timeline** at the bottom lets you switch between `history` / `now` /
   `forecast` and pick a specific date + hour. The map re-colors to match.

---

## Tech stack

| Concern | Choice |
|---------|--------|
| Framework | React 19.1 + TypeScript ~5.8 |
| Build tool | Vite 7 (`@vitejs/plugin-react`) |
| Routing | react-router-dom 6 (`/map`, `/zone/:region`) |
| Map | MapLibre GL via `react-map-gl` (this is the one actually used) |
| Charts | Chart.js + react-chartjs-2 |
| Styling | Tailwind CSS + some hand-written CSS / "glass" components |

> ⚠️ Heads-up: `package.json` also lists **Leaflet, react-leaflet, and
> mapbox-choropleth**. These are leftovers from an earlier map implementation and
> are mostly *not used* anymore. Don't add new code against them — the live map is
> MapLibre. (Removing them is on the cleanup list in the reorganization doc.)

---

## Folder structure

```
CarbonCastUI/
├─ README.md                  # canonical setup instructions
├─ LOCAL_DEVELOPMENT.md       # running against a local API
├─ REMOTE_SERVER_DEPLOYMENT.md# deploying to the shared server
└─ web/
   ├─ index.html              # Vite entry HTML
   ├─ package.json            # deps + scripts
   ├─ vite.config.ts          # build config
   ├─ tailwind.config.js
   ├─ public/                 # static assets + legacy CSS / geo JS
   │   ├─ us-states.js         # US balancing-authority geometries
   │   ├─ world.js             # world/Europe geometries
   │   └─ legacy-*.css         # old styles kept around
   └─ src/
       ├─ main.tsx            # React root + Router bootstrap
       ├─ App.tsx             # top-level view: wires map + timeline + panels
       ├─ index.css / App.css # global styles
       ├─ components/         # all UI pieces (see below)
       ├─ hooks/              # data fetching, caching, settings, theme
       └─ utils/              # constants, date helpers, region mapping, logging
```

### Components (`src/components/`) — one line each

| File | What it does |
|------|--------------|
| `MapEM.tsx` | The main map component (MapLibre). Big one — owns the choropleth, hover, click-to-zoom. |
| `MapLibreMap.tsx` / `MapLibreChoropleth.tsx` | Lower-level MapLibre wrappers used by the map. |
| `Choropleth.tsx` | Coloring logic / layer for the shaded regions. |
| `MapEventBridge.tsx` | Plumbs map events (hover/click) back up to React state. |
| `DynamicTileLayer.tsx` | Base map tiles. |
| `Timeline.tsx` | The bottom scrubber: history / now / forecast + date + hour. |
| `TimeControllerWrapper.tsx` | Wraps timeline state handling. |
| `TimelineLoadingOverlay.tsx` | The "loading the rest of the day…" overlay. |
| `LeftPanelEM.tsx` | The per-region detail panel (energy mix + charts). |
| `DiagnosticLeftPanel.tsx` | A debug/diagnostic variant of the left panel. |
| `AppSidebar.tsx` (+ `.css`) | The main navigation sidebar. |
| `TopControls.tsx` | Top-of-screen controls (region search, mode toggles). |
| `MenuDrawer.tsx` | Slide-out menu. |
| `SettingsModal.tsx` | User settings dialog. |
| `LegendGlass.tsx` | The color legend for the map. |
| `InfoPopover.tsx` | The "what does this mean?" info popover. |
| `DataStatusIndicator.tsx` | Shows when data is fresh vs. a fallback. Exports the `FallbackInfo` type. |
| `LoadingBar.tsx` | Thin progress bar. |
| `GlassContainer.tsx` | Reusable frosted-glass panel wrapper. |
| `Logo.tsx` | The CarbonCast logo. |

### Hooks (`src/hooks/`)

| File | What it does |
|------|--------------|
| `cache.ts` | **The heart of data flow.** Fetches carbon-intensity data, caches it, exposes `useCarbonIntensityData(timelineState)`, plus `warmCache` / `initializeCache`. Also defines the `TimelineState` type. |
| `cache-optimized.ts` | An alternate/optimized caching path. (Two cache files exist — see cleanup notes.) |
| `useEnergyData.ts` | Fetches the energy-mix breakdown for a region (used by the left panel). |
| `useSettingsState.ts` | Reads/writes user settings. |
| `useTheme.ts` | Light/dark theme handling. |
| `performance-logger.ts` | Dev-time performance instrumentation. |

### Utils (`src/utils/`)

| File | What it does |
|------|--------------|
| `constants.ts` | Shared constants (region lists, color scales, API paths, etc.). |
| `regionMapping.ts` | Maps between region codes, display names, and map geometry IDs. |
| `dateUtils.ts` | Date/hour formatting and timezone helpers. |
| `debugLogger.ts` | A toggle-able logger so we don't ship `console.log` spam. |

---

## How data flows (the mental model)

```
Timeline.tsx  ──(user picks mode/date/hour)──►  timelineState (in App.tsx)
                                                      │
                                                      ▼
                                useCarbonIntensityData(timelineState)   ← hooks/cache.ts
                                                      │ fetch + cache
                                                      ▼
                                              carbonData object
                                            ┌─────────┴──────────┐
                                            ▼                    ▼
                                        MapEM.tsx           DataStatusIndicator.tsx
                                    (colors the map)        (fresh vs fallback)
                                            │
                              (user clicks a region)
                                            ▼
                                       LeftPanelEM.tsx  ──► useEnergyData.ts
                                    (energy mix + charts)
```

`App.tsx` is the conductor: it holds `selectedRegion`, `timelineState`, panel
visibility, and the "is a fallback being shown?" logic, and passes those down.

The caching layer is intentionally clever: it fetches the **current hour first**
(so the map paints fast), then loads the remaining 23 hours of the day in the
background, showing a progress overlay. Keep that in mind before "simplifying" it.

---

## Connecting to the backend

The UI talks to the Django API over HTTP. The base URL comes from an environment
variable read at build time by Vite:

```
# CarbonCastUI/web/.env
VITE_API_BASE_URL=http://localhost:8000      # or the deployed API URL
```

Anything Vite should expose to the browser **must** be prefixed with `VITE_`.
The actual endpoint paths the UI calls (e.g. `CarbonIntensity`,
`EnergySources`, `SupportedRegions`) are documented in the
[API guide](02-api-guide.md).

---

## Running, building, deploying

```bash
cd CarbonCastUI/web
npm install
npm run dev        # local dev server with hot reload
npm run build      # production build into dist/
npm run preview    # serve the production build locally to sanity-check it
npm run lint       # eslint
```

- For local development against a local API, follow `web/LOCAL_DEVELOPMENT.md`.
- For deploying to the shared server, follow `REMOTE_SERVER_DEPLOYMENT.md`.

---

## Gotchas & things future-you will thank present-you for knowing

- **`App.tsx` is ~340 lines and does a lot.** It holds map state, timeline state,
  panel state, *and* the fallback-detection logic. It's readable but dense. If you
  add features, consider pulling logic into hooks rather than growing it.
- **Two cache implementations** (`cache.ts` and `cache-optimized.ts`) coexist.
  Make sure you know which one `App.tsx` actually imports (currently `cache.ts`)
  before editing the other.
- **`any` types show up** in a few spots (e.g. `selectedRegionBounds: any`).
  Tightening these is a safe, incremental win.
- **Geometry lives in `public/us-states.js` and `public/world.js`** as plain JS,
  not JSON. If a region won't render, the cause is often a mismatch between a
  region code and its geometry ID — check `utils/regionMapping.ts`.
- **Legacy CSS in `public/legacy-*.css`** is kept for reference; new styling
  should go through Tailwind or the existing component CSS.
