import os
import requests
import zipfile
import io
import pandas as pd
from datetime import datetime, timedelta
import time
import numpy as np
import subprocess

FILE_PATH = "../data/CISO/solar_wind_forecasts/"

def getFileFromWeb(FILE_PATH, startDate, endDate=None):
    startDateStr = startDate.split("-")
    startDateStr = startDateStr[0]+startDateStr[1]+startDateStr[2]
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d")
    if (endDate is None):
        endDate = startDateObj + timedelta(days=1)
        endDateStr = endDate.strftime("%Y-%m-%d").split("-")
    else:
        endDateStr = endDate.split("-")
    endDateStr = endDateStr[0]+endDateStr[1]+endDateStr[2]
    print(startDateStr, endDateStr)

    requestUrl = "http://oasis.caiso.com/oasisapi/SingleZip?queryname=SLD_REN_FCST&market_run_id=DAM&startdatetime="+startDateStr+"T00:00-0000&enddatetime="+endDateStr+"T0:00-0000&resultformat=6&version=1"
    print(requestUrl)
    resp = requests.get(requestUrl)
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    z.extractall(FILE_PATH)
    os.rename(FILE_PATH+z.namelist()[0], FILE_PATH+"CISO_raw_solar_wind_forecast_"+str(startDate)+".csv")

    if (resp.status_code != 200):
        print("Error! Code: ", resp.status_code)
        print("Error! Message: ", resp.text)
        print("Error! Reason: ", resp.reason)
        
    return FILE_PATH+"CISO_raw_solar_wind_forecast_"+str(startDate)+".csv", resp.status_code

def parseDataset(inFileName, dayJump=1):
    dataset = pd.read_csv(inFileName, header=0)
    dataset = dataset.sort_values(by=["TRADING_HUB", "RENEWABLE_TYPE", "OPR_DT", "OPR_HR"], ignore_index=True)
    np15Solar = np.array(dataset["MW"].values[0:24*dayJump], dtype=float)
    np15Wind = np.array(dataset["MW"].values[24*dayJump:48*dayJump], dtype=float)
    sp15Solar = np.array(dataset["MW"].values[48*dayJump:72*dayJump], dtype=float)
    sp15wind = np.array(dataset["MW"].values[72*dayJump:96*dayJump], dtype=float)
    zp26Solar = np.array(dataset["MW"].values[96*dayJump:120*dayJump], dtype=float)

    solarProdcutionForecast = np15Solar + sp15Solar + zp26Solar
    windProductionForecast = np15Wind + sp15wind

    return dataset["INTERVALSTARTTIME_GMT"].values[:24*dayJump], solarProdcutionForecast, windProductionForecast

def createCleanedForecastFile(rawFileName, cleanedFileName, dates, solarForecast, windForecast, 
                              creationTimeInUTC, version):
    cleanDataset = pd.DataFrame(
        {"UTC time": dates,
         "avg_solar_production_forecast": solarForecast,
         "avg_wind_production_forecast": windForecast
        })
    cleanDataset.set_index("UTC time", inplace=True)
    if (creationTimeInUTC is not None and version is not None):
        cleanDataset.insert(0, "creation_time (UTC)", creationTimeInUTC)
        cleanDataset.insert(1, "version", version)
    cleanDataset.to_csv(cleanedFileName)
    val = subprocess.call("rm "+rawFileName, shell=True)
    return cleanDataset

def startScript(FILE_PATH, startDate, endDate, dayJump=1, creationTimeInUTC=None,
                version=None):
    filename, status = getFileFromWeb(FILE_PATH, startDate, endDate)
    print(filename)
    dates, solarForecast, windForecast = parseDataset(filename, dayJump)
    cleanedFileName = FILE_PATH+"CISO_solar_wind_forecast_"+str(startDate)+".csv"
    cleanDataset = createCleanedForecastFile(filename, cleanedFileName, dates, solarForecast, windForecast, 
                                             creationTimeInUTC, version)
    print(cleanDataset.head())
    return cleanedFileName, cleanDataset



if __name__ == "__main__":
    fullDataset = pd.DataFrame()
    startDate = "2022-01-01"
    numDays = 368
    dayJump = 8
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d")
    for days in range(0, numDays, 8):
        print(startDate)
        endDateObj = startDateObj + timedelta(days=8)
        endDate = endDateObj.strftime("%Y-%m-%d")
        outFileName, dataset = startScript(FILE_PATH, startDate, endDate, dayJump=dayJump, 
                                           creationTimeInUTC=None, version=None)
        if (days == 0):
            fullDataset = dataset.copy()
        else:
            fullDataset = pd.concat([fullDataset, dataset])
        time.sleep(5) # [DM] CAISO OASIS policy: needs to have 5 secs gap between consecutive requests
        startDateObj = startDateObj + timedelta(days=8)
        startDate = startDateObj.strftime("%Y-%m-%d")
        val = subprocess.call("rm "+outFileName, shell=True)
    fullDataset.to_csv(FILE_PATH+"CISO_solar_wind_forecast.csv")
    