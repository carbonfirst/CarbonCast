#!/usr/bin/env python3
"""
Continuous-operation wrapper for the RDA batch automation system.

batch_automation.py is a run-to-completion program: it exits when every
control file has been downloaded or permanently failed. The Django pipeline
regenerates control files weekly (Monday 03:00 UTC), so something must
notice the new files and start a fresh run. This wrapper is that something —
a small supervisor loop designed to run under supervisord/systemd with
autorestart:

    while True:
        run batch_automation --process-all-control-files --reprocess-changed
        wait; re-run when ctl files change or incomplete work remains

It deliberately runs batch_automation as a subprocess (not in-process) so
that a crash in the automation system never takes the supervisor down, and
each run starts from clean state.

Usage:
    python run_automation_loop.py [--config CONFIG] [--poll-minutes 15]
                                  [--control-files-dir DIR] [--once]
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - automation_loop - %(levelname)s - %(message)s',
)
logger = logging.getLogger('automation_loop')

SCRIPT_DIR = Path(__file__).resolve().parent

# statuses that mean a request still needs work (mirror batch_automation)
INCOMPLETE_STATUSES = {
    'pending', 'submitting', 'submitted', 'processing',
    'ready_for_download', 'downloading',
}

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %s; shutting down after current run", signum)
    _shutdown = True


def _ctl_fingerprint(control_dir: Path):
    """(name, mtime) set for all ctl files — detects regeneration."""
    if not control_dir.is_dir():
        return frozenset()
    return frozenset(
        (f.name, round(f.stat().st_mtime, 2))
        for f in control_dir.glob('*.ctl')
    )


def _has_incomplete_state(state_file: Path) -> bool:
    if not state_file.exists():
        return False
    try:
        with open(state_file) as f:
            state = json.load(f)
    except (ValueError, OSError):
        logger.warning("State file unreadable; assuming incomplete work")
        return True
    return any(
        entry.get('status') in INCOMPLETE_STATUSES
        for entry in state.values()
    )


def _run_batch_automation(config: str) -> int:
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / 'batch_automation.py'),
        '--process-all-control-files',
        '--reprocess-changed',
        '--config', config,
    ]
    logger.info("Starting batch automation: %s", ' '.join(cmd))
    proc = subprocess.Popen(cmd, cwd=str(SCRIPT_DIR))
    while proc.poll() is None:
        if _shutdown:
            logger.info("Forwarding SIGTERM to batch automation (pid %s)", proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
            break
        time.sleep(5)
    rc = proc.returncode if proc.returncode is not None else -1
    logger.info("Batch automation exited with code %s", rc)
    return rc


def main():
    parser = argparse.ArgumentParser(description='Continuous RDA automation supervisor loop')
    parser.add_argument('--config', default='automation_config.json',
                        help='Config path forwarded to batch_automation.py')
    parser.add_argument('--control-files-dir', default=str(SCRIPT_DIR / 'control_files'),
                        help='Directory watched for regenerated .ctl files')
    parser.add_argument('--state-file', default=str(SCRIPT_DIR / 'batch_automation_state.json'),
                        help='batch_automation state file (checked for incomplete work)')
    parser.add_argument('--poll-minutes', type=float, default=15,
                        help='How often to check for new work when idle')
    parser.add_argument('--backoff-minutes', type=float, default=5,
                        help='Wait after a crashed run before retrying')
    parser.add_argument('--once', action='store_true',
                        help='Run a single batch cycle and exit (for testing)')
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    control_dir = Path(args.control_files_dir)
    state_file = Path(args.state_file)

    logger.info("Automation loop starting (control_files=%s, poll=%.0f min)",
                control_dir, args.poll_minutes)

    last_fingerprint = frozenset()

    while not _shutdown:
        fingerprint = _ctl_fingerprint(control_dir)
        ctl_changed = fingerprint != last_fingerprint and bool(fingerprint)
        incomplete = _has_incomplete_state(state_file)

        if ctl_changed or incomplete:
            reason = 'control files changed' if ctl_changed else 'incomplete requests in state'
            logger.info("Work detected (%s) — launching batch automation", reason)
            rc = _run_batch_automation(args.config)
            last_fingerprint = _ctl_fingerprint(control_dir)
            if args.once:
                sys.exit(rc)
            if rc != 0 and not _shutdown:
                logger.warning("Run failed (rc=%s); backing off %.0f min",
                               rc, args.backoff_minutes)
                _sleep_interruptible(args.backoff_minutes * 60)
                continue
        else:
            if args.once:
                logger.info("No work to do")
                sys.exit(0)

        _sleep_interruptible(args.poll_minutes * 60)

    logger.info("Automation loop stopped")


def _sleep_interruptible(seconds: float):
    deadline = time.monotonic() + seconds
    while not _shutdown and time.monotonic() < deadline:
        time.sleep(min(5, max(0, deadline - time.monotonic())))


if __name__ == '__main__':
    main()
