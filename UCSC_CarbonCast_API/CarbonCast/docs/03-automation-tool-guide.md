# Automation Tool Guide — UCSC_OSRE_CC_automation_tool

> This one is the unsung hero. It's a Python tool that automatically downloads
> the weather data the forecasting pipeline depends on, from NCAR's Research Data
> Archive (RDA). Without fresh weather, the forecasts go stale — so this keeps the
> inputs flowing.

Code lives in `UCSC_OSRE_CC_automation_tool/CarbonCast/`.

---

## The problem it solves

The CarbonCast forecasts need recent weather data — specifically NCEP GFS 0.25°
global forecast grids, dataset **`ds084.1`** on NCAR's RDA. Getting that data is
annoying for a few reasons:

- RDA limits each account to roughly **10 concurrent data requests**.
- But the workload is **~288 control files across 85+ regions** (US grid operators
  like CISO, ERCOT, PJM, MISO, NYISO, plus European countries).
- Each request has to be submitted, waited on, downloaded when ready, and then
  purged to free up quota.

Doing that by hand would be miserable. This tool automates the whole loop:

```
submit request → monitor status → download files when ready
      → organize files by REGION/variable/ → purge to free the quota → repeat
```

It also gives you a real-time **Flask web dashboard** to watch progress, and it can
**resume** where it left off if interrupted (that's what the JSON state files are
for).

---

## Weather variables it fetches

Four variables (the inputs the models care about):

- `dswrf` — downward shortwave radiation (a proxy for solar)
- ...and three others in the same family (wind/temperature-type fields)

The exact set is defined in the config; check `config/` for the authoritative list.

---

## Folder structure

```
UCSC_OSRE_CC_automation_tool/CarbonCast/
├─ README.md                  # start here
├─ CONTRIBUTING.md            # contribution conventions
├─ TROUBLESHOOTING.md         # when RDA / downloads misbehave
├─ RDA_Automation_Architecture_Analysis_and_Refactoring_Plan.md
│                              # an existing, detailed refactoring plan — read it!
├─ requirements.txt
├─ pytest.ini                 # test config
├─ batch_automation_state.json# resumable state for batch runs
├─ queue_state.json           # resumable state for the request queue
├─ ds0841.1_control.ctl       # an example RDA control file
├─ config/                    # configuration (regions, variables, credentials wiring)
├─ control_files/             # the ~288 .ctl request templates, by region
├─ docs/                      # additional documentation
├─ src/                       # the actual Python modules (the engine)
├─ templates/                 # Flask dashboard HTML templates
└─ tests/                     # pytest suite
```

> Scale note: `src/` is a large, mature codebase (tens of thousands of lines
> across ~90 modules). It's the biggest of the three projects by line count. Take
> it module by module rather than trying to read it all at once.

---

## The workflow / state machine

The tool is essentially a queue-driven state machine. The two JSON files are its
memory:

| File | Role |
|------|------|
| `queue_state.json` | Tracks the queue of RDA requests — what's pending, submitted, ready, downloaded. |
| `batch_automation_state.json` | Tracks progress across a full batch run so it can resume after a crash/restart. |

The lifecycle for a single request:

```
QUEUED ──submit──► SUBMITTED ──(RDA processes)──► READY ──download──► DOWNLOADED
                                                                         │
                                                            organize into REGION/variable/
                                                                         │
                                                                       PURGE (free quota)
```

Because RDA only allows ~10 in flight, the tool keeps a window of active requests,
submitting new ones only as old ones complete and get purged.

---

## Configuration

- Region lists, variables, and run parameters live in `config/`.
- The RDA request specifications are the `.ctl` **control files** in
  `control_files/` (one or more per region). `ds0841.1_control.ctl` at the root is
  an example you can read to understand the format.
- You'll need **RDA account credentials**. See the README / TROUBLESHOOTING for
  exactly where those go (don't commit them).

---

## Running it & running tests

```bash
cd UCSC_OSRE_CC_automation_tool/CarbonCast
pip install -r requirements.txt

# Run the test suite first — it's the fastest way to confirm your environment works
pytest

# Then launch the tool / dashboard per the README's entry-point instructions.
```

The README is the canonical source for the exact command-line entry points and the
dashboard URL. If something breaks mid-run, `TROUBLESHOOTING.md` is genuinely
helpful and worth reading before you start debugging.

---

## Already-existing refactoring plan

This project ships with its own architecture analysis:
`RDA_Automation_Architecture_Analysis_and_Refactoring_Plan.md`. **Read it.** It
predates this handoff doc and lays out the maintainers' own thinking on how the
codebase should evolve. The high-level themes it raises:

- The codebase grew large and would benefit from clearer module boundaries
  (separating queue management, RDA communication, download/organization, and the
  web dashboard).
- Consolidating configuration and state handling.
- Improving testability and reducing coupling.

When in doubt, defer to that document for this project's direction — our
cross-project reorganization notes ([`04-reorganization-recommendations.md`](04-reorganization-recommendations.md))
build on top of it rather than replacing it.

---

## Gotchas & honest notes

- **State files are committed.** `queue_state.json` and `batch_automation_state.json`
  in the repo reflect a past run. Don't assume they represent a clean slate — you
  may want to reset them before a fresh batch.
- **RDA is the external dependency that fails most.** Quota limits, slow request
  processing, and credential issues are the usual suspects. `TROUBLESHOOTING.md`
  covers them.
- **It's the largest project here.** Don't let the size intimidate you — the
  workflow above is the whole story; everything in `src/` is in service of that
  submit→download→organize→purge loop.
