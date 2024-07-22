#!/bin/bash

# Change the below to the CarbonCast diretory
CARBON_CAST_DIR=/Users/jc/Downloads/CarbonCast_3.0/

# Change the below to the directory you want to move
# Default is `EU_DATA`
DATA=EU_DATA

# No need to change the below
DIR_SRC=$CARBON_CAST_DIR/$DATA
DIR_DST=$CARBON_CAST_DIR/real_time

pushd $DIR_SRC
for x in `ls -d */`; do
	pushd $x
	cp -a daily $DIR_DST/
	mv $DIR_DST/daily $DIR_DST/$x
	popd
done
popd
