import os
import time
import logging
from typing import Dict
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Periodic importer daemon that watches a real_time/ folder for new or modified
    lifecycle/direct emissions CSV files and triggers the existing `import_csvs`
    command when changes are detected.

    Design:
    - On startup: snapshot file mtimes for *_lifecycle_emissions.csv and *_direct_emissions.csv
      and run a full import once (unless --no-initial-import given).
    - Loop every --interval seconds (default 300) and rescan:
        * If any target file is new or its mtime increased: run `import_csvs --path <path>`
        * Update snapshot
    - Optional exit conditions:
        * --max-loops N : stop after N scan iterations (useful for CI)
        * --once-if-idle : perform at most one additional import; if no changes after initial import, exit
    - Idempotent: relies on update_or_create in import_csvs so reprocessing is safe.

    Usage examples:
        python manage.py import_daemon --path real_time
        python manage.py import_daemon --path real_time --interval 60
        python manage.py import_daemon --path real_time --once-if-idle
        python manage.py import_daemon --path real_time --max-loops 10

    NOTE: This implementation avoids external dependencies (e.g. watchdog) for simplicity.
    """

    help = "Run a lightweight loop to automatically import new / modified emissions CSV files."

    TARGET_PATTERNS = ("_lifecycle_emissions.csv", "_direct_emissions.csv")

    def add_arguments(self, parser):
        parser.add_argument("--path", required=True, help="Path to root real_time folder")
        parser.add_argument("--interval", type=int, default=300, help="Seconds between scans (default: 300)")
        parser.add_argument("--no-initial-import", action="store_true", help="Skip the initial full import on startup")
        parser.add_argument("--max-loops", type=int, default=None, help="Maximum scan iterations before exiting")
        parser.add_argument("--once-if-idle", action="store_true",
                            help="Exit after first loop if no changes detected since last import")
        parser.add_argument("--verbose", action="store_true", help="Increase logging verbosity")

    def handle(self, *args, **options):
        path = options["path"]
        interval = options["interval"]
        no_initial = options["no_initial_import"]
        max_loops = options["max_loops"]
        once_if_idle = options["once_if_idle"]
        verbose = options["verbose"]

        if verbose:
            logger.setLevel(logging.INFO)

        if not os.path.exists(path):
            raise CommandError(f"Path does not exist: {path}")

        self.stdout.write(self.style.SUCCESS(
            f"[import_daemon] Starting watcher path={path} interval={interval}s"
        ))

        snapshot = self._collect_state(path)

        if not no_initial:
            self._run_import(path, reason="initial import")

        loops = 0
        imports_run = 0
        idle_cycles = 0

        try:
            while True:
                if max_loops is not None and loops >= max_loops:
                    self.stdout.write(self.style.SUCCESS(
                        f"[import_daemon] Reached max loops ({max_loops}); exiting."
                    ))
                    break

                loops += 1
                time.sleep(interval)

                new_snapshot = self._collect_state(path)
                changed = self._detect_changes(snapshot, new_snapshot)

                if changed:
                    imports_run += 1
                    self._run_import(path, reason=f"detected {changed} changed/new file(s)")
                    snapshot = new_snapshot
                    idle_cycles = 0
                else:
                    idle_cycles += 1
                    logger.info("[import_daemon] No changes detected (loop=%d idle_cycles=%d)", loops, idle_cycles)
                    if once_if_idle and imports_run > 0:
                        self.stdout.write(self.style.SUCCESS(
                            "[import_daemon] Idle after prior import and --once-if-idle set; exiting."
                        ))
                        break

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("[import_daemon] Interrupted by user (Ctrl+C)."))

        self.stdout.write(self.style.SUCCESS(
            f"[import_daemon] Finished loops={loops} imports_run={imports_run}"
        ))

    # --- internal helpers -------------------------------------------------

    def _collect_state(self, root: str) -> Dict[str, float]:
        """
        Walk the directory and capture mtimes for target CSV files.
        Returns dict: {absolute_path: mtime}
        """
        state: Dict[str, float] = {}
        for dirpath, _, files in os.walk(root):
            for f in files:
                if f.endswith(self.TARGET_PATTERNS):
                    full = os.path.join(dirpath, f)
                    try:
                        state[full] = os.path.getmtime(full)
                    except OSError:
                        continue
        logger.info("[import_daemon] Collected state with %d files", len(state))
        return state

    def _detect_changes(self, old: Dict[str, float], new: Dict[str, float]) -> int:
        """
        Return count of files that are new or whose mtime increased.
        """
        changed = 0
        for path, mtime in new.items():
            old_mtime = old.get(path)
            if old_mtime is None or mtime > old_mtime:
                changed += 1
        return changed

    def _run_import(self, path: str, reason: str):
        """
        Invoke the existing import_csvs command.
        """
        self.stdout.write(self.style.NOTICE(f"[import_daemon] Running import_csvs ({reason})"))
        start = time.time()
        try:
            call_command("import_csvs", path=path)
        except Exception as e:
            logger.exception("Error running import_csvs: %s", e)
            self.stdout.write(self.style.ERROR(f"[import_daemon] import_csvs failed: {e}"))
        else:
            duration = time.time() - start
            self.stdout.write(self.style.SUCCESS(
                f"[import_daemon] import_csvs completed in {duration:.2f}s ({reason})"
            ))