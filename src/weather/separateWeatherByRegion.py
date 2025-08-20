'''
This file uses the code from https://towardsdatascience.com/the-correct-way-to-average-the-globe-92ceecd172b7 
for the below two functions:
    earth_radius()
    area_grid()
These functions aggregate the weather data over a specified bounding box.

This file takes in weathre data for a whole continent, aggregates the weather data 
and separates it by the regions specified.

PLEASE MODIFY THE "FILE_DIR", "OUT_FILE_DIR" AND "YEARS", VARIABLES WITH THE CORRECT PATH FOR THIS TO WORK.
'''

import subprocess
from collections import namedtuple
from calendar import monthrange
import os.path
import pandas as pd
import csv
import math
import numpy as np
# import weather_util as wutil
import threading
import sys
import os
import argparse
from typing import Optional

FILE_DIR = ["../../src/weather/EU_2023/ugrd_vgrd/",
            "../../src/weather/EU_2023/tmp_dpt/",
            "../../src/weather/EU_2023/dswrf/",
            "../../src/weather/EU_2023/apcp/"] # Modify this as required
OUT_FILE_DIR = "./EU_2023/" # Modify this as required
YEARS = [2023] # Modify this as required. If YEARS is current year (2023), modify line 254 also.

FILE_PREFIX = "gfs.0p25."
HOUR = ["00"] ##, "06", "12", "18"]
FCST = ["000"] + [f"{i:03d}" for i in range(3, 169, 3)]
FCST_RT = [f"{i:03d}" for i in range(3, 169, 3)]
FCST_AVG_ACC = [f"{i:03d}" for i in range(3, 169, 3)]
HEADER = ["startDate", "endDate", "param", "level", "longitude", "latitude", "value"]

# Non-RT headers (include an "Analysis" column for 000h, then 3..168hr labels)
CSV_FILE_FIELDS_FCST = [
    "datetime", "param", "level", "latitude", "longitude", "Analysis",
] + [f"{i} hr fcst" for i in range(3, 169, 3)]

# Build 3-hourly window labels up to 168h: 0-3, 0-6, 6-9, 6-12, ... , 165-168
def _build_three_hour_window_labels(suffix: str):
    labels = []
    step_hours = list(range(0, 168, 3))  # 0,3,6,...,165
    for idx, h in enumerate(step_hours):
        if idx % 2 == 0:
            labels.append(f"{h}-{h+3} hr {suffix}")
        else:
            labels.append(f"{h-3}-{h+3} hr {suffix}")
    return labels

CSV_FILE_FIELDS_AVG = ["datetime", "param", "level", "latitude", "longitude"] + _build_three_hour_window_labels("avg")
CSV_FILE_FIELDS_ACC = ["datetime", "param", "level", "latitude", "longitude"] + _build_three_hour_window_labels("acc")

# RT headers (no Analysis column)
CSV_FILE_FIELDS_FCST_RT = ["datetime", "param", "level", "latitude", "longitude"]
CSV_FILE_FIELDS_FCST_RT.extend([str(i) + " hr fcst" for i in range(3, 169, 3)])
CSV_FILE_FIELDS_AVG_RT = ["datetime", "param", "level", "latitude", "longitude"]
CSV_FILE_FIELDS_AVG_RT.extend([str(i) + " hr avg" for i in range(3, 169, 3)])
CSV_FILE_FIELDS_ACC_RT = ["datetime", "param", "level", "latitude", "longitude"]
CSV_FILE_FIELDS_ACC_RT.extend([str(i) + " hr acc" for i in range(3, 169, 3)])

GRIB2_CMD = "wgrib2"

ISO_WITH_INCONSISTENT_DATA = {
    # "FMPP": (-83.00, 24.00, -79.50, 30.75),
    # "TAL":  (-84.75, 29.75, -83.50, 31.25),
    # "TEC":  (-83.25, 27.00, -81.25, 29.00),
    # "LGEE": (-89.75, 36.00, -82.25, 39.50),
    # "DOPD": (-120.75, 46.75, -118.25, 49.50),
    # "PGE":  (-124.25, 44.25, -121.25, 46.50),
    # "PNM":  (-123.50, 30.75, -101.50, 44.50),
    # "TEPC": (-115.25, 31.25, -110.00, 36.75),
}

ISO_BOUNDING_BOX = {
# US regions
    "CISO": (-124.75, 32, -113.5, 42), # wlon, slat, elon, nlat
    "PJM": (-91, 34.25, -73.5, 43),
    "ERCO": (-104.5, 25.25, -93.25, 36.5),
    "ISNE": (-74.25, 40, -66.5, 48),
    "BPAT": (-125.25, 39.50, -105.5, 49.5),
    "FPL": (-83.5, 24, -79.5, 31.25),
    "NYIS": (-80.25, 40, -71.25, 45.5),
    "MISO": (-107.75, 28.50, -81.75, 50.00),
    "SWPP": (-107.75, 30.25, -89.50, 49.50),
    "SOCO": (-90.50, 29.25, -80.25, 35.50),
    "BANC": (-124.00, 37.00, -120.00, 41.75),
    "LDWP": (-119.00, 33.25, -117.00, 38.00),
    "TIDC": (-121.75, 36.75, -119.75, 38.25),
    "DUK":  (-84.75, 33.00, -77.75, 37.00),
    "SC":   (-82.75, 31.50, -78.00, 35.25),
    "SCEG": (-83.00, 31.50, -78.75, 35.25),
    "SPA":  (-98.00, 34.25, -89.00, 40.75),    
    "FPC":  (-86.50, 25.75, -80.00, 31.25),    
    "AECI": (-98.50, 34.25, -88.50, 41.75),    
    "GCPD": (-120.50, 46.25, -118.50, 48.50),
    "GRID": (-119.75, 44.75, -118.25, 46.25),
    "IPCO": (-120.50, 41.50, -111.00, 47.25),
    "NEVP": (-122.00, 34.50, -111.00, 42.50),
    "NWMT": (-116.50, 43.25, -103.50, 49.50),
    "PACE": (-115.75, 33.00, -104.25, 45.50),
    "PACW": (-124.75, 38.75, -115.75, 47.50),    
    "PSCO": (-109.50, 35.75, -102.00, 41.75),
    "PSEI": (-123.75, 45.75, -119.75, 49.50),
    "SCL":  (-123.00, 47.00, -121.75, 48.25),
    "TPWR": (-124.00, 45.75, -120.50, 48.25),
    "WACM": (-114.50, 35.50, -95.75, 48.00),
    "AZPS": (-115.25, 30.75, -108.75, 36.75),
    "EPE":  (-108.75, 26.75, -98.25, 34.00),    
    "SRP":  (-113.75, 32.00, -110.50, 34.50),    
    "WALC": (-124.25, 30.75, -105.00, 44.00),
    "TVA":  (-90.75, 31.75, -81.25, 38.00),

# EU regions

    "AL": (19.25, 39.50, 21.00, 42.75), # wlon, slat, elon, nlat
    "AT": (9.50, 46.50, 17.00 , 49.00),
    "BE": (2.50, 49.50, 6.25 , 51.50),
    "BG": (22.25, 41.25, 28.50, 44.25),
    "HR": (13.75, 42.50, 19.50, 46.50),
    "CZ": (12.25, 48.50, 18.75, 51.00),
    "DK": (7.50, 54.50, 13.25, 57.75),
    # Denmark zone 2: DK-DK2:  7.25, 54.75, 11.25, 57.75}
    "EE": (23.25, 57.50, 28.25, 59.50),
    "FI": (20.50, 59.75, 31.50, 70.00),
    "FR": (-5.25, 42.25, 8.25, 51.25),
    "DE": (5.75, 47.25, 15.00, 55.25),
    "GB": (-8.25, 49.75, 2.25, 61.00),
    "GR": (20.25, 35.00, 26.50, 41.75),
    "HU": (16.25, 45.75, 22.75, 48.50),
    "IE": (-10.00, 51.75, -6.00, 55.25),
    "IT": (6.75, 36.50, 18.50, 47.00),
    "LV": (21.00, 55.50, 28.25, 58.00),
    "LT": ( 21.00, 54.00, 26.50, 56.25),
    "NL": ( 3.25, 50.75, 7.00, 53.50),
    "PL": ( 14.00, 49.00, 24.00, 54.75),
    "PT": ( -10.00, 36.50, -5.75, 42.75),
    "RO": ( 20.25, 43.75, 29.50, 48.25),
    "RS": ( 18.75, 42.25, 23.00, 46.25),
    "SK": ( 16.75, 47.75, 22.50, 49.50),
    "SI": ( 13.75 , 45.50, 16.50 , 46.75),
    "ES": ( -9.25, 36.00, 3.50, 43.75),
    "SE": (11.25, 55.25, 21.25, 69.00),
    "CH": (6.00, 45.75, 10.50, 47.75)
}

US_REGION_LIST = ["AECI", "AZPS", "BPAT", "CISO", "DUK", "EPE", "ERCO", "FPL", 
                "ISNE", "LDWP", "MISO", "NEVP", "NWMT", "NYIS", "PACE", "PJM", 
                "SC", "SCEG", "SOCO", "TIDC", "TVA"] # add US regions here
EU_REGION_LIST = ["AL", "AT", "BE", "BG", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", 
                  "GB", "GR", "HU", "IE", "IT", "LV", "LT", "NL", "PL", "PT", "RO", 
                  "RS", "SK", "SI", "ES", "SE", "CH"] # add EU regions here

US_VAR_SEPARATOR =  24780 # 24308 --> for 2022 as different data boundaries, 24780 is for 2019-2021
EU_VAR_SEPARATOR =  23547

import numpy as np

_printed_first_sample: bool = False
def _debug_print_first_sample(csv_path: str):
    global _printed_first_sample
    if _printed_first_sample:
        return
    try:
        df = pd.read_csv(csv_path, names=HEADER)
        print("Sample params in", os.path.basename(csv_path), ":", df["param"].head(5).tolist())
        print("Sample levels:", df["level"].head(5).tolist())
    except Exception as e:
        print("Sample read failed for", csv_path, e)
    _printed_first_sample = True

def _list_dir_grib2_files(fileDir: str):
    """Return a sorted list of full paths to GRIB2 files in a directory.
    This is used when a concrete directory of files is provided (like combined/<REGION>/<VAR>/)
    to avoid calendar-based iteration and "prev file" fallback loops.
    """
    try:
        if not os.path.isdir(fileDir):
            return None
        entries = [f for f in os.listdir(fileDir) if f.endswith('.grib2') and f.startswith(FILE_PREFIX)]
        if not entries:
            # Fallback to any .grib2 if prefix isn't used
            entries = [f for f in os.listdir(fileDir) if f.endswith('.grib2')]
        entries.sort()  # lexicographic sort groups by date/hour then fcst
        return [os.path.join(fileDir, f) for f in entries]
    except Exception as e:
        print(f"Warning: failed to list files in {fileDir}: {e}")
        return None

def earth_radius(lat):
    '''
    calculate radius of Earth assuming oblate spheroid
    defined by WGS84
    
    Input
    ---------
    lat: vector or latitudes in degrees  
    
    Output
    ----------
    r: vector of radius in meters
    
    Notes
    -----------
    WGS84: https://earth-info.nga.mil/GandG/publications/tr8350.2/tr8350.2-a/Chapter%203.pdf
    '''
    from numpy import deg2rad, sin, cos

    # define oblate spheroid from WGS84
    a = 6378137
    b = 6356752.3142
    e2 = 1 - (b**2/a**2)
    
    # convert from geodecic to geocentric
    # see equation 3-110 in WGS84
    lat = deg2rad(lat)
    lat_gc = np.arctan( (1-e2)*np.tan(lat) )

    # radius equation
    # see equation 3-107 in WGS84
    r = (
        (a * (1 - e2)**0.5) 
         / (1 - (e2 * np.cos(lat_gc)**2))**0.5 
        )

    # print("Earth radius:", r ,len(r))
    return r

def area_grid(lat, lon):
    """
    Calculate the area of each grid cell
    Area is in square meters
    
    Input
    -----------
    lat: vector of latitude in degrees
    lon: vector of longitude in degrees
    
    Output
    -----------
    area: grid-cell area in square-meters with dimensions, [lat,lon]
    
    Notes
    -----------
    Based on the function in
    https://github.com/chadagreene/CDT/blob/master/cdt/cdtarea.m
    """
    from numpy import meshgrid, deg2rad, gradient, cos
    # from xarray import DataArray  # unused

    xlon, ylat = meshgrid(lon, lat)
    # print(ylat)
    R = earth_radius(ylat)

    dlat = deg2rad(gradient(ylat, axis=0))
    dlon = deg2rad(gradient(xlon, axis=1))

    dy = dlat * R
    dx = dlon * R * cos(deg2rad(ylat))

    area = dy * dx
    # print("Area shape: ", area.shape, type(area))
    return area

def getFileList(yearList = [2022], fileDir = None, fcstCol = FCST):
    # Prefer directory scan mode when a concrete folder of GRIB2s is provided
    dir_files = _list_dir_grib2_files(fileDir)
    if dir_files is not None:
        return dir_files
    fileList = []
    prevFile = None
    for year in yearList:
        for month in range(1, 13): # Month is always 1..12 # [DM] change this from 13 to (current month no. + 1) if 2023.
            for day in range(1, monthrange(year, month)[1] + 1):
                curDate = str(year)+f"{month:02d}"+f"{day:02d}"
                fileName = FILE_PREFIX + str(curDate)
                oldFileName = fileName
                for hr in HOUR:
                    for fcst in fcstCol:
                        fileName = oldFileName
                        fileName +=str(hr) + ".f"+str(fcst)+".grib2"
                        filePath = ""
                        filePath = fileDir + fileName
                        if (os.path.exists(filePath) == False):
                            # In calendar mode, skip missing files without falling back indefinitely
                            # to the previous file (prevents endless repeats at dataset tail).
                            # print(filePath + " doesn't exist")
                            pass
                        else:
                            fileList.append(filePath)
                            prevFile = fileName # assuming the first file to be searched is always present
    return fileList

def getFileListForDate(startDate = None, fileDir = None, fcstCol = FCST):
    fileList = []
    prevFile = None
    year = startDate[0:4]
    month = startDate[5:7]
    day = startDate[8:10]
    curDate = str(year) + str(month) + str(day)
    fileName = "gfs.t00z.pgrb2.0p25." + str(curDate)
    oldFileName = fileName
    # for fcst in range(1, 168): # uncomment this line & comment below line for hourly weather forecasts
    for fcst in range(3, 169, 3):
        fileName = oldFileName

        if fcst < 10:
            fcst = "0" + str(fcst)
        else:
            fcst = str(fcst)
        fileName += f".f00{fcst}.grib2"
        filePath = ""
        filePath = f"{fileDir}/{fileName}"
        if (os.path.exists(filePath) == False):
            print(filePath + " doesn't exist")
            filePath = fileDir + str(prevFile)
            if (os.path.exists(filePath) == True):
                fileList.append(filePath)
                print("Using previous forecast value with file: ", prevFile)
            else:
                print(filePath + " doesn't exist also")
        else:
            fileList.append(filePath)
            prevFile = fileName # assuming the first file to be searched is always present
    return fileList

def fetchWeatherDataByRegion(weatherVariable, fcstCol, pid, isRealTime, startDate, varSeparator,
                             stream: bool = False, stream_out: str | None = None,
                             stream_fields: list | None = None, stream_file_name=None):
    if (isRealTime is False):
        fileList = getFileList(YEARS, weatherVariable, fcstCol)
    else:
        if(startDate is not None):
            fileList = getFileListForDate(startDate, weatherVariable, fcstCol)
        else:
            print("Error! No date specified")
            exit(0)
    fileIdx = 0
    rows = {}
    tmprows = {}
    dptrows = {}
    
    # Track header written per region for streaming mode
    header_written = set()

    while fileIdx < len(fileList):
        lat = None
        lon = None
        latitude = {}
        longitude = {}
        grid_cell_area = {}
        total_area_of_earth = {}
        windrow = {}
        tmprow = {}
        dptrow = {}
        weatherVarRow = {}
        for i in range(len(fcstCol)):
            if fileIdx >= len(fileList):
                break  # guard against partial final block
            row = {}
            urow = {}
            vrow = {}
            tmpCsvFile = "tmp"+str(pid)+weatherVariable.split("/")[-2]+str(YEARS[0])+".csv"
            if (isRealTime is True):
                tmpCsvFile = "tmp"+str(pid)+weatherVariable.split("/")[-2]+str(startDate)+".csv"
            current_file = fileList[fileIdx]
            val = subprocess.call(GRIB2_CMD + " " + current_file + " -csv "+tmpCsvFile, shell=True)
            print("File:", current_file)
            fileIdx+=1
            if(val == 0):
                dataset = pd.read_csv(tmpCsvFile, infer_datetime_format=True, 
                        names=HEADER) #, header=0,  parse_dates=['UTC time'], index_col=['UTC time'])    
                # print(dataset.head(2))
                _debug_print_first_sample(tmpCsvFile)
                if ("ugrd_vgrd" in weatherVariable or "tmp_dpt" in weatherVariable):
                    # Robust split: use 'param' labels instead of a fixed row separator
                    if ("ugrd_vgrd" in weatherVariable):
                        udataset = dataset[
                            dataset["param"].astype(str).str.startswith("UGRD")
                            & dataset["level"].astype(str).str.contains("10 m")
                        ]
                        vdataset = dataset[
                            dataset["param"].astype(str).str.startswith("VGRD")
                            & dataset["level"].astype(str).str.contains("10 m")
                        ]
                    else:  # tmp_dpt
                        udataset = dataset[
                            dataset["param"].astype(str).str.startswith("TMP")
                            & dataset["level"].astype(str).str.contains("2 m")
                        ]
                        vdataset = dataset[
                            dataset["param"].astype(str).str.startswith("DPT")
                            & dataset["level"].astype(str).str.contains("2 m")
                        ]
                    # print(udataset.tail(2))
                    # print(vdataset.head(2))
                    for line in range(len(udataset)):
                        lon = float(udataset["longitude"].values[line])
                        # Normalize longitudes to -180..180 if needed
                        if lon > 180:
                            lon -= 360.0
                        lat = float(udataset["latitude"].values[line])
                        for region, val in ISO_BOUNDING_BOX.items():
                            (wlon, slat, elon, nlat) = val
                            if (lon >=wlon and lon <=elon and lat>=slat and lat <=nlat):
                                if (region not in urow.keys()):
                                    urow[region] = [[udataset["startDate"].iloc[line], udataset["endDate"].iloc[line], 
                                                     udataset["param"].iloc[line], udataset["level"].iloc[line], 
                                                     udataset["longitude"].iloc[line], udataset["latitude"].iloc[line], 
                                                     udataset["value"].iloc[line]]]
                                else:
                                    urow[region].append([udataset["startDate"].iloc[line], udataset["endDate"].iloc[line],
                                                         udataset["param"].iloc[line], udataset["level"].iloc[line], 
                                                         udataset["longitude"].iloc[line], udataset["latitude"].iloc[line], 
                                                         udataset["value"].iloc[line]])
                    for line in range(len(vdataset)):
                        lon = float(vdataset["longitude"].values[line])
                        # Normalize longitudes to -180..180 if needed
                        if lon > 180:
                            lon -= 360.0
                        lat = float(vdataset["latitude"].values[line])
                        for region, val in ISO_BOUNDING_BOX.items():
                            (wlon, slat, elon, nlat) = val
                            if (lon >=wlon and lon <=elon and lat>=slat and lat <=nlat):
                                if (region not in vrow.keys()):
                                    vrow[region] = [[vdataset["startDate"].iloc[line], vdataset["endDate"].iloc[line],
                                                     vdataset["param"].iloc[line], vdataset["level"].iloc[line], 
                                                     vdataset["longitude"].iloc[line], vdataset["latitude"].iloc[line], 
                                                     vdataset["value"].iloc[line]]]
                                else:
                                    vrow[region].append([vdataset["startDate"].iloc[line], vdataset["endDate"].iloc[line], 
                                                         vdataset["param"].iloc[line], vdataset["level"].iloc[line], 
                                                         vdataset["longitude"].iloc[line], vdataset["latitude"].iloc[line], 
                                                         vdataset["value"].iloc[line]])
                    # If either split is empty, log and proceed to NaN seeding below
                    if len(udataset) == 0 or len(vdataset) == 0:
                        print(f"Warning: empty component set for {os.path.basename(current_file)}: U={len(udataset)} V={len(vdataset)}")

                    # now we have region-wise datasets for this timestamp
                    for region in ISO_BOUNDING_BOX.keys():
                        u_entries = urow.get(region, [])
                        v_entries = vrow.get(region, [])

                        if len(u_entries) == 0 or len(v_entries) == 0:
                            # No grid cells for this region in this file; append NaN and lazily init metadata
                            if ("ugrd_vgrd" in weatherVariable):
                                if region not in windrow.keys():
                                    # Seed metadata from any available record in the raw dataset
                                    if len(dataset) > 0:
                                        seed = dataset.iloc[0]
                                        windrow[region] = [seed["startDate"], seed["param"], seed["level"], seed["latitude"], seed["longitude"]]
                                    else:
                                        windrow[region] = ["", "", "", "", ""]
                                windrow[region].append(np.nan)
                            else:
                                # tmp_dpt branch: keep both temp and dewpoint aligned
                                if region not in tmprow.keys():
                                    if len(dataset) > 0:
                                        seed = dataset.iloc[0]
                                        tmprow[region] = [seed["startDate"], seed["param"], seed["level"], seed["latitude"], seed["longitude"]]
                                    else:
                                        tmprow[region] = ["", "", "", "", ""]
                                if region not in dptrow.keys():
                                    if len(dataset) > 0:
                                        seed = dataset.iloc[0]
                                        dptrow[region] = [seed["startDate"], seed["param"], seed["level"], seed["latitude"], seed["longitude"]]
                                    else:
                                        dptrow[region] = ["", "", "", "", ""]
                                tmprow[region].append(np.nan)
                                dptrow[region].append(np.nan)
                            # Skip to next region for this timestamp
                            continue

                        udataset = pd.DataFrame(u_entries, columns=HEADER)
                        vdataset = pd.DataFrame(v_entries, columns=HEADER)
                        if (i==0):
                            latitude[region] = np.unique(udataset["latitude"].values)
                            longitude[region] = np.unique(udataset["longitude"].values)
                            grid_cell_area[region] = area_grid(latitude[region], longitude[region])
                            total_area_of_earth[region] = np.sum(grid_cell_area[region])
                        if region not in windrow.keys():
                            windrow[region] = [udataset["startDate"].iloc[0], udataset["param"].iloc[0], udataset["level"].iloc[0],
                                        udataset["latitude"].iloc[0], udataset["longitude"].iloc[0]]
                        if region not in tmprow.keys():
                            tmprow[region] = [udataset["startDate"].iloc[0], udataset["param"].iloc[0], udataset["level"].iloc[0],
                                        udataset["latitude"].iloc[0], udataset["longitude"].iloc[0]]
                        if region not in dptrow.keys():
                            dptrow[region] = [vdataset["startDate"].iloc[0], vdataset["param"].iloc[0], vdataset["level"].iloc[0],
                                        vdataset["latitude"].iloc[0], vdataset["longitude"].iloc[0]]

                        if ("ugrd_vgrd" in weatherVariable):
                            windSpeed = (udataset["value"].values**2 + vdataset["value"].values**2)**(0.5)
                            value = np.reshape(windSpeed, (len(latitude[region]), len(longitude[region])))
                            weighted_mean = (value * grid_cell_area[region]) / total_area_of_earth[region]
                            weighted_mean = np.sum(weighted_mean)
                            windrow[region].append(weighted_mean)
                        else: # tmp_dpt
                            # temperature
                            value = udataset["value"].values
                            value = np.reshape(value, (len(latitude[region]), len(longitude[region])))
                            weighted_mean = (value * grid_cell_area[region]) / total_area_of_earth[region]
                            weighted_mean = np.sum(weighted_mean)
                            tmprow[region].append(weighted_mean)
                            # dewpoint
                            value = vdataset["value"].values
                            value = np.reshape(value, (len(latitude[region]), len(longitude[region])))
                            weighted_mean = (value * grid_cell_area[region]) / total_area_of_earth[region]
                            weighted_mean = np.sum(weighted_mean)
                            dptrow[region].append(weighted_mean)
                else: # dswrf or apcp
                    if (isRealTime is True and "apcp" in weatherVariable): # TODO: [DM] Check why APCP is downloaded twice
                        dataset = dataset[varSeparator:]
                    for line in range(len(dataset)):
                        lon = float(dataset["longitude"].values[line])
                        # Normalize longitudes to -180..180 if needed
                        if lon > 180:
                            lon -= 360.0
                        lat = float(dataset["latitude"].values[line])
                        for region, val in ISO_BOUNDING_BOX.items():
                            (wlon, slat, elon, nlat) = val
                            if (lon >=wlon and lon <=elon and lat>=slat and lat <=nlat):
                                if (region not in row.keys()):
                                    row[region] = [[dataset["startDate"].iloc[line], dataset["endDate"].iloc[line], 
                                                    dataset["param"].iloc[line], dataset["level"].iloc[line], 
                                                    dataset["longitude"].iloc[line], dataset["latitude"].iloc[line],  
                                                    dataset["value"].iloc[line]]]
                                else:
                                    row[region].append([dataset["startDate"].iloc[line], dataset["endDate"].iloc[line], 
                                                        dataset["param"].iloc[line], dataset["level"].iloc[line], 
                                                        dataset["longitude"].iloc[line], dataset["latitude"].iloc[line], 
                                                        dataset["value"].iloc[line]])
                    # now we have region-wise datasets for this timestamp
                    for region in ISO_BOUNDING_BOX.keys():
                        entries = row.get(region, [])
                        if len(entries) == 0:
                            # Append NaN and lazily init metadata
                            if region not in weatherVarRow.keys():
                                if len(dataset) > 0:
                                    seed = dataset.iloc[0]
                                    weatherVarRow[region] = [seed["startDate"], seed["param"], seed["level"], seed["latitude"], seed["longitude"]]
                                else:
                                    weatherVarRow[region] = ["", "", "", "", ""]
                            weatherVarRow[region].append(np.nan)
                            continue

                        dset = pd.DataFrame(entries, columns=HEADER)
                        if (i==0):
                            latitude[region] = np.unique(dset["latitude"].values)
                            longitude[region] = np.unique(dset["longitude"].values)
                            grid_cell_area[region] = area_grid(latitude[region], longitude[region])
                            total_area_of_earth[region] = np.sum(grid_cell_area[region])
                        if region not in weatherVarRow.keys():
                            weatherVarRow[region] = [dset["startDate"].iloc[0], dset["param"].iloc[0], dset["level"].iloc[0],
                                        dset["latitude"].iloc[0], dset["longitude"].iloc[0]]
                        value = dset["value"].values
                        value = np.reshape(value, (len(latitude[region]), len(longitude[region])))
                        weighted_mean = (value * grid_cell_area[region]) / total_area_of_earth[region]
                        weighted_mean = np.sum(weighted_mean)
                        weatherVarRow[region].append(weighted_mean)
                delFile = subprocess.call("rm "+tmpCsvFile, shell=True)
                if(delFile != 0):
                    print("Error: Process call failed -- rm")
            else:
                print("Error: Process call failed -- ", GRIB2_CMD)
                
        # If we broke early due to partial block at the end, drop this incomplete aggregation
        # by not appending any region rows and exit loop.
        if fileIdx >= len(fileList) and i+1 < len(fcstCol):
            break
        # Build per-region row blocks to optionally stream
        block_rows = {}
        block_tmprows = {}
        block_dptrows = {}
        for region in ISO_BOUNDING_BOX.keys():
            if ("tmp_dpt" in weatherVariable):
                # collect this block
                block_tmprows[region] = [tmprow.get(region)] if region in tmprow else None
                block_dptrows[region] = [dptrow.get(region)] if region in dptrow else None
                # accumulate full result when not streaming
                if region not in tmprows.keys():
                    tmprows[region] = [tmprow.get(region)] if region in tmprow else []
                else:    
                    tmprows[region].append(tmprow.get(region))
                if (region not in dptrows.keys()):
                    dptrows[region] = [dptrow.get(region)] if region in dptrow else []
                else:
                    dptrows[region].append(dptrow.get(region))
            else:
                if ("ugrd_vgrd" in weatherVariable):
                    block_rows[region] = [windrow.get(region)] if region in windrow else None
                    if (region not in rows.keys()):
                        rows[region] = [windrow.get(region)] if region in windrow else []
                    else:
                        rows[region].append(windrow.get(region))
                else:
                    block_rows[region] = [weatherVarRow.get(region)] if region in weatherVarRow else None
                    if (region not in rows.keys()):
                        rows[region] = [weatherVarRow.get(region)] if region in weatherVarRow else []
                    else:
                        rows[region].append(weatherVarRow.get(region))

        # Stream write this block if requested
        if stream and stream_out and stream_fields and stream_file_name:
            if ("tmp_dpt" in weatherVariable):
                temp_file, dpt_file = stream_file_name
                _write_stream_block(stream_out, block_tmprows, stream_fields, temp_file, isRealTime, header_written)
                _write_stream_block(stream_out, block_dptrows, stream_fields, dpt_file, isRealTime, header_written)
            else:
                _write_stream_block(stream_out, block_rows, stream_fields, stream_file_name, isRealTime, header_written)

        # If we consumed a full block, continue; if not, exit while
        if fileIdx >= len(fileList):
            break

    if stream:
        # In streaming mode we already wrote blocks; return empty to avoid large memory
        return ({}, {}) if ("tmp_dpt" in weatherVariable) else ({}, None)
    else:
        if ("tmp_dpt" in weatherVariable):
            return tmprows, dptrows
        return rows, None

def writeWeatherValuesToFile(outFilePath, weatherValues, csvFields, weatherVariableFileName, isRealTime=False):
    for region in ISO_BOUNDING_BOX.keys():
        writeMode = "a"
        regionOutFilePath = ""
        if (isRealTime is True):
            regionOutFilePath = outFilePath + region + "/weather_data/"
            writeMode = "w"
            print(regionOutFilePath+region+"_"+weatherVariableFileName)
        else:
            regionOutFilePath = outFilePath
        # Ensure directory exists when writing files
        try:
            os.makedirs(regionOutFilePath, exist_ok=True)
        except Exception as e:
            print(f"Warning: could not create directory {regionOutFilePath}: {e}")
        with open(regionOutFilePath+region+"_"+weatherVariableFileName, writeMode) as regioncsvfile:
            csvwriter = csv.writer(regioncsvfile)
            csvwriter.writerow(csvFields)
            csvwriter.writerows(weatherValues[region])

def _write_stream_block(outFilePath, blockValues, csvFields, weatherVariableFileName, isRealTime, header_written):
    """Append a single block (one forecast cycle) to per-region CSVs.
    Writes header once per region (tracked in header_written set).
    blockValues is a dict[region] -> list[list[...]] where each inner list is one row.
    """
    for region, rows_list in blockValues.items():
        if rows_list is None:
            continue
        writeMode = "a"
        regionOutFilePath = ""
        if (isRealTime is True):
            regionOutFilePath = outFilePath + region + "/weather_data/"
        else:
            regionOutFilePath = outFilePath
        try:
            os.makedirs(regionOutFilePath, exist_ok=True)
        except Exception as e:
            print(f"Warning: could not create directory {regionOutFilePath}: {e}")
        out_path = regionOutFilePath+region+"_"+weatherVariableFileName
        need_header = False
        if region not in header_written:
            # If file doesn't exist or empty, write header first
            need_header = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
        with open(out_path, writeMode, newline="") as regioncsvfile:
            csvwriter = csv.writer(regioncsvfile)
            if need_header:
                csvwriter.writerow(csvFields)
                header_written.add(region)
            csvwriter.writerows(rows_list)

def startScript(continent, regionList, index, pid, inFilePath, outFilePath, isRealTime, startDate, stream=False):
    global FCST
    global CSV_FILE_FIELDS_FCST
    global CSV_FILE_FIELDS_AVG
    global CSV_FILE_FIELDS_ACC
    global ISO_BOUNDING_BOX

    weatherVariable = ["WIND_SPEED", "TEMP", "DPT", "DSWRF", "APCP"]

    print("Process id = ", pid, "index = ", index)
    # affinity = os.sched_getaffinity(0)
    # print("Process is eligible to run on:", affinity)
    # # affinity_mask = {(index+1)*2, (index+1)*2+1}
    # affinity_mask = {8, 9}
    # os.sched_setaffinity(0, affinity_mask)
    # print("CPU affinity mask is modified for process id % s" % pid)
    # affinity = os.sched_getaffinity(0)
    # print("Now, process is eligible to run on:", affinity) 

    tmpIsoBoundingBox = {}
    for region in regionList:
        tmpIsoBoundingBox[region] = ISO_BOUNDING_BOX[region]
    ISO_BOUNDING_BOX = tmpIsoBoundingBox
    
    if (isRealTime is True):
        CSV_FILE_FIELDS_FCST = CSV_FILE_FIELDS_FCST_RT
        CSV_FILE_FIELDS_AVG = CSV_FILE_FIELDS_AVG_RT
        CSV_FILE_FIELDS_ACC = CSV_FILE_FIELDS_ACC_RT
        FCST = FCST_RT
        if (startDate is not None):
            for i in range(len(weatherVariable)):
                weatherVariable[i] = weatherVariable[i]+"_"+str(startDate)

    varSeparator = US_VAR_SEPARATOR
    if (continent == "EU"):
        varSeparator = EU_VAR_SEPARATOR


    if ("ugrd_vgrd" in inFilePath[index]):
        if stream:
            fetchWeatherDataByRegion(
                inFilePath[index], FCST, pid, isRealTime, startDate, varSeparator,
                stream=True, stream_out=outFilePath, stream_fields=CSV_FILE_FIELDS_FCST,
                stream_file_name=weatherVariable[0]+".csv"
            )
        else:
            windSpeed, nop = fetchWeatherDataByRegion(inFilePath[index], FCST, pid, isRealTime, startDate, varSeparator)
            writeWeatherValuesToFile(outFilePath, windSpeed, CSV_FILE_FIELDS_FCST, weatherVariable[0]+".csv", isRealTime)
    elif ("tmp_dpt" in inFilePath[index]):
        if stream:
            fetchWeatherDataByRegion(
                inFilePath[index], FCST, pid, isRealTime, startDate, varSeparator,
                stream=True, stream_out=outFilePath, stream_fields=CSV_FILE_FIELDS_FCST,
                stream_file_name=(weatherVariable[1]+".csv", weatherVariable[2]+".csv")
            )
        else:
            temperature, dewpoint = fetchWeatherDataByRegion(inFilePath[index], FCST, pid, isRealTime, startDate, varSeparator)
            writeWeatherValuesToFile(outFilePath, temperature, CSV_FILE_FIELDS_FCST, weatherVariable[1]+".csv", isRealTime)
            writeWeatherValuesToFile(outFilePath, dewpoint, CSV_FILE_FIELDS_FCST, weatherVariable[2]+".csv", isRealTime)
    else:
        if stream:
            if ("dswrf" in inFilePath[index]):
                fetchWeatherDataByRegion(
                    inFilePath[index], FCST_AVG_ACC, pid, isRealTime, startDate, varSeparator,
                    stream=True, stream_out=outFilePath, stream_fields=CSV_FILE_FIELDS_AVG,
                    stream_file_name=weatherVariable[3]+".csv"
                )
            else:
                fetchWeatherDataByRegion(
                    inFilePath[index], FCST_AVG_ACC, pid, isRealTime, startDate, varSeparator,
                    stream=True, stream_out=outFilePath, stream_fields=CSV_FILE_FIELDS_ACC,
                    stream_file_name=weatherVariable[4]+".csv"
                )
        else:
            weatherValues, nop = fetchWeatherDataByRegion(inFilePath[index], FCST_AVG_ACC, pid, isRealTime, startDate, varSeparator)
            if ("dswrf" in inFilePath[index]):
                writeWeatherValuesToFile(outFilePath, weatherValues, CSV_FILE_FIELDS_AVG, weatherVariable[3]+".csv", isRealTime)
            else:
                writeWeatherValuesToFile(outFilePath, weatherValues, CSV_FILE_FIELDS_ACC, weatherVariable[4]+".csv", isRealTime)
        
    
    return


if __name__ == "__main__":
    # Backward-compatible CLI with optional overrides
    parser = argparse.ArgumentParser(description="Aggregate GRIB2 weather by region and export CSVs.")
    parser.add_argument("continent", choices=["US", "EU"], help="Continent key")
    parser.add_argument("index", type=int, choices=[0, 1, 2, 3], help="Variable index: 0=wind, 1=tmp/dpt, 2=dswrf, 3=apcp")
    parser.add_argument("--base", dest="base_dir", default=None, help="Base directory containing subfolders ugrd_vgrd, tmp_dpt, dswrf, apcp")
    parser.add_argument("--out", dest="out_dir", default=None, help="Output directory. If --rt is set, files go under <out>/<REGION>/weather_data/")
    parser.add_argument("--years", dest="years", default=None, help="Comma-separated years, e.g. 2021,2022 (batch mode)")
    parser.add_argument("--regions", dest="regions", default=None, help="Comma-separated region codes to process (subset)")

    # Track header written per region for streaming mode
    header_written = set()

    parser.add_argument("--rt", dest="rt_date", default=None, help="Real-time single start date: YYYY-MM-DD or YYYYMMDD")
    parser.add_argument("--stream", dest="stream", action="store_true", help="Append rows to output CSVs as each block completes (enables tail -f monitoring)")

    args = parser.parse_args()

    def _ensure_trailing_sep(p: str) -> str:
        if p is None or p == "":
            return p
        return p if p.endswith(os.sep) else p + os.sep

    def _normalize_date(s: str) -> str:
        s = s.strip()
        if len(s) == 8 and s.isdigit():
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return s
        raise ValueError("Invalid date; use YYYY-MM-DD or YYYYMMDD")

    continent = args.continent
    index = args.index

    # Determine region list
    regionList = US_REGION_LIST
    if continent == "EU":
        regionList = EU_REGION_LIST
        print("EU mode selected (bounding boxes available); note: historical EU batch may need validation.")

    if args.regions:
        req = [r.strip() for r in args.regions.split(",") if r.strip()]
        # Validate provided regions
        unknown = [r for r in req if r not in regionList]
        if unknown:
            print(f"Error: unknown region codes for {continent}: {unknown}")
            sys.exit(1)
        regionList = req

    # Build input variable directories
    inFilePath = FILE_DIR
    if args.base_dir:
        base = _ensure_trailing_sep(args.base_dir)
        inFilePath = [
            os.path.join(base, "ugrd_vgrd") + os.sep,
            os.path.join(base, "tmp_dpt") + os.sep,
            os.path.join(base, "dswrf") + os.sep,
            os.path.join(base, "apcp") + os.sep,
        ]

    # Output directory
    outFilePath = OUT_FILE_DIR
    if args.out_dir:
        outFilePath = _ensure_trailing_sep(args.out_dir)

    # Years for batch mode
    if args.years:
        try:
            globals()["YEARS"] = [int(y.strip()) for y in args.years.split(",") if y.strip()]
        except Exception as e:
            print(f"Error parsing --years: {e}")
            sys.exit(1)

    # Real-time optional single start date
    isRealTime = False
    startDate = None
    if args.rt_date:
        try:
            startDate = _normalize_date(args.rt_date)
            isRealTime = True
        except Exception as e:
            print(f"Error parsing --rt: {e}")
            sys.exit(1)

    # index: 0 = wind, 1 = tmp/dpt, 2 = dswrf, 3 = apcp
    startScript(continent, regionList, index, os.getpid(), inFilePath, outFilePath, isRealTime=isRealTime, startDate=startDate, stream=args.stream)