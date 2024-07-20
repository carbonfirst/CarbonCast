#!/bin/bash

DIR_SRC=/Users/asouza/tmp2/CarbonCast/EU_DATA
DIR_DST=/Users/asouza/tmp2/CarbonCast/real_time

pushd $DIR_SRC
for x in `ls -d */`; do
	pushd $x
	cp -a daily $DIR_DST/
	mv $DIR_DST/daily $DIR_DST/$x
	popd
done
popd
