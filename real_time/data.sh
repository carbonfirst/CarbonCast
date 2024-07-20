#!/bin/bash

# Change the below to the CarbonCast diretory
CARBON_CAST_DIR=.

# No need to change the below
DIR_SRC=$CARBON_CAST_DIR/EU_DATA
DIR_DST=$CARBON_CAST_DIR/real_time

pushd $DIR_SRC
for x in `ls -d */`; do
	pushd $x
	cp -a daily $DIR_DST/
	mv $DIR_DST/daily $DIR_DST/$x
	popd
done
popd
