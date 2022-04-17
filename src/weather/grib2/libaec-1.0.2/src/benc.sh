#!/bin/sh
set -e
TEST_DATA=$1
AEC=./aec
if [ ! -f  bench.dat ]; then
    rm -f typical.dat
    $AEC -d -n16 -j64 -r256 -m $TEST_DATA typical.dat
    for i in $(seq 0 499);
    do
        cat typical.dat >> bench.dat
    done
    rm -f typical.dat
fi
rm -f bench.rz
utime=$(./utime $AEC -n16 -j64 -r256 -m bench.dat bench.rz 2>&1)
echo $utime
bsize=$(wc -c bench.dat | awk '{print $1}')
perf=$(awk "BEGIN {print ${bsize}/1048576/${utime}}")
echo "[0;32m*** Encoding with $perf MiB/s user time ***[0m"
