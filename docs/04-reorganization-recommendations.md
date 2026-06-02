# Reorganization & Readability Recommendations

> This is a **low-risk, incremental** plan to make the codebase easier to read and
> work in — *without changing behavior*. Nothing here requires a big-bang rewrite.
> Each item is something you can do in an afternoon, ship, and verify. Pick them
> off in roughly the order listed (safest/highest-value first).

A guiding principle for all of this: **change structure, not behavior.** Before and
after every refactor, the API responses, the UI output, and the test results
should be identical. If you can't prove that, don't merge it.

---

## Ground rules (please read before refactoring)

1. **One concern per PR.** "Split views.py" and "rename variables" should be
   separate pull requests. Small diffs are reviewable diffs.
2. **Lean on the tools you already have.** Run `npm run lint` / `npm run build` for
   the frontend and `pytest` for the Python projects after every change.
3. **No logic changes disguised as cleanup.** If you spot a real bug while
   refactoring, fix it in its own commit so it's visible in history.
4. **Update the docs in `docs/` as you go.** If you move a file, fix the path here.

---

## Tier 1 — Quick, safe wins (do these first)

These are nearly zero-risk and immediately reduce noise.

### Frontend (`CarbonCastUI/web`)
- **✅ DONE — Removed unused map libraries.** `leaflet`, `react-leaflet`,
  `mapbox-choropleth`, and `@types/leaflet` had 0 references in `src/` and have
  been dropped from `package.json`. (`npm run build` still passes.)
- **Replace stray `console.log` with `debugLogger`.** There's already a
  `utils/debugLogger.ts` for exactly this. Route logging through it so production
  builds stay quiet.
- **Tighten obvious `any` types.** Start with `selectedRegionBounds: any` in
  `App.tsx` and similar spots. Give them real interfaces.
- **✅ DONE — One cache implementation.** The unused `hooks/cache-optimized.ts`
  was deleted; `hooks/cache.ts` is now the single source of truth.

### Backend (`UCSC_CarbonCast_API`)
- **Swap `print()` for `logging`.** ⏳ Partial — the import-time `print` is gone;
  the per-handler debug `print()`s inside the views remain. Route those through a
  module logger. Pure cleanup, big readability gain.
- **✅ DONE — De-duplicated imports.** The four duplicate `rest_framework` import
  lines in the old `views.py` were collapsed into one before the split.
- **Add a top-of-file docstring to the big modules** (`tasks.py`)
  summarizing what lives there and the section order. (The new `views/` package
  already has a docstring in its `__init__.py`.)

### Automation tool
- **Add `*_state.json` to `.gitignore`** (or move the committed ones to a
  `examples/` folder) so runtime state isn't mistaken for source.

---

## Tier 2 — Structural splits (the high-value ones)

### Split the giant Django `views.py` (~1,900 lines) — **✅ DONE**

This was the single biggest readability problem in the repo, and it was safe to
fix because Django doesn't care where a view *class* is defined, only that `urls.py`
can import it. **This has now been done** — `views.py` is a `views/` package, the
class bodies were carved out byte-for-byte, `__init__.py` re-exports everything,
and `python manage.py check` passes. The recipe below is kept for reference / in
case you split another large module the same way.

**Target layout (now in place):**

```
CarbonCastRESTAPI/
└─ views/
   ├─ __init__.py          # re-export every view so existing imports keep working
   ├─ carbon_intensity.py  # CarbonIntensity + History views
   ├─ energy_sources.py    # EnergySources + History views
   ├─ forecasts.py         # all *Forecasts* views
   ├─ regions.py           # SupportedRegions, DataFreshness
   ├─ retraining.py        # RetrainingStatus
   └─ auth.py              # SignUp, SignIn, Logout, VerifyOTP, UserAuthenticationEnforced
```

**How to do it without breaking anything:**
1. Create the `views/` folder and move each view class into the appropriate file.
2. In `views/__init__.py`, re-export them all:
   ```python
   from .carbon_intensity import CarbonIntensityApiView, CarbonIntensityHistoryApiView
   from .energy_sources import EnergySourcesApiView, EnergySourcesHistoryApiView
   # ...etc
   ```
3. `urls.py` imports stay exactly the same (`from .views import (...)`) because the
   package's `__init__.py` exposes the same names.
4. Run `pytest` and hit each endpoint. Responses must be byte-for-byte identical.

> Do the same trick for `serializers.py` and `helper.py` only if they grow large.
> Don't over-engineer small files.

### Separate "the research scripts" from "the Django app"

Right now the original research pipeline (`src/*.py`) sits next to the deployed
Django project (`src/CarbonCastAPI/`). Consider a top-level `research/` (or
`pipeline/`) folder so newcomers immediately know which code is the live service
vs. the experimental/training code. This is a *move*, so: do it in one commit,
update any import paths, and run the pipeline + API once to confirm.

### Frontend: extract logic out of `App.tsx`

`App.tsx` (~340 lines) holds map state, timeline state, panel visibility, *and* the
fallback-detection `useMemo`. Move cohesive chunks into hooks:
- `useFallbackInfo(carbonData, timelineState)` → returns `FallbackInfo | null`.
- `useSelectedRegion()` → encapsulates region selection + bounds.

The component then reads top-to-bottom like a story. No behavior changes — you're
just relocating the same code into named hooks.

### Frontend: break up the largest components

`MapEM.tsx` and `LeftPanelEM.tsx` are the big ones. You don't need to shatter them;
just peel off self-contained pieces (e.g., the tooltip, the legend interaction, a
single chart) into child components with clear props. Smaller files = easier
reviews.

---

## Tier 3 — Consistency & conventions (nice-to-have, ongoing)

- **Naming consistency.** The `EM` suffix (`MapEM`, `LeftPanelEM`) is an artifact of
  an "Electricity Maps"-style iteration. It's fine to keep, but document what it
  means (done — see the frontend guide) or rename consistently in one sweep.
- **Centralize API paths.** Make sure every endpoint string the UI calls comes from
  `utils/constants.ts`, not hard-coded in multiple hooks. One source of truth.
- **Co-locate component CSS.** `AppSidebar.tsx` has an `AppSidebar.css`; not all
  components follow that pattern. Pick one convention (co-located CSS *or* Tailwind)
  and migrate gradually.
- **Add minimal type definitions for the API responses.** A shared
  `types/api.ts` describing the carbon/energy/forecast payloads would let the whole
  frontend stop using `Record<string, unknown>` casts.
- **For the automation tool**, follow its own
  `RDA_Automation_Architecture_Analysis_and_Refactoring_Plan.md` — it already
  prescribes clearer module boundaries (queue / RDA client / downloader /
  dashboard). Don't reinvent that plan; execute it.

---

## What NOT to touch (at least not casually)

- **The CSV fallback paths** (`real_time/`, `CI_forecast_data/`). They look like dead
  data but the API reads them when the DB is empty. Removing them will silently
  break endpoints.
- **The progressive cache-warming logic** in `hooks/cache.ts` (fetch current hour
  first, then background-load the rest). It looks complex but it's a deliberate UX
  optimization. Understand it fully before simplifying.
- **The `metric_type` fields** on the models. They're "unused" today but are the
  designed-in path for adding demand/price later. Leave them.
- **Saved model directories** (`saved_first_tier_models/`, `saved_second_tier_models/`).
  These are trained artifacts, not regeneratable on a whim.

---

## Suggested order of attack

1. Tier 1 quick wins across all three projects (a day or two, immediate payoff).
2. Split `views.py` into a `views/` package (the biggest single readability win).
3. Extract hooks out of `App.tsx`.
4. Separate research scripts from the Django app.
5. Everything in Tier 3, opportunistically, whenever you're already touching a file.

Work in small, verifiable steps, keep the test suites green, and this codebase will
get noticeably friendlier without a single behavior change.
