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

FILE_DIR = ["../../src/weather/EU_2023/ugrd_vgrd/",
            "../../src/weather/EU_2023/tmp_dpt/",
            "../../src/weather/EU_2023/dswrf/",
            "../../src/weather/EU_2023/apcp/"] # Modify this as required
OUT_FILE_DIR = "./EU_2023/" # Modify this as required
YEARS = [2023] # Modify this as required. If YEARS is current year (2023), modify line 254 also.

FILE_PREFIX = "gfs.0p25."
HOUR = ["00"] ##, "06", "12", "18"]
FCST = ["000", "003", "006", "009", "012", "015", "018", "021", "024",
                "027", "030", "033", "036", "039", "042", "045", "048",
                "051", "054", "057", "060", "063", "066", "069", "072",
                "075", "078", "081", "084", "087", "090", "093", "096"]
FCST_RT = ["003", "006", "009", "012", "015", "018", "021", "024",
                "027", "030", "033", "036", "039", "042", "045", "048",
                "051", "054", "057", "060", "063", "066", "069", "072",
                "075", "078", "081", "084", "087", "090", "093", "096"]
FCST_AVG_ACC = ["003", "006", "009", "012", "015", "018", "021", "024",
                "027", "030", "033", "036", "039", "042", "045", "048",
                "051", "054", "057", "060", "063", "066", "069", "072",
                "075", "078", "081", "084", "087", "090", "093", "096"]
HEADER = ["startDate", "endDate", "param", "level", "longitude", "latitude", "value"]
CSV_FILE_FIELDS_FCST = ["datetime", "param", "level", "latitude", "longitude", "Analysis", "3 hr fcst", 
        "6 hr fcst", "9 hr fcst", "12 hr fcst", "15 hr fcst", "18 hr fcst",
        "21 hr fcst", "24 hr fcst", "27 hr fcst", "30 hr fcst", "33 hr fcst",
        "36 hr fcst", "39 hr fcst", "42 hr fcst", "45 hr fcst", "48 hr fcst",
        "51 hr fcst", "54 hr fcst", "57 hr fcst", "60 hr fcst", "63 hr fcst",
        "66 hr fcst", "69 hr fcst", "72 hr fcst", "75 hr fcst", "78 hr fcst",
        "81 hr fcst", "84 hr fcst", "87 hr fcst", "90 hr fcst", "93 hr fcst", "96 hr fcst"]
CSV_FILE_FIELDS_AVG = ["datetime", "param", "level", "latitude", "longitude", "0-3 hr avg", 
        "0-6 hr avg", "6-9 hr avg", "6-12 hr avg", "12-15 hr avg", "12-18 hr avg",
        "18-21 hr avg", "18-24 hr avg", "24-27 hr avg", "24-30 hr avg", "30-33 hr avg",
        "30-36 hr avg", "36-39 hr avg", "36-42 hr avg", "42-45 hr avg", "42-48 hr avg",
        "48-51 hr avg", "48-54 hr avg", "54-57 hr avg", "54-60 hr avg", "60-63 hr avg",
        "60-66 hr avg", "66-69 hr avg", "66-72 hr avg", "72-75 hr avg", "72-78 hr avg",
        "78-81 hr avg", "78-84 hr avg", "84-87 hr avg", "84-90 hr avg", "90-93 hr avg", "90-96 hr avg"] 
CSV_FILE_FIELDS_ACC = ["datetime", "param", "level", "latitude", "longitude", "0-3 hr acc", 
        "0-6 hr acc", "6-9 hr acc", "6-12 hr acc", "12-15 hr acc", "12-18 hr acc",
        "18-21 hr acc", "18-24 hr acc", "24-27 hr acc", "24-30 hr acc", "30-33 hr acc",
        "30-36 hr acc", "36-39 hr acc", "36-42 hr acc", "42-45 hr acc", "42-48 hr acc",
        "48-51 hr acc", "48-54 hr acc", "54-57 hr acc", "54-60 hr acc", "60-63 hr acc",
        "60-66 hr acc", "66-69 hr acc", "66-72 hr acc", "72-75 hr acc", "72-78 hr acc",
        "78-81 hr acc", "78-84 hr acc", "84-87 hr acc", "84-90 hr acc", "90-93 hr acc", "90-96 hr acc"]

CSV_FILE_FIELDS_FCST_RT = ["datetime", "param", "level", "latitude", "longitude"]
CSV_FILE_FIELDS_FCST_RT.extend([str(i) + " hr fcst" for i in range(3, 97, 3)]) # change range to (1, 97) for hourly weather forecasts
CSV_FILE_FIELDS_AVG_RT = ["datetime", "param", "level", "latitude", "longitude"]
CSV_FILE_FIELDS_AVG_RT.extend([str(i) + " hr avg" for i in range(3, 97, 3)]) # change range to (1, 97) for hourly weather forecasts
CSV_FILE_FIELDS_ACC_RT = ["datetime", "param", "level", "latitude", "longitude"]
CSV_FILE_FIELDS_ACC_RT.extend([str(i) + " hr acc" for i in range(3, 97, 3)]) # change range to (1, 97) for hourly weather forecasts

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
    from xarray import DataArray

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
                            print(filePath + " doesn't exist")
                            filePath = fileDir + str(prevFile)
                            if (os.path.exists(filePath) == True):
                                fileList.append(filePath)
                                print("Using previous forecast value with file: ", prevFile)
                            else:
                                print(filePath + " doesn't exist also")
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
    # for fcst in range(1, 96): # uncomment this line & comment below line for hourly weather forecasts
    for fcst in range(3, 97, 3):
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

def fetchWeatherDataByRegion(weatherVariable, fcstCol, pid, isRealTime, startDate, varSeparator):
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
            row = {}
            urow = {}
            vrow = {}
            tmpCsvFile = "tmp"+str(pid)+weatherVariable.split("/")[-2]+str(YEARS[0])+".csv"
            if (isRealTime is True):
                tmpCsvFile = "tmp"+str(pid)+weatherVariable.split("/")[-2]+str(startDate)+".csv"
            val = subprocess.call(GRIB2_CMD + " " + fileList[fileIdx] + " -csv "+tmpCsvFile, shell=True)
            print("File: ", fileList[fileIdx])
            fileIdx+=1
            if(val == 0):
                dataset = pd.read_csv(tmpCsvFile, infer_datetime_format=True, 
                        names=HEADER) #, header=0,  parse_dates=['UTC time'], index_col=['UTC time'])    
                # print(dataset.head(2))
                if ("ugrd_vgrd" in weatherVariable or "tmp_dpt" in weatherVariable):
                    vdataset = dataset[varSeparator:]
                    udataset = dataset[:varSeparator]
                    # print(udataset.tail(2))
                    # print(vdataset.head(2))
                    for line in range(len(udataset)):
                        lon = float(udataset["longitude"].values[line])
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
                    # now we have region-wise datasets for this timestamp
                    vdataset = None
                    udataset = None
                    for region in ISO_BOUNDING_BOX.keys():
                        udataset = pd.DataFrame(urow[region], columns=HEADER)
                        vdataset = pd.DataFrame(vrow[region], columns=HEADER)
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
                            # print(len(windSpeed), len(latitude[region]), len(longitude[region]), len(latitude[region])*len(longitude[region]))
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
                        dataset = pd.DataFrame(row[region], columns=HEADER)
                        if (i==0):
                            latitude[region] = np.unique(dataset["latitude"].values)
                            longitude[region] = np.unique(dataset["longitude"].values)
                            grid_cell_area[region] = area_grid(latitude[region], longitude[region])
                            total_area_of_earth[region] = np.sum(grid_cell_area[region])
                        if region not in weatherVarRow.keys():
                            weatherVarRow[region] = [dataset["startDate"].iloc[0], dataset["param"].iloc[0], dataset["level"].iloc[0],
                                        dataset["latitude"].iloc[0], dataset["longitude"].iloc[0]]
                        
                        value = dataset["value"].values
                        value = np.reshape(value, (len(latitude[region]), len(longitude[region])))
                        weighted_mean = (value * grid_cell_area[region]) / total_area_of_earth[region]
                        weighted_mean = np.sum(weighted_mean)
                        weatherVarRow[region].append(weighted_mean)
                delFile = subprocess.call("rm "+tmpCsvFile, shell=True)
                if(delFile != 0):
                    print("Error: Process call failed -- rm")
            else:
                print("Error: Process call failed -- ", GRIB2_CMD)
                
        for region in ISO_BOUNDING_BOX.keys():
            if ("tmp_dpt" in weatherVariable):
                if region not in tmprows.keys():
                    tmprows[region] = [tmprow[region]]
                else:    
                    tmprows[region].append(tmprow[region])
                if (region not in dptrows.keys()):
                    dptrows[region] = [dptrow[region]]
                else:
                    dptrows[region].append(dptrow[region])
            else:
                if ("ugrd_vgrd" in weatherVariable):
                    if (region not in rows.keys()):
                        rows[region] = [windrow[region]]
                    else:
                        rows[region].append(windrow[region])
                else:
                    if (region not in rows.keys()):
                        rows[region] = [weatherVarRow[region]]
                    else:
                        rows[region].append(weatherVarRow[region])

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
        with open(regionOutFilePath+region+"_"+weatherVariableFileName, writeMode) as regioncsvfile:
            csvwriter = csv.writer(regioncsvfile)
            csvwriter.writerow(csvFields)
            csvwriter.writerows(weatherValues[region])

def startScript(continent, regionList, index, pid, inFilePath, outFilePath, isRealTime, startDate):
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
        windSpeed, nop = fetchWeatherDataByRegion(inFilePath[index], FCST, pid, isRealTime, startDate, varSeparator)
        writeWeatherValuesToFile(outFilePath, windSpeed, CSV_FILE_FIELDS_FCST, weatherVariable[0]+".csv", isRealTime)
    elif ("tmp_dpt" in inFilePath[index]):
        temperature, dewpoint = fetchWeatherDataByRegion(inFilePath[index], FCST, pid, isRealTime, startDate, varSeparator)
        writeWeatherValuesToFile(outFilePath, temperature, CSV_FILE_FIELDS_FCST, weatherVariable[1]+".csv", isRealTime)
        writeWeatherValuesToFile(outFilePath, dewpoint, CSV_FILE_FIELDS_FCST, weatherVariable[2]+".csv", isRealTime)
    else:
        weatherValues, nop = fetchWeatherDataByRegion(inFilePath[index], FCST_AVG_ACC, pid, isRealTime, startDate, varSeparator)
        if ("dswrf" in inFilePath[index]):
            writeWeatherValuesToFile(outFilePath, weatherValues, CSV_FILE_FIELDS_AVG, weatherVariable[3]+".csv", isRealTime)
        else:
            writeWeatherValuesToFile(outFilePath, weatherValues, CSV_FILE_FIELDS_ACC, weatherVariable[4]+".csv", isRealTime)
        
    
    return


if __name__ == "__main__":
    print("Separating whole US data by CarbonCast regions...")
    print("Usage: python3 separateWeatherByRegion <continent> <index>")
    print("Continent: US") # curently, only US is supported
    print("Index: 0 -> wind speed, 1 -> tmp/dpt, 2-> dswrf, 3 -> apcp")
    if (len(sys.argv) < 3):
        print("Wrong no. of arguments!")
        exit(0)

    continent = sys.argv[1]
    index = int(sys.argv[2])
    regionList = US_REGION_LIST
    # index: 0 = wind, 1 = tmp/dpt, 2 = dswrf, 3 = apcp
    inFilePath = FILE_DIR
    outFilePath = OUT_FILE_DIR
    if (continent == "EU"):
        regionList = EU_REGION_LIST
        print("Coming soon!") # not ready yet
        exit(0)
    startScript(continent, regionList, index, os.getpid(), inFilePath, outFilePath, isRealTime=False, startDate=None)