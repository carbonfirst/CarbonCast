#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${1:-/Users/tanushsavadi/Documents/Research/UCSC_CarbonCast/CarbonCast/168h_grib2_data}"
OUT_DIR="$BASE_DIR/combined"
VARS=(ugrd_vgrd tmp_dpt dswrf apcp)

mkdir -p "$OUT_DIR"

# Derive region codes from folder names like REGION_VAR_YYYY...
# Only consider directories with at least two underscores to avoid 'combined'
REGIONS=$(find "$BASE_DIR" -maxdepth 1 -mindepth 1 -type d -name '*_*_*' -print0 \
  | xargs -0 -n1 basename | sed -E 's/_.*//' | sort -u)

for REGION in $REGIONS; do
  for VAR in "${VARS[@]}"; do
    # Check if there is at least one matching source directory
    any=0
    for SRC in "$BASE_DIR"/${REGION}_${VAR}_*; do
      [ -d "$SRC" ] || continue
      any=1
      break
    done
    [ "$any" -eq 1 ] || continue

    TARGET_DIR="$OUT_DIR/$REGION/$VAR"
    mkdir -p "$TARGET_DIR"
    # Symlink all .grib2 files from each source directory
    for SRC in "$BASE_DIR"/${REGION}_${VAR}_*; do
      [ -d "$SRC" ] || continue
      find "$SRC" -type f -name '*.grib2' -exec ln -sf {} "$TARGET_DIR/" \;
    done
  COUNT=$(find "$TARGET_DIR" \( -type f -o -type l \) -name '*.grib2' | wc -l | tr -d ' ')
    echo "$REGION/$VAR -> $COUNT files"
  done
done

echo "Combined directories created under: $OUT_DIR"
