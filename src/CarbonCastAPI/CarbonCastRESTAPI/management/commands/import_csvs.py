from django.core.management.base import BaseCommand, CommandError
import os
import csv
import logging
from django.db import transaction
from CarbonCastRESTAPI.models import EmissionActual
from datetime import datetime
from django.utils.timezone import make_aware

# Prefer dateutil for robust parsing when available
try:
    from dateutil import parser as dateutil_parser
    HAVE_DATEUTIL = True
except Exception:
    dateutil_parser = None
    HAVE_DATEUTIL = False

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import lifecycle and direct emissions CSVs into the EmissionActual model."

    def add_arguments(self, parser):
        parser.add_argument('--path', required=True, help='Path to real_time folder containing CSV files')

    def handle(self, *args, **options):
        path = options.get('path')
        if not path:
            raise CommandError("--path is required")

        if not os.path.exists(path):
            # requirement: if path does not exist, print "no files found" and exit 0
            self.stdout.write("no files found")
            return 0

        # target filename patterns
        patterns = ('_lifecycle_emissions.csv', '_direct_emissions.csv')

        # discover files
        files_found = []
        for root, dirs, files in os.walk(path):
            for f in files:
                if f.endswith(patterns):
                    files_found.append(os.path.join(root, f))

        if not files_found:
            self.stdout.write("no files found")
            return 0

        # counters
        files_processed = 0
        rows_inserted = 0
        rows_updated = 0
        files_skipped = 0
        rows_skipped = 0
        errors = 0

        # process each file one-by-one (atomic per-file)
        for filepath in files_found:
            files_processed += 1
            filename = os.path.basename(filepath)
            # infer region from filename prefix before first underscore
            region = filename.split('_')[0] if '_' in filename else filename
            is_lifecycle = filename.endswith('_lifecycle_emissions.csv')
            is_direct = filename.endswith('_direct_emissions.csv')
            if not (is_lifecycle or is_direct):
                files_skipped += 1
                continue

            self.stdout.write(f"Processing {filename} (region={region})")

            try:
                with open(filepath, newline='') as csvfile:
                    # Read a sample to detect dialect and header presence
                    sample = csvfile.read(8192)
                    csvfile.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(sample) if sample else csv.excel
                    except Exception:
                        dialect = csv.excel

                    has_header = False
                    try:
                        has_header = csv.Sniffer().has_header(sample)
                    except Exception:
                        has_header = False

                    reader = csv.reader(csvfile, dialect)
                    headers = None
                    if has_header:
                        try:
                            headers = next(reader)
                        except StopIteration:
                            self.stdout.write(f"Empty file: {filename}")
                            files_skipped += 1
                            continue
                        # normalize headers whitespace
                        headers = [h.strip() for h in headers]

                    # Use transaction per-file to ensure atomic commit
                    with transaction.atomic():
                        for row in reader:
                            # low-memory processing: row-by-row
                            if not row or all((c is None or str(c).strip() == '') for c in row):
                                continue  # skip empty rows

                            try:
                                if headers:
                                    # map columns to header names
                                    row_map = {k: v for k, v in zip(headers, row)}
                                    dt = self._extract_datetime_from_map(row_map)
                                    # extract both lifecycle and direct when headers exist
                                    lifecycle_val, direct_val = self._extract_values_from_map(row_map)
                                    data_blob = row_map
                                else:
                                    # no header: assume first column datetime, second is value
                                    dt = self._parse_datetime(row[0])
                                    lifecycle_val = None
                                    direct_val = None
                                    try:
                                        value = float(row[1]) if len(row) > 1 and row[1] != '' else None
                                    except Exception:
                                        value = None
                                    # attribute the value based on filename semantics
                                    if is_lifecycle:
                                        lifecycle_val = value
                                    else:
                                        direct_val = value
                                    data_blob = None

                                if dt is None:
                                    raise ValueError("could not parse datetime")

                                # ensure tz-aware datetimes for DB storage
                                try:
                                    if dt.tzinfo is None:
                                        dt = make_aware(dt)
                                except Exception:
                                    # if make_aware fails, continue and let DB handle or skip row
                                    pass

                                defaults = {'source_file': filename}
                                # store lifecycle/direct when present in headers or inferred
                                if lifecycle_val is not None:
                                    defaults['lifecycle'] = lifecycle_val
                                if direct_val is not None:
                                    defaults['direct'] = direct_val
                                if data_blob is not None:
                                    defaults['data'] = data_blob

                                # upsert: unique_together (region, ts)
                                obj, created = EmissionActual.objects.update_or_create(
                                    region=region, ts=dt, defaults=defaults
                                )
                                if created:
                                    rows_inserted += 1
                                else:
                                    rows_updated += 1
                            except Exception as e:
                                rows_skipped += 1
                                logger.exception("Skipping malformed row in %s: %s", filename, e)
                                continue
            except Exception as e:
                files_skipped += 1
                errors += 1
                logger.exception("Error processing file %s: %s", filepath, e)
                continue

        # print summary (both to stdout and logger)
        summary_lines = [
            f"files_processed: {files_processed}",
            f"files_skipped: {files_skipped}",
            f"rows_inserted: {rows_inserted}",
            f"rows_updated: {rows_updated}",
            f"rows_skipped: {rows_skipped}",
            f"errors: {errors}",
        ]
        for line in summary_lines:
            self.stdout.write(line)
            logger.info(line)

        # non-zero exit if unexpected exceptions occurred
        if errors:
            raise CommandError("Errors occurred during import; see logs")

        return 0

    def _parse_datetime(self, s):
        """Parse datetime string using dateutil when available, then fromisoformat, then common formats."""
        if s is None:
            return None
        s = str(s).strip()
        if s == '':
            return None

        # try dateutil if available
        if HAVE_DATEUTIL and dateutil_parser:
            try:
                return dateutil_parser.parse(s)
            except Exception:
                pass

        # try datetime.fromisoformat
        try:
            return datetime.fromisoformat(s)
        except Exception:
            pass

        # fallback common formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue

        return None

    def _extract_datetime_from_map(self, row_map):
        """Given a dict of header->value, find the best datetime column and parse it."""
        candidates = []
        for k in row_map.keys():
            kl = k.strip().lower()
            if 'time' in kl or 'date' in kl or kl in ('ts', 'timestamp', 'datetime'):
                candidates.append(k)

        if not candidates:
            # fallback: first column
            first_key = next(iter(row_map.keys()))
            return self._parse_datetime(row_map[first_key])

        # prefer exact names
        for prefer in ('ts', 'timestamp', 'datetime'):
            for c in candidates:
                if c.strip().lower() == prefer:
                    return self._parse_datetime(row_map[c])

        # otherwise use first candidate
        return self._parse_datetime(row_map[candidates[0]])

    def _extract_values_from_map(self, row_map):
        """
        Given a mapped row (headers->values) attempt to extract both lifecycle and direct numeric values.
        Uses a heuristic list of candidate header names to find best matches. Returns (lifecycle_val, direct_val)
        or (None, None) when not present.
        """
        lifecycle_keys = [
            'lifecycle', 'carbon_intensity_avg_lifecycle', 'carbon_intensity_lifecycle',
            'carbon_intensity_avg', 'carbon_intensity', 'ci_lifecycle'
        ]
        direct_keys = [
            'direct', 'carbon_intensity_avg_direct', 'carbon_intensity_direct',
            'carbon_intensity', 'ci_direct'
        ]
        generic_value_keys = ['value', 'val']

        lifecycle_val = None
        direct_val = None

        # helper to coerce
        def _coerce(v):
            try:
                return float(v) if v not in (None, '') else None
            except Exception:
                return None

        # normalize map lookup: try exact or containing matches
        for k in row_map.keys():
            kl = k.strip().lower()
            if any(kl == lk or lk in kl for lk in lifecycle_keys) and lifecycle_val is None:
                lifecycle_val = _coerce(row_map[k])
            if any(kl == dk or dk in kl for dk in direct_keys) and direct_val is None:
                direct_val = _coerce(row_map[k])

        # If both still None, fall back to generic 'carbon_intensity' or 'value'
        if lifecycle_val is None and direct_val is None:
            for k in row_map.keys():
                kl = k.strip().lower()
                if kl in ('carbon_intensity', 'carbon intensity', 'ci') and lifecycle_val is None:
                    lifecycle_val = _coerce(row_map[k])
                if kl in generic_value_keys and lifecycle_val is None:
                    lifecycle_val = _coerce(row_map[k])

        # Final attempt: if carbon_intensity present and one of lifecycle/direct missing, try to assign to both
        if (lifecycle_val is None or direct_val is None):
            for k in row_map.keys():
                kl = k.strip().lower()
                if kl in ('carbon_intensity', 'carbon intensity', 'ci'):
                    v = _coerce(row_map[k])
                    if lifecycle_val is None:
                        lifecycle_val = v
                    if direct_val is None:
                        direct_val = v

        return lifecycle_val, direct_val

    # Backward-compat: keep old name to minimize calling-site changes
    def _extract_value_from_map(self, row_map, lifecycle=True):
        val = self._extract_values_from_map(row_map)
        return val[0] if lifecycle else val[1]