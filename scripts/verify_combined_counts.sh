#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${1:-/Users/tanushsavadi/Documents/Research/UCSC_CarbonCast/CarbonCast/168h_grib2_data}"
VARS=(ugrd_vgrd tmp_dpt dswrf apcp)

if [ ! -d "$BASE_DIR" ]; then
  echo "Base directory not found: $BASE_DIR" >&2
  exit 2
fi

REGIONS=$(find "$BASE_DIR" -maxdepth 1 -mindepth 1 -type d -name '*_*_*' -print0 \
  | xargs -0 -n1 basename | sed -E 's/_.*//' | sort -u)

TOTAL_SRC=0; TOTAL_COMB=0; MISMATCH=0

for R in $REGIONS; do
  for V in "${VARS[@]}"; do
    SRC_COUNT=0
    for D in "$BASE_DIR"/${R}_${V}_*; do
      [ -d "$D" ] || continue
      C=$(find "$D" -type f -name '*.grib2' | wc -l | tr -d ' ')
      SRC_COUNT=$((SRC_COUNT + C))
    done
    COMB_DIR="$BASE_DIR/combined/$R/$V"
    COMB_COUNT=0
    if [ -d "$COMB_DIR" ]; then
      COMB_COUNT=$(find "$COMB_DIR" \( -type f -o -type l \) -name '*.grib2' | wc -l | tr -d ' ')
    fi
    if [ "$SRC_COUNT" -ne 0 ] || [ "$COMB_COUNT" -ne 0 ]; then
      printf "%s/%s: src=%d combined=%d\n" "$R" "$V" "$SRC_COUNT" "$COMB_COUNT"
    fi
    TOTAL_SRC=$((TOTAL_SRC + SRC_COUNT))
    TOTAL_COMB=$((TOTAL_COMB + COMB_COUNT))
    if [ "$SRC_COUNT" -ne "$COMB_COUNT" ]; then
      MISMATCH=$((MISMATCH + 1))
    fi
  done
done

echo "SUMMARY: total_src=$TOTAL_SRC total_combined=$TOTAL_COMB mismatches=$MISMATCH"
