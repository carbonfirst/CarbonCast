#!/bin/sh
# This shell script runs extra tests ncdump for netcdf-4
# $Id: tst_netcdf4_4.sh,v 1.1 2008/04/14 15:47:53 russ Exp $

set -e
echo ""
echo "*** Running extra tests."

echo "*** dumping tst_string_data.nc to tst_string_data.cdl..."
./ncdump tst_string_data.nc > tst_string_data.cdl
echo "*** comparing tst_string_data.cdl with ref_tst_string_data.cdl..."
diff tst_string_data.cdl $srcdir/ref_tst_string_data.cdl

echo
echo "*** All ncgen and ncdump extra test output for netCDF-4 format passed!"
exit 0
