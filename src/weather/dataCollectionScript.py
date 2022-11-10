'''
This file uses the code from https://towardsdatascience.com/the-correct-way-to-average-the-globe-92ceecd172b7 
for the below two functions:
    earth_radius()
    area_grid()
These functions aggregate the weather data over a specified bounding box.
'''


import subprocess
from collections import namedtuple
from calendar import monthrange
import os.path
import pandas as pd
import csv
import math
import numpy as np

ISO_LIST = ["AUS_QLD"]
# IF 2 CONSECUTIVE FILES ARE NOT PRESENT, MANUALLY ADD THEM

GRIB2_CMD = "grib2/wgrib2/wgrib2"
# FILE_DIR = "gfs.0p25.2020010100-2021010100.f000.grib2/"

FILE_PREFIX = "gfs.0p25."
UGRD_VGRD_SEPRATOR = {"CISO": 1886, "PJM": 2556, "SE": 2296, "DK-DK2": 221, 
                        "ERCO": 2116, "ISNE": 1056, "GB": 1978, "DE": 1254, 
                        "PL": 984, "AUS_NSW": 64, "AUS_QLD": 5695, "AUS_SA": 2809}
TMP_DPT_SEPARATOR = {"CISO": 1886, "PJM": 2556, "SE": 2296, "DK-DK2": 221, 
                        "ERCO": 2116, "ISNE": 1056, "GB": 1978, "DE": 1254, 
                        "PL": 984, "AUS_NSW": 64, "AUS_QLD": 5695, "AUS_SA": 2809}

HOUR = ["00"] ##, "06", "12", "18"]
FCST = ["000", "003", "006", "009", "012", "015", "018", "021", "024",
                "027", "030", "033", "036", "039", "042", "045", "048",
                "051", "054", "057", "060", "063", "066", "069", "072",
                "075", "078", "081", "084", "087", "090", "093", "096"]
FCST_AVG_ACC = ["003", "006", "009", "012", "015", "018", "021", "024",
                "027", "030", "033", "036", "039", "042", "045", "048",
                "051", "054", "057", "060", "063", "066", "069", "072",
                "075", "078", "081", "084", "087", "090", "093", "096"]
YEARS = [2019, 2020, 2021]
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

def getFileList(yearList=[2020], fileDir = None, fcstCol=FCST):
    fileList = []
    prevFile = None
    for year in yearList:
        for month in range(1, 13): # Month is always 1..12
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
                        else:
                            fileList.append(filePath)
                            prevFile = fileName # assuming the first file to be searched is always present
    return fileList

def getWeatherData(fileList, csvFields, outFileName, fcstCol, weatherVariable):
    with open(outFileName, 'w') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile)                    
        # writing the fields 
        csvwriter.writerow(csvFields)
    fileIdx = 0
    rows = []
    while fileIdx < len(fileList):
        row = None
        lat = None
        lon = None
        # weatherValues = []
        for i in range(len(fcstCol)):
            val = subprocess.call(GRIB2_CMD + " " + fileList[fileIdx] + " -csv tmp.csv", shell=True)
            fileIdx+=1
            if(val == 0):
                dataset = pd.read_csv("tmp.csv", infer_datetime_format=True, 
                        names=HEADER) #, header=0,  parse_dates=['UTC time'], index_col=['UTC time'])    
                # print(dataset.head(2))
                if (weatherVariable == "TEMP"):
                    dataset = dataset[:TMP_DPT_SEPARATOR[ISO]]
                elif (weatherVariable == "DPT"):
                    dataset = dataset[TMP_DPT_SEPARATOR[ISO]:]
                if (i==0):
                    lat = np.unique(dataset["latitude"].values)
                    lon = np.unique(dataset["longitude"].values)
                    grid_cell_area = area_grid(lat, lon)
                    total_area_of_earth = np.sum(grid_cell_area)
                # averageValue = round(dataset["value"].mean(), 5)
                
                if row is None:
                    row = [dataset["startDate"].iloc[0], dataset["param"].iloc[0], dataset["level"].iloc[0],
                                dataset["latitude"].iloc[0], dataset["longitude"].iloc[0]]

                value = dataset["value"].values
                # weighted_mean = np.mean(temperature)
                value = np.reshape(value, (len(lat), len(lon)))
                weighted_mean = (value * grid_cell_area) / total_area_of_earth
                weighted_mean = np.sum(weighted_mean)
                row.append(weighted_mean)
                delFile = subprocess.call("rm tmp.csv", shell=True)
                if(delFile != 0):
                    print("Error: Process call failed -- rm")
            else:
                print("Error: Process call failed -- ", GRIB2_CMD)
        # writing to csv file
        # print(weatherValues)
        # row.extend(weatherValues) 
        rows.append(row)
    with open(outFileName, 'a') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerows(rows)

    return

def getWindData(fileList, csvFields, outFileName):
    # print(len(fileList))
    # exit(0)
    with open(outFileName, 'w') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile)                    
        # writing the fields 
        csvwriter.writerow(csvFields)
    fileIdx = 0
    rows = []
    
    while fileIdx < len(fileList):
        row = None
        lat = None
        lon = None
        grid_cell_area = None
        total_area_of_earth = None
        # weatherValues = []
        for i in range(len(FCST)):
            val = subprocess.call(GRIB2_CMD + " " + fileList[fileIdx] + " -csv tmp.csv", shell=True)
            fileIdx+=1
            if(val == 0):
                dataset = pd.read_csv("tmp.csv", infer_datetime_format=True, 
                        names=HEADER) #, header=0,  parse_dates=['UTC time'], index_col=['UTC time'])    
                # print(dataset.head(2))
                vdataset = dataset[UGRD_VGRD_SEPRATOR[ISO]:]
                udataset = dataset[:UGRD_VGRD_SEPRATOR[ISO]]
                if (i==0):
                    lat = np.unique(dataset["latitude"].values)
                    lon = np.unique(dataset["longitude"].values)
                    grid_cell_area = area_grid(lat, lon)
                    total_area_of_earth = np.sum(grid_cell_area)
                if row is None:
                    row = [dataset["startDate"].iloc[0], dataset["param"].iloc[0], dataset["level"].iloc[0],
                                dataset["latitude"].iloc[0], dataset["longitude"].iloc[0]]

                windSpeed = (udataset["value"].values**2 + vdataset["value"].values**2)**(0.5)
                # weighted_mean = np.mean(temperature)
                value = np.reshape(windSpeed, (len(lat), len(lon)))
                weighted_mean = (value * grid_cell_area) / total_area_of_earth
                weighted_mean = np.sum(weighted_mean)
                row.append(weighted_mean)
                
                delFile = subprocess.call("rm tmp.csv", shell=True)
                if(delFile != 0):
                    print("Error: Process call failed -- rm")
            else:
                print("Error: Process call failed -- ", GRIB2_CMD)
        # writing to csv file
        # print(weatherValues)
        # row.extend(weatherValues) 
        rows.append(row)
    with open(outFileName, 'a') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerows(rows)

    return

def addColumnToCSVFile(fileName, newColName, newColValue):
    dataset = pd.read_csv(fileName, header=0)
    dataset[newColName] = newColValue
    dataset.to_csv(fileName)
    return

def getWindSpeedAcrossAllRegions(inFileName):
    maxWindSpeedList = []
    totalWindSpeedList = []
    avgWindSpeedList = []
    uWindFileList = None
    if (inFileName is None):
        uWindFileList = getFileList(2020, "SE/ugrd_vgrd/")
    else:
        uWindFileList = getFileList(2020, inFileName)
    # vWindFileList = getFileList(2020, "ds084_1/vGRD/")
    fileIdx = 0
    rows = []
    while fileIdx < len(uWindFileList):
        row = None
        # weatherValues = []
        for i in range(len(FCST)):
            uval = subprocess.call(GRIB2_CMD + " " + uWindFileList[fileIdx] + " -csv utmp.csv", shell=True)
            if(uval == 0):
                vval = 0 #subprocess.call(GRIB2_CMD + " " + vWindFileList[fileIdx] + " -csv vtmp.csv", shell=True)
                fileIdx+=1
                if (vval == 0):
                    udataset = pd.read_csv("utmp.csv", infer_datetime_format=True, 
                            names=HEADER)
                    # vdataset = pd.read_csv("vtmp.csv", infer_datetime_format=True, 
                    #         names=HEADER)
                    vdataset = udataset[UGRD_VGRD_SEPRATOR[ISO]:]
                    udataset = udataset[:UGRD_VGRD_SEPRATOR[ISO]]
                    # if row is None:
                    #     row = [dataset["startDate"].iloc[cityIdx], dataset["param"].iloc[cityIdx], dataset["level"].iloc[cityIdx],
                    #                 dataset["latitude"].iloc[cityIdx], dataset["longitude"].iloc[cityIdx]]

                    maxWindSpeed = 0
                    totalWindSpeed = 0
                    avgWindSpeed = 0
                    for j in range(len(udataset)):
                        u = udataset["value"].iloc[j]
                        v = vdataset["value"].iloc[j]
                        windSpeed = math.sqrt(u*u + v*v)
                        totalWindSpeed +=windSpeed
                        if  windSpeed> maxWindSpeed:
                            maxWindSpeed = windSpeed
                    avgWindSpeed = totalWindSpeed/len(udataset)
                    maxWindSpeedList.append([udataset["startDate"].iloc[0], maxWindSpeed])
                    totalWindSpeedList.append([udataset["startDate"].iloc[0], totalWindSpeed])
                    avgWindSpeedList.append([udataset["startDate"].iloc[0], avgWindSpeed])
                    # delFile = subprocess.call("rm utmp.csv", shell=True)
                    # if(delFile != 0):
                    #     print("Error: Process call failed -- rm")
                else:
                    print("Error: Process call failed -- ", GRIB2_CMD)
            else:
                print("Error: Process call failed -- ", GRIB2_CMD)
        # writing to csv file
        # print(weatherValues)
        # row.extend(weatherValues) 
        # rows.append(row)
    return maxWindSpeedList, totalWindSpeedList, avgWindSpeedList

def getTotalDWSRFcrossAllRegions():
    totalWindSpeedList = []
    avgWindSpeedList = []
    dswrfFileList = getFileList(2020, "PJM/dswrf/")
    # vWindFileList = getFileList(2020, "ds084_1/vGRD/")
    fileIdx = 0
    rows = []
    while fileIdx < len(dswrfFileList):
        row = None
        # weatherValues = []
        for i in range(len(FCST)):
            uval = subprocess.call(GRIB2_CMD + " " + dswrfFileList[fileIdx] + " -csv utmp.csv", shell=True)
            if(uval == 0):
                fileIdx+=1
                udataset = pd.read_csv("utmp.csv", infer_datetime_format=True, 
                        names=HEADER)
                totalWindSpeed = np.sum(udataset["value"].values)
                avgWindSpeed = np.average(udataset["value"].values)
                totalWindSpeedList.append([udataset["startDate"].iloc[0], totalWindSpeed])
                avgWindSpeedList.append([udataset["startDate"].iloc[0], avgWindSpeed])
            else:
                print("Error: Process call failed -- ", GRIB2_CMD)
        # writing to csv file
        # print(weatherValues)
        # row.extend(weatherValues) 
        # rows.append(row)
    return totalWindSpeedList, avgWindSpeedList

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

# # maxWindSpeedList, totalWindSpeedList, avgWindSpeedList = getWindSpeedAcrossAllRegions()
# totalDwsrfList, avgDwsrfList = getTotalDWSRFcrossAllRegions()
# # pd.DataFrame(maxWindSpeedList).to_csv("SE_maxWS.csv")
# pd.DataFrame(totalDwsrfList).to_csv("PJM_totalDWSRF.csv")
# pd.DataFrame(avgDwsrfList).to_csv("PJM_avgDWSRF.csv")



for ISO in ISO_LIST:
    # FILE_DIR = ["../final_weather_data/"+ISO+"/ugrd_vgrd/", #/2019_weather_data
    #         "../final_weather_data/"+ISO+"/tmp_dpt/",
    #         "../final_weather_data/"+ISO+"/tmp_dpt/",
    #         "../final_weather_data/"+ISO+"/dswrf/",
    #         "../final_weather_data/"+ISO+"/apcp/"]

    # OUT_FILE_NAME_LIST = ["../final_weather_data/"+ISO+"/"+ISO+"_AVG_WIND_SPEED.csv", #/2019_weather_data
    #                     "../final_weather_data/"+ISO+"/"+ISO+"_AVG_TEMP.csv",
    #                     "../final_weather_data/"+ISO+"/"+ISO+"_AVG_DPT.csv",
    #                     "../final_weather_data/"+ISO+"/"+ISO+"_AVG_DSWRF.csv",
    #                     "../final_weather_data/"+ISO+"/"+ISO+"_AVG_PCP.csv"]

    FILE_DIR = ["../extn/"+ISO+"/weather_data/ugrd_vgrd/",
            "../extn/"+ISO+"/weather_data/tmp_dpt/",
            "../extn/"+ISO+"/weather_data/tmp_dpt/",
            "../extn/"+ISO+"/weather_data/dswrf/",
            "../extn/"+ISO+"/weather_data/apcp/"]

    OUT_FILE_NAME_LIST = ["../extn/"+ISO+"/weather_data/"+ISO+"_AVG_WIND_SPEED.csv",
                        "../extn/"+ISO+"/weather_data/"+ISO+"_AVG_TEMP.csv",
                        "../extn/"+ISO+"/weather_data/"+ISO+"_AVG_DPT.csv",
                        "../extn/"+ISO+"/weather_data/"+ISO+"_AVG_DSWRF.csv",
                        "../extn/"+ISO+"/weather_data/"+ISO+"_AVG_PCP.csv"]

    # FILE_DIR = ["../extn/"+ISO+"/weather_data/tmp_dpt/",
    #         "../extn/"+ISO+"/weather_data/tmp_dpt/"]
            
    # OUT_FILE_NAME_LIST = ["../extn/"+ISO+"/weather_data/"+ISO+"_AVG_TEMP.csv",
    #                     "../extn/"+ISO+"/weather_data/"+ISO+"_AVG_DPT.csv"]

    print("*******************", ISO, "*******************")
    for xx in range(len(OUT_FILE_NAME_LIST)):
        if ("WIND" in OUT_FILE_NAME_LIST[xx]):
            fileList = getFileList(YEARS, FILE_DIR[xx], fcstCol=FCST)
            print("WIND: ", OUT_FILE_NAME_LIST[xx])
            getWindData(fileList, CSV_FILE_FIELDS_FCST, OUT_FILE_NAME_LIST[xx])
        else:
            if ("TEMP" in OUT_FILE_NAME_LIST[xx]):
                fileList = getFileList(YEARS, FILE_DIR[xx], fcstCol=FCST)
                print("TEMP: ", OUT_FILE_NAME_LIST[xx])
                getWeatherData(fileList, CSV_FILE_FIELDS_FCST, OUT_FILE_NAME_LIST[xx], FCST, "TEMP")
            elif ("DPT" in OUT_FILE_NAME_LIST[xx]):
                fileList = getFileList(YEARS, FILE_DIR[xx], fcstCol=FCST)
                print("DPT: ", OUT_FILE_NAME_LIST[xx])
                getWeatherData(fileList, CSV_FILE_FIELDS_FCST, OUT_FILE_NAME_LIST[xx], FCST, "DPT")
            elif ("DSWRF" in OUT_FILE_NAME_LIST[xx]):
                fileList = getFileList(YEARS, FILE_DIR[xx], fcstCol=FCST_AVG_ACC)
                print("DSWRF: ", OUT_FILE_NAME_LIST[xx])
                getWeatherData(fileList, CSV_FILE_FIELDS_AVG, OUT_FILE_NAME_LIST[xx], FCST_AVG_ACC, "DSWRF")
            elif ("PCP" in OUT_FILE_NAME_LIST[xx]):
                fileList = getFileList(YEARS, FILE_DIR[xx], fcstCol=FCST_AVG_ACC)
                print("PCP: ", OUT_FILE_NAME_LIST[xx])
                getWeatherData(fileList, CSV_FILE_FIELDS_ACC, OUT_FILE_NAME_LIST[xx], FCST_AVG_ACC, "PCP")
    print("*******************", ISO, " done *******************")

