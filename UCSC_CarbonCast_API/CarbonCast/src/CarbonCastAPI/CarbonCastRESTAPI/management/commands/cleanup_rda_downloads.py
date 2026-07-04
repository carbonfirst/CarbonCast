"""
Reclaim disk from RDA weather downloads that have already been ingested.

The ingest_weather command records every processed file in
processed_files.json (rel_path -> ingestion timestamp ISO string) next to
the download root. This command deletes (or archives) files whose ingestion
timestamp is older than the retention window. Manifest entries are KEPT so
a re-appearing file is not re-ingested.

Safety properties:
- Only files listed in the manifest (i.e., verified ingested) are touched.
- Disabled unless RDA_CLEANUP_ENABLED=true or --force is passed.
- --dry-run reports what would be removed without touching anything.
"""

import json
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "Delete or archive ingested RDA weather downloads past the retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            '--path', default=None,
            help='Download root (defaults to RDA_DOWNLOAD_DIR)',
        )
        parser.add_argument(
            '--retention-days', type=int, default=None,
            help='Days to keep ingested files (defaults to RDA_RETENTION_DAYS or 14)',
        )
        parser.add_argument(
            '--archive-dir', default=None,
            help='Move files here instead of deleting (defaults to RDA_ARCHIVE_DIR; unset = delete)',
        )
        parser.add_argument('--dry-run', action='store_true', help='Report only, change nothing')
        parser.add_argument('--force', action='store_true', help='Run even if RDA_CLEANUP_ENABLED is not set')

    def handle(self, *args, **options):
        root = options['path'] or os.environ.get('RDA_DOWNLOAD_DIR', '')
        if not root or not os.path.isdir(root):
            self.stdout.write(f"Download dir not found: {root!r}")
            return

        enabled = _truthy(os.environ.get('RDA_CLEANUP_ENABLED')) or options['force']
        if not enabled and not options['dry_run']:
            self.stdout.write("Cleanup disabled (set RDA_CLEANUP_ENABLED=true or pass --force); "
                              "running as dry-run instead")
            options['dry_run'] = True

        retention_days = options['retention_days']
        if retention_days is None:
            retention_days = int(os.environ.get('RDA_RETENTION_DAYS', '14'))
        archive_dir = options['archive_dir'] or os.environ.get('RDA_ARCHIVE_DIR', '')

        manifest_path = os.path.join(root, 'processed_files.json')
        if not os.path.exists(manifest_path):
            self.stdout.write("No processed_files.json manifest; nothing verified as ingested")
            return

        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except Exception:
            self.stdout.write("Manifest unreadable; refusing to clean")
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        removed = 0
        archived = 0
        kept = 0
        missing = 0
        bytes_freed = 0

        for rel_path, ingested_at in manifest.items():
            try:
                ingested = datetime.fromisoformat(str(ingested_at))
                if ingested.tzinfo is None:
                    ingested = ingested.replace(tzinfo=timezone.utc)
            except Exception:
                kept += 1
                continue

            if ingested >= cutoff:
                kept += 1
                continue

            abs_path = os.path.join(root, rel_path)
            if not os.path.isfile(abs_path):
                missing += 1
                continue

            size = os.path.getsize(abs_path)
            if options['dry_run']:
                self.stdout.write(f"[dry-run] would remove {rel_path} ({size / 1e6:.1f} MB)")
                removed += 1
                bytes_freed += size
                continue

            try:
                if archive_dir:
                    dest = os.path.join(archive_dir, rel_path)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.move(abs_path, dest)
                    archived += 1
                else:
                    os.remove(abs_path)
                    removed += 1
                bytes_freed += size
            except OSError:
                logger.exception("Failed to remove %s", abs_path)

        summary = (
            f"retention_days: {retention_days}\n"
            f"removed: {removed}\n"
            f"archived: {archived}\n"
            f"kept (within retention): {kept}\n"
            f"already gone: {missing}\n"
            f"space freed: {bytes_freed / 1e9:.2f} GB"
            + (" (dry-run)" if options['dry_run'] else "")
        )
        self.stdout.write(summary)
        logger.info("cleanup_rda_downloads: %s", summary.replace('\n', ' | '))
