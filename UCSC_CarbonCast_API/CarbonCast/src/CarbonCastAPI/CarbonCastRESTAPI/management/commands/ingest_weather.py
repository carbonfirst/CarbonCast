"""
Management command to ingest weather data from the RDA automation tool's
downloaded_files/ directory into the WeatherForecast model.

Usage:
    python manage.py ingest_weather --path /path/to/downloaded_files

The command accepts either downloaded_files/REGION/variable/ or flatter RDA
automation output trees. Region and weather variable are inferred from the
path first, then from the filename.

A processed_files.json manifest is maintained alongside the download directory
to avoid re-processing files.  Source files are NEVER deleted.
"""

import json
import logging
import os
import re
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)

# RDA download directories are named with the tool's region codes, which for
# some balancing authorities differ from the API's (EIA) region codes.
REGION_ALIASES = {
    'ERCOT': 'ERCO',
    'NYISO': 'NYIS',
}


def _load_rda_config_regions():
    """Region codes from the automation tool's config (via RDA_CONFIG_PATH).

    The tool covers ~72 regions while consts.US_region_codes lists only the
    ones the API serves energy data for. Weather downloads for tool-only
    regions (BANC, PNM, TEPC, ...) are still worth ingesting — they'd
    otherwise be skipped as "cannot infer region".
    """
    config_path = os.environ.get('RDA_CONFIG_PATH', '')
    if not config_path or not os.path.exists(config_path):
        return set()
    try:
        with open(config_path) as f:
            config = json.load(f)
        return {str(code).upper() for code in config.get('regions', {})}
    except Exception:
        logger.exception("Could not load regions from RDA_CONFIG_PATH=%s", config_path)
        return set()

# GFS member filenames look like gfs.0p25.2023010100.f003.grib2 —
# capture the forecast cycle (YYYYMMDDHH) and forecast hour (fNNN).
GFS_FILENAME_RE = re.compile(r'gfs\.0p25\.(\d{10})\.f(\d{3})')

KNOWN_VARIABLES = {'temp', 'wind', 'dswrf', 'rain'}
VARIABLE_ALIASES = {
    'temp': 'temp',
    'tmp': 'temp',
    't2m': 'temp',
    'temperature': 'temp',
    'wind': 'wind',
    'ugrd': 'wind',
    'vgrd': 'wind',
    'wspd': 'wind',
    'dswrf': 'dswrf',
    'solar': 'dswrf',
    'shortwave': 'dswrf',
    'apcp': 'rain',
    'precip': 'rain',
    'rain': 'rain',
}


class Command(BaseCommand):
    help = "Ingest RDA weather downloads into the WeatherForecast model."

    def add_arguments(self, parser):
        parser.add_argument(
            '--path', required=True,
            help='Root of the downloaded_files/ directory from the RDA automation tool',
        )

    def handle(self, *args, **options):
        from CarbonCastRESTAPI.models import WeatherForecast

        root = options['path']
        if not os.path.isdir(root):
            self.stdout.write(f"Path does not exist: {root}")
            return

        manifest_path = os.path.join(root, 'processed_files.json')
        processed = self._load_manifest(manifest_path)
        now = datetime.now(timezone.utc)

        files_processed = 0
        rows_inserted = 0
        rows_updated = 0
        files_skipped = 0

        for data_file in sorted(Path(root).rglob("*")):
            if not data_file.is_file():
                continue
            if data_file.name == 'processed_files.json' or data_file.name.startswith('.'):
                continue

            rel_path = str(data_file.relative_to(root))
            if rel_path in processed:
                files_skipped += 1
                continue

            region = self._infer_region(data_file, root)
            variable = self._infer_variable(data_file.relative_to(root))
            if not region or not variable:
                logger.warning("Cannot infer region/variable for %s", data_file)
                files_skipped += 1
                continue

            try:
                ins, upd = self._ingest_file(
                    data_file, region, variable, now, WeatherForecast,
                )
                rows_inserted += ins
                rows_updated += upd
                files_processed += 1
                processed[rel_path] = now.isoformat()
            except Exception:
                logger.exception("Error ingesting %s", data_file)

        self._save_manifest(manifest_path, processed)

        self.stdout.write(
            f"files_processed: {files_processed}\n"
            f"files_skipped: {files_skipped}\n"
            f"rows_inserted: {rows_inserted}\n"
            f"rows_updated: {rows_updated}"
        )

    def _known_regions(self):
        from CarbonCastRESTAPI.consts import US_region_codes

        if not hasattr(self, '_known_regions_cache'):
            self._known_regions_cache = set(US_region_codes) | _load_rda_config_regions()
        return self._known_regions_cache

    def _infer_region(self, path, root):
        known_regions = self._known_regions()
        rel_parts = [part.upper() for part in path.relative_to(root).parts]
        for part in rel_parts:
            token = part.split('.')[0]
            if token in REGION_ALIASES:
                return REGION_ALIASES[token]
            if token in known_regions:
                return token
            prefix = token.split('_')[0].split('-')[0]
            if prefix in REGION_ALIASES:
                return REGION_ALIASES[prefix]
            if prefix in known_regions:
                return prefix
        return None

    def _infer_variable(self, path):
        tokens = []
        for part in path.parts:
            normalized = part.lower().replace('-', '_').replace('.', '_')
            tokens.extend(t for t in normalized.split('_') if t)

        for token in tokens:
            if token in VARIABLE_ALIASES:
                return VARIABLE_ALIASES[token]
        return None

    def _ingest_file(self, path, region, variable, created_at, model_cls):
        """
        Parse a single downloaded weather file and write rows to the DB.

        Tries cfgrib (for GRIB) first, then xarray/netCDF4, then falls back
        to treating the file as CSV.  Returns (inserted, updated) counts.
        """
        inserted = 0
        updated = 0

        records = self._try_parse(path, region, variable, created_at)

        with transaction.atomic():
            for rec in records:
                _, created = model_cls.objects.update_or_create(
                    region=rec['region'],
                    forecast_created=rec['forecast_created'],
                    forecast_target=rec['forecast_target'],
                    variable=rec['variable'],
                    defaults={
                        'value': rec['value'],
                        'source': 'rda',
                        'data': rec.get('data'),
                    },
                )
                if created:
                    inserted += 1
                else:
                    updated += 1

        return inserted, updated

    def _try_parse(self, path, region, variable, created_at):
        """Attempt multiple parsers in order of preference."""
        suffix = path.suffix.lower()

        if suffix == '.tar' or path.name.endswith(('.grib2.tar', '.tar.gz', '.tgz')):
            return self._parse_tar(path, region, variable, created_at)
        if suffix in ('.grib', '.grib2', '.grb', '.grb2'):
            return self._parse_grib(path, region, variable, created_at)
        if suffix in ('.nc', '.nc4', '.netcdf'):
            return self._parse_netcdf(path, region, variable, created_at)
        if suffix in ('.csv', '.txt'):
            return self._parse_csv(path, region, variable, created_at)

        # Unknown extension — try grib first since that's the most common RDA format
        try:
            return self._parse_grib(path, region, variable, created_at)
        except Exception:
            pass
        try:
            return self._parse_netcdf(path, region, variable, created_at)
        except Exception:
            pass

        logger.warning("Cannot parse %s — unsupported format", path)
        return []

    def _parse_tar(self, path, region, variable, created_at):
        """
        Extract a RDA .tar archive of GFS GRIB members and parse each one.

        Member names look like gfs.0p25.2023010100.f003.grib2: the cycle
        timestamp becomes forecast_created and the fNNN hour offset gives
        forecast_target. Members without that pattern fall back to the
        archive-level created_at and the timestamps inside the GRIB data.
        """
        records = []
        mode = 'r:gz' if path.name.endswith(('.tar.gz', '.tgz')) else 'r'
        with tarfile.open(path, mode) as tar, tempfile.TemporaryDirectory() as tmpdir:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                member_name = os.path.basename(member.name)
                if not member_name.lower().endswith(('.grib', '.grib2', '.grb', '.grb2')):
                    continue

                # extract just this member, without trusting archive paths
                member.name = member_name
                tar.extract(member, tmpdir)
                member_path = Path(tmpdir) / member_name

                forecast_created = created_at
                forecast_target = None
                match = GFS_FILENAME_RE.search(member_name)
                if match:
                    cycle_str, fhour_str = match.groups()
                    try:
                        forecast_created = datetime.strptime(
                            cycle_str, '%Y%m%d%H').replace(tzinfo=timezone.utc)
                        forecast_target = forecast_created + timedelta(hours=int(fhour_str))
                    except ValueError:
                        forecast_created = created_at
                        forecast_target = None

                try:
                    member_records = self._parse_grib(
                        member_path, region, variable, forecast_created)
                except Exception:
                    logger.exception("Error parsing %s from %s", member_name, path)
                    continue
                finally:
                    member_path.unlink(missing_ok=True)
                    # cfgrib writes .idx sidecar files next to the GRIB
                    for idx in Path(tmpdir).glob(f"{member_name}*.idx"):
                        idx.unlink(missing_ok=True)

                if forecast_target is not None:
                    for rec in member_records:
                        rec['forecast_target'] = forecast_target
                records.extend(member_records)
        return records

    def _parse_grib(self, path, region, variable, created_at):
        import xarray as xr
        ds = xr.open_dataset(str(path), engine='cfgrib')
        return self._xarray_to_records(ds, region, variable, created_at)

    def _parse_netcdf(self, path, region, variable, created_at):
        import xarray as xr
        ds = xr.open_dataset(str(path))
        return self._xarray_to_records(ds, region, variable, created_at)

    def _xarray_to_records(self, ds, region, variable, created_at):
        """Convert an xarray Dataset to a list of forecast records."""
        import pandas as pd

        records = []
        data_vars = list(ds.data_vars)
        if not data_vars:
            return records

        var_name = data_vars[0]
        da = ds[var_name]

        if 'time' in da.dims:
            for t_idx in range(da.sizes['time']):
                ts_val = da.coords['time'].values[t_idx]
                target = pd.Timestamp(ts_val).to_pydatetime()
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                val = float(da.isel(time=t_idx).mean().values)
                records.append({
                    'region': region,
                    'variable': variable,
                    'forecast_created': created_at,
                    'forecast_target': target,
                    'value': val,
                })
        else:
            val = float(da.mean().values)
            records.append({
                'region': region,
                'variable': variable,
                'forecast_created': created_at,
                'forecast_target': created_at,
                'value': val,
            })
        return records

    def _parse_csv(self, path, region, variable, created_at):
        import csv
        records = []
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row.get('time') or row.get('timestamp') or row.get('date')
                val_str = row.get('value') or row.get(variable)
                if not ts_str:
                    continue
                try:
                    target = datetime.fromisoformat(ts_str)
                    if target.tzinfo is None:
                        target = target.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                try:
                    val = float(val_str) if val_str else None
                except (ValueError, TypeError):
                    val = None
                records.append({
                    'region': region,
                    'variable': variable,
                    'forecast_created': created_at,
                    'forecast_target': target,
                    'value': val,
                })
        return records

    def _load_manifest(self, path):
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_manifest(self, path, data):
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            logger.exception("Failed to save manifest at %s", path)
