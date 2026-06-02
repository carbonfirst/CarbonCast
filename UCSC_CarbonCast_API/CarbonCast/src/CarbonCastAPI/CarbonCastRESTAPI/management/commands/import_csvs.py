from django.core.management.base import BaseCommand, CommandError
import os
import csv
import logging
from django.db import transaction
from CarbonCastRESTAPI.models import EmissionActual, Forecast96
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
    help = "Import real_time actual and forecast CSVs into EmissionActual and Forecast96."

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
        patterns = (
            '_lifecycle_emissions.csv',
            '_direct_emissions.csv',
            '_lifecycle_CI_forecasts_',
            '_direct_CI_forecasts_',
            '_96hr_forecasts_',
            '_168hr_forecasts_',
        )

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
            is_forecast = any(token in filename for token in (
                '_lifecycle_CI_forecasts_',
                '_direct_CI_forecasts_',
                '_96hr_forecasts_',
                '_168hr_forecasts_',
            ))
            if is_forecast:
                self.stdout.write(f"Processing forecast {filename} (region={region})")
                try:
                    ins, upd, skipped = self._import_forecast_file(filepath, filename, region)
                    rows_inserted += ins
                    rows_updated += upd
                    rows_skipped += skipped
                except Exception as e:
                    files_skipped += 1
                    errors += 1
                    logger.exception("Error processing forecast file %s: %s", filepath, e)
                continue

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

    def _import_forecast_file(self, filepath, filename, region):
        """Import CarbonCast forecast CSVs into Forecast96."""
        inserted = 0
        updated = 0
        skipped = 0

        if '_lifecycle_CI_forecasts_' in filename:
            forecast_type = 'lifecycle'
        elif '_direct_CI_forecasts_' in filename:
            forecast_type = 'direct'
        else:
            forecast_type = 'energy'

        forecast_horizon = 168 if '_168hr_forecasts_' in filename else 96
        batch_id = os.path.splitext(filename)[0][-64:]

        with open(filepath, newline='') as csvfile:
            sample = csvfile.read(8192)
            csvfile.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample) if sample else csv.excel
            except Exception:
                dialect = csv.excel

            reader = csv.DictReader(csvfile, dialect=dialect)
            if not reader.fieldnames:
                return inserted, updated, skipped

            fieldnames = [f.strip() for f in reader.fieldnames]
            reader.fieldnames = fieldnames

            with transaction.atomic():
                for row in reader:
                    try:
                        dt = self._extract_datetime_from_map(row)
                        if dt is None:
                            raise ValueError("could not parse forecast timestamp")
                        if dt.tzinfo is None:
                            dt = make_aware(dt)

                        if forecast_type == 'energy':
                            data_blob = self._normalize_energy_forecast_row(row)
                            numeric_values = [
                                self._coerce_float(v)
                                for k, v in data_blob.items()
                                if k.endswith('_production_forecast')
                            ]
                            valid_values = [v for v in numeric_values if v is not None]
                            value = sum(valid_values) if valid_values else 0.0
                        else:
                            data_blob = dict(row)
                            value = self._extract_forecast_value(row, forecast_type)
                            if value is None:
                                raise ValueError("could not parse forecast value")
                            data_blob['carbon_intensity_unit'] = data_blob.get(
                                'carbon_intensity_unit',
                                'gCO2eg/kWh',
                            )

                        data_blob['source_file'] = filename
                        data_blob['batch_id'] = batch_id
                        data_blob['forecast_horizon'] = forecast_horizon

                        _, created = Forecast96.objects.update_or_create(
                            region=region,
                            ts=dt,
                            forecast_type=forecast_type,
                            defaults={
                                'value': value,
                                'forecast_horizon': forecast_horizon,
                                'batch_id': batch_id,
                                'data': data_blob,
                            },
                        )
                        if created:
                            inserted += 1
                        else:
                            updated += 1
                    except Exception as e:
                        skipped += 1
                        logger.exception("Skipping malformed forecast row in %s: %s", filename, e)

        return inserted, updated, skipped

    def _extract_forecast_value(self, row_map, forecast_type):
        keys = [
            f'forecasted_avg_carbon_intensity_{forecast_type}',
            'forecasted_avg_carbon_intensity',
            f'carbon_intensity_avg_{forecast_type}',
            'carbon_intensity',
            'value',
        ]
        for key in keys:
            for row_key, row_value in row_map.items():
                if row_key.strip().lower() == key:
                    value = self._coerce_float(row_value)
                    if value is not None:
                        return value
        for row_value in row_map.values():
            value = self._coerce_float(row_value)
            if value is not None:
                return value
        return None

    def _normalize_energy_forecast_row(self, row_map):
        source_fields = {
            'coal': 'avg_coal_production_forecast',
            'nat_gas': 'avg_nat_gas_production_forecast',
            'nuclear': 'avg_nuclear_production_forecast',
            'oil': 'avg_oil_production_forecast',
            'hydro': 'avg_hydro_production_forecast',
            'solar': 'avg_solar_production_forecast',
            'wind': 'avg_wind_production_forecast',
            'other': 'avg_other_production_forecast',
        }
        data_blob = dict(row_map)
        lower_map = {k.strip().lower(): v for k, v in row_map.items()}
        for source, target_key in source_fields.items():
            if target_key not in data_blob:
                data_blob[target_key] = lower_map.get(source, lower_map.get(target_key, "0"))
        return data_blob

    def _coerce_float(self, value):
        try:
            return float(value) if value not in (None, '') else None
        except Exception:
            return None
