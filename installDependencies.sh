#!/bin/bash

sudo apt install -y wget python3-pip make cmake gcc gfortran

echo "Installing required python modules..."
pip3 install -U -r requirements.txt

echo "Installing packages to fetch & parse weather forecast data..."
wget https://ftp.cpc.ncep.noaa.gov/wd51we/wgrib2/wgrib2.tgz
tar -xzvf wgrib2.tgz
cd grib2
export CC=gcc
export FC=gfortran
export COMP_SYS=gnu_linux
make
make lib
echo "export PATH=\$PATH:$(pwd)/grib2/wgrib2" >> ~/.bashrc

cd ..
