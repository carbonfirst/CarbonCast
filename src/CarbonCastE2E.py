"""This script functions as an end-to-end script to run Carboncast. It can be run as follows:
    python3 <continent> <date>
    where continent has the regions of interest and <date> is the date of interest.

    This script will then do the following in order:
    - Download the data from the EIA API
    - Download weather data from NOMADS for the region and date of interest
    - Run the first-tier model on the downloaded data and generate models for each source
    - Run the second-tier model on the downloaded data and generate 96-hour carbon intensity forecasts
"""

"""
Regions covered by continent:
    US: United States --> yes 
    CA: Canada --> no
    SA: South America --> no
    EU: Europe --> no
    AUS: Oceania --> Australia (no), NZ (no)
    ASIA: Asia --> no
"""

import pandas as pd
import eiaParser
from weather import getRealTimeWeatherData, separateWeatherByRegion, cleanWeatherData
import carbonIntensityCalculator as cicalc
import os
import sys
import subprocess
from datetime import datetime, timedelta
import firstTierForecasts as ftf
import secondTierForecasts as stf
import cisoSolarWindForecastParser as cisosolwndfcst

REAL_TIME_FILE_DIR = "../real_time/"
REAL_TIME_WEATHER_FILE_DIR = "../real_time/weather_data/"

US_REGIONS = ["AECI", "AZPS", "BPAT", "CISO", "DUK", "EPE", "ERCO", "FPL", 
                "ISNE", "LDWP", "MISO", "NEVP", "NWMT", "NYIS", "PACE", "PJM", 
                "SC", "SCEG", "SOCO", "SRP", "TIDC", "TVA", "WACM"] # add US regions here

US_REGIONS = ["CISO"]

EU_REGIONS = [] # add EU regions here

def fetchElectricityData(continent, baList, startDate):
    # TODO: Change this to be downloaded only for the specific region
    print(f"Downloading EIA data on {startDate} for all regions in {continent}")
    if (continent == "US"):
        for balAuth in baList:
            # get electricity data
            fetchedDataset = eiaParser.getELectricityProductionDataFromEIA(balAuth, startDate, numDays=1, DAY_JUMP=1)
            filedir = os.path.dirname(__file__)
            csvFile = os.path.normpath(os.path.join(filedir, f"{REAL_TIME_FILE_DIR}{balAuth}/{balAuth}_{str(startDate)}.csv"))
            with open(csvFile, 'w') as f:
                fetchedDataset.to_csv(f, index=False)
            print("Electricity data fetched")
            # clean electricity data
            fetchedDataset = pd.read_csv(csvFile, header=0, parse_dates=["UTC time"], index_col=["UTC time"])
            cleanedDataset = eiaParser.cleanElectricityProductionDataFromEIA(fetchedDataset, balAuth)
            csvFileClean = REAL_TIME_FILE_DIR+balAuth+"/"+balAuth+"_"+str(startDate)+"_clean.csv"
            cleanedDataset.to_csv(csvFileClean)
            print("Electricity data cleaned")

            # adjust source columns
            cleanedDataset = pd.read_csv(csvFileClean, header=0, index_col=["UTC time"])
            modifiedDataset = eiaParser.adjustColumns(cleanedDataset, balAuth)
            modifiedDataset.to_csv(csvFile)
            val = subprocess.call("rm "+csvFileClean, shell=True)
        print("Download complete")

        print("Calculating lifecycle and direct CI values")
        for balAuth in baList:
            inFileName = REAL_TIME_FILE_DIR+balAuth+"/"+balAuth+"_"+str(startDate)+".csv"
            lifecycleOutFileName = REAL_TIME_FILE_DIR+balAuth+"/"+balAuth+"_"+str(startDate)+"_lifecycle_emissions.csv"
            directOutFileName = REAL_TIME_FILE_DIR+balAuth+"/"+balAuth+"_"+str(startDate)+"_direct_emissions.csv"
            cicalc.runProgram(region=balAuth, isLifecycle=True, isForecast=False, realTimeInFileName=inFileName, 
                              realTimeOutFileName=lifecycleOutFileName, forecastInFileName=None, 
                              forecastOutFileName=None)
            cicalc.runProgram(region=balAuth, isLifecycle=False, isForecast=False, realTimeInFileName=inFileName, 
                              realTimeOutFileName=directOutFileName, forecastInFileName=None, 
                              forecastOutFileName=None)
            print(f"Generated lifecycle & direct emissions for {balAuth} on {startDate}")
    else:
        print("Continent (region) not covered by CarbonCast at this time.")
    return

def fetchWeatherData(continent, baList, startDate):
    print(f"Downloading weather data for {continent} on {startDate}")
        
    # fetch weather forecasts
    getRealTimeWeatherData.getWeatherData(continent=continent, date=startDate)
    
    # aggregate weather forecasts
    inFilePath = [REAL_TIME_WEATHER_FILE_DIR+"ugrd_vgrd/",
        REAL_TIME_WEATHER_FILE_DIR+"tmp_dpt/",
        REAL_TIME_WEATHER_FILE_DIR+"dswrf/",
        REAL_TIME_WEATHER_FILE_DIR+"apcp/"]
    outFilePath = REAL_TIME_FILE_DIR
    separateWeatherByRegion.startScript(regionList=baList, index=0, pid=os.getpid(), 
                                        inFilePath=inFilePath, outFilePath=outFilePath, 
                                        isRealTime=True, startDate=startDate) # index 0 is wind
    separateWeatherByRegion.startScript(regionList=baList, index=1, pid=os.getpid(), 
                                        inFilePath=inFilePath, outFilePath=outFilePath, 
                                        isRealTime=True, startDate=startDate) # index 1 is tmp/dpt
    separateWeatherByRegion.startScript(regionList=baList, index=2, pid=os.getpid(), 
                                        inFilePath=inFilePath, outFilePath=outFilePath, 
                                        isRealTime=True, startDate=startDate) # index 2 is dswrf
    separateWeatherByRegion.startScript(regionList=baList, index=3, pid=os.getpid(), 
                                        inFilePath=inFilePath, outFilePath=outFilePath, 
                                        isRealTime=True, startDate=startDate) # index 3 is apcp

    # clean weather forecasts
    columnNames = ["forecast_avg_wind_speed_wMean", "forecast_avg_temperature_wMean", "forecast_avg_dewpoint_wMean", 
                    "forecast_avg_dswrf_wMean", "forecast_avg_precipitation_wMean"]
    cleanWeatherData.startScript(regionList=baList, fileDir=REAL_TIME_FILE_DIR, 
                                    columnNames=columnNames, isRealTime=True, startDate=startDate)
    print("Generated weather forecasts")
    return

def fetchSolarWindForecastsForCISO(filePath, startDate):
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d")
    endDateObj = startDateObj + timedelta(days=1)
    endDate = endDateObj.strftime("%Y-%m-%d")
    solWindFcstFileName, solWindFcstDataset = cisosolwndfcst.startScript(FILE_PATH=filePath+"CISO/", 
                                                                         startDate=startDate, endDate=endDate,
                                                                         dayJump=1)
    return solWindFcstFileName, solWindFcstDataset

def generateSourceProductionForecasts(baList, startDate, electricityDataDate, solWindFcstDataset):
    # generate source production forecasts for each source & aggregate them in 1 file along with weather forecasts
    return ftf.runFirstTierInRealTime(configFileName="firstTierConfig.json", regionList=baList, startDate=startDate,
                                      electricityDataDate=electricityDataDate, solWindFcstData=solWindFcstDataset,
                                      realTimeFileDir=REAL_TIME_FILE_DIR, 
                                      realTimeWeatherFileDir=REAL_TIME_FILE_DIR)

def generateCIForecasts(baList, startDate, electricityDataDate, aggregatedForecastFileName):
    # generate lifecycle & direct CI forecasts & write them to respective files
    lifecycleCIForecastFile =  stf.runSecondTierInRealTime(configFileName="secondTierConfig.json", 
                                                           regionList=baList, cefType="-l", startDate=startDate,
                                                           electricityDataDate=electricityDataDate,
                                                           realTimeFileDir=REAL_TIME_FILE_DIR, 
                                                           realTimeWeatherFileDir=REAL_TIME_FILE_DIR,
                                                           realTimeForeCastFileName = aggregatedForecastFileName)
    directCIForecastFile =  stf.runSecondTierInRealTime(configFileName="secondTierConfig.json", 
                                                           regionList=baList, cefType="-d", startDate=startDate,
                                                           electricityDataDate=electricityDataDate,                                                           
                                                           realTimeFileDir=REAL_TIME_FILE_DIR, 
                                                           realTimeWeatherFileDir=REAL_TIME_FILE_DIR,
                                                           realTimeForeCastFileName = aggregatedForecastFileName)
    directCIForecastFile = None
    return lifecycleCIForecastFile, directCIForecastFile

def startScript(continent, baList, startDate):
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d")
    electricityDataDateObj = startDateObj - timedelta(days=1)
    electricityDataDate = electricityDataDateObj.strftime("%Y-%m-%d")
    # forecast date is in the future, so real time electricity data needs to be from the previous date
    fetchElectricityData(continent, baList, electricityDataDate)
    fetchWeatherData(continent, baList, startDate)
    if ("CISO" in baList):
        print("Fetching solar wind forecasts")
        solWindFcstFileName, solWindFcstDataset = fetchSolarWindForecastsForCISO(REAL_TIME_FILE_DIR, startDate)
    aggregatedForecastFileNames = generateSourceProductionForecasts(baList, startDate, 
                                                                    electricityDataDate, solWindFcstDataset) # first tier
    lifecycleCIForecastFile, directCIForecastFile = generateCIForecasts(baList, startDate, 
                                                                        electricityDataDate, aggregatedForecastFileNames) # second tier
    return



if __name__ == "__main__":

    startDate = None
    continent = None
    startTime = datetime.now()
    print("Usage: python3 CarbonCastE2E.py <continent> <starting forecast date in yyyy-mm-dd>")
    if (len(sys.argv) < 2):
        print("Must specify region. Exiting.")
        exit(0)
    elif (len(sys.argv) == 2):
        continent = sys.argv[1]
        startDate = datetime.today().strftime('%Y-%m-%d')
        print("No start date specified. Taking current day as default start date: ", startDate)
    elif (len(sys.argv) == 3):
        continent = sys.argv[1]
        startDate = sys.argv[2]
    
    baList = None
    if continent == "US":
        baList = US_REGIONS

    print(continent, baList, startDate)
    startScript(continent, baList, startDate)
    endTime = datetime.now()
    diffTime = (endTime - startTime).total_seconds()
    print("Total time taken for CarbonCast to run end to end = ", diffTime, " secs, = ", diffTime/60, " mins")
