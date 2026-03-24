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
import shutil
import re
from datetime import datetime, timedelta
from shutil import which
import firstTierForecasts as ftf
import secondTierForecasts as stf
import cisoSolarWindForecastParser as cisosolwndfcst

REAL_TIME_FILE_DIR = "../real_time/"
REAL_TIME_WEATHER_FILE_DIR = "../real_time/weather_data/"

REGIONS_HAVING_ERRORS = ["SRP", "WACM"] # TODO: Need to check and fix this.

US_REGIONS = ["AECI", "AZPS", "BPAT", "CISO", "DUK", "EPE", "ERCO", "FPL", 
                "ISNE", "LDWP", "MISO", "NEVP", "NWMT", "NYIS", "PACE", "PJM", 
                "SC", "SCEG", "SOCO", "TIDC", "TVA"] # add US regions here

# US_REGIONS = ["CISO"]

EU_REGIONS = [] # add EU regions here

def _get_real_time_region_dir(balAuth):
    filedir = os.path.dirname(__file__)
    return os.path.normpath(os.path.join(filedir, f"{REAL_TIME_FILE_DIR}{balAuth}"))

def _get_real_time_root_dir():
    filedir = os.path.dirname(__file__)
    return os.path.normpath(os.path.join(filedir, REAL_TIME_FILE_DIR))

def _get_real_time_weather_root_dir():
    filedir = os.path.dirname(__file__)
    return os.path.normpath(os.path.join(filedir, REAL_TIME_WEATHER_FILE_DIR))

def _get_src_path(filename):
    filedir = os.path.dirname(__file__)
    return os.path.join(filedir, filename)

def _get_real_time_csv_path(balAuth, date_str):
    return os.path.join(_get_real_time_region_dir(balAuth), f"{balAuth}_{date_str}.csv")

def _get_real_time_emissions_path(balAuth, date_str, emissions_type):
    return os.path.join(
        _get_real_time_region_dir(balAuth),
        f"{balAuth}_{date_str}_{emissions_type}_emissions.csv",
    )

def _get_real_time_clean_path(balAuth, date_str):
    return os.path.join(_get_real_time_region_dir(balAuth), f"{balAuth}_{date_str}_clean.csv")

def _weather_param_dir(param):
    filedir = os.path.dirname(__file__)
    return os.path.normpath(
        os.path.join(filedir, f"{REAL_TIME_WEATHER_FILE_DIR}{param.lower().replace('/', '_')}")
    )

def _exact_weather_files_exist(startDate):
    yyyymmdd = startDate.replace("-", "")
    params = ["UGRD/VGRD", "TMP/DPT", "DSWRF", "APCP"]
    for param in params:
        directory = _weather_param_dir(param)
        for hour in range(3, 97, 3):
            expected = os.path.join(
                directory, f"gfs.t00z.pgrb2.0p25.{yyyymmdd}.f00{hour:02d}.grib2"
            )
            if not os.path.exists(expected):
                return False
    return True

def runPreflightChecks(continent, baList, startDate):
    print("Running realtime preflight checks")
    issues = []
    warnings = []

    if continent == "US":
        if os.getenv("EIA_API_KEY"):
            print("Preflight: EIA_API_KEY configured")
        else:
            warnings.append(
                "EIA_API_KEY is not configured. Live electricity fetch will fail and CarbonCast will rely on cached electricity data if available."
            )

    if which("wgrib2"):
        print(f"Preflight: wgrib2 available at {which('wgrib2')}")
    else:
        issues.append("wgrib2 is not installed or not on PATH.")

    if _exact_weather_files_exist(startDate):
        print(f"Preflight: exact-date weather files already exist for {startDate}")
    else:
        warnings.append(
            f"No exact-date weather files are present for {startDate}. A live NOMADS download is required for realtime forecasting."
        )

    for balAuth in baList:
        region_dir = _get_real_time_region_dir(balAuth)
        os.makedirs(region_dir, exist_ok=True)
        os.makedirs(os.path.join(region_dir, "weather_data"), exist_ok=True)

    if warnings:
        for warning in warnings:
            print(f"Preflight warning: {warning}")
    if issues:
        raise RuntimeError("Preflight failed: " + " ".join(issues))

def _find_cached_electricity_file(balAuth, target_date):
    region_dir = _get_real_time_region_dir(balAuth)
    if not os.path.isdir(region_dir):
        return None

    pattern = re.compile(rf"^{re.escape(balAuth)}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv$")
    candidates = []
    for filename in os.listdir(region_dir):
        match = pattern.match(filename)
        if not match:
            continue
        try:
            candidate_date = datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            continue
        candidates.append((abs((candidate_date - target_date).days), candidate_date, filename))

    if not candidates:
        return None

    _, candidate_date, filename = min(candidates, key=lambda item: (item[0], item[1]))
    return os.path.join(region_dir, filename), candidate_date.strftime("%Y-%m-%d")

def _copy_cached_electricity_data(balAuth, startDate):
    target_date = datetime.strptime(startDate, "%Y-%m-%d")
    cached = _find_cached_electricity_file(balAuth, target_date)
    if cached is None:
        raise FileNotFoundError(f"No cached realtime electricity file found for {balAuth}.")

    cached_path, cached_date = cached
    target_path = _get_real_time_csv_path(balAuth, startDate)
    if os.path.abspath(cached_path) != os.path.abspath(target_path):
        shutil.copyfile(cached_path, target_path)
    print(
        f"Using cached electricity data for {balAuth}: "
        f"{os.path.basename(cached_path)} -> {os.path.basename(target_path)}"
    )
    return target_path, cached_date

def fetchElectricityData(continent, baList, startDate, creationTimeInUTC, version):
    # TODO: Change this to be downloaded only for the specific region
    print(f"Downloading EIA data on {startDate} for all regions in {continent}")
    used_fallback = {}
    if (continent == "US"):
        for balAuth in baList:
            csvFile = _get_real_time_csv_path(balAuth, startDate)
            try:
                fetchedDataset = eiaParser.getELectricityProductionDataFromEIA(
                    balAuth, startDate, numDays=1, DAY_JUMP=1
                )
                with open(csvFile, 'w') as f:
                    fetchedDataset.to_csv(f, index=False)
                print("Electricity data fetched")
                fetchedDataset = pd.read_csv(csvFile, header=0, parse_dates=["UTC time"], index_col=["UTC time"])
                cleanedDataset = eiaParser.cleanElectricityProductionDataFromEIA(fetchedDataset, balAuth)
                csvFileClean = _get_real_time_clean_path(balAuth, str(startDate))
                cleanedDataset.to_csv(csvFileClean)
                print("Electricity data cleaned")

                cleanedDataset = pd.read_csv(csvFileClean, header=0, index_col=["UTC time"])
                modifiedDataset = eiaParser.adjustColumns(cleanedDataset, balAuth)
                modifiedDataset.insert(0, "creation_time (UTC)", creationTimeInUTC)
                modifiedDataset.insert(1, "version", version)
                modifiedDataset.to_csv(csvFile)
                val = subprocess.call("rm "+csvFileClean, shell=True)
            except (eiaParser.EIADataError, pd.errors.ParserError, FileNotFoundError) as exc:
                print(f"Live EIA fetch failed for {balAuth}: {exc}")
                try:
                    csvFile, cached_date = _copy_cached_electricity_data(balAuth, startDate)
                    used_fallback[balAuth] = cached_date
                except FileNotFoundError as fallback_exc:
                    raise RuntimeError(
                        f"Failed to fetch live EIA data for {balAuth} and no cached fallback was available."
                    ) from fallback_exc
        print("Download complete")
        if used_fallback:
            print(f"Fallback electricity data used for: {used_fallback}")

        print("Calculating lifecycle and direct CI values")
        for balAuth in baList:
            inFileName = _get_real_time_csv_path(balAuth, str(startDate))
            lifecycleOutFileName = _get_real_time_emissions_path(balAuth, str(startDate), "lifecycle")
            directOutFileName = _get_real_time_emissions_path(balAuth, str(startDate), "direct")
            cicalc.runProgram(region=balAuth, isLifecycle=True, isForecast=False, realTimeInFileName=inFileName, 
                              realTimeOutFileName=lifecycleOutFileName, forecastInFileName=None, 
                              forecastOutFileName=None, creationTimeInUTC=creationTimeInUTC, version=version)
            cicalc.runProgram(region=balAuth, isLifecycle=False, isForecast=False, realTimeInFileName=inFileName, 
                              realTimeOutFileName=directOutFileName, forecastInFileName=None, 
                              forecastOutFileName=None, creationTimeInUTC=creationTimeInUTC, version=version)
            print(f"Generated lifecycle & direct emissions for {balAuth} on {startDate}")
    else:
        print("Continent (region) not covered by CarbonCast at this time.")
    return

def fetchWeatherData(continent, baList, startDate, creationTimeInUTC, version):
    print(f"Downloading weather data for {continent} on {startDate}")
        
    # fetch weather forecasts
    try:
        getRealTimeWeatherData.getWeatherData(continent=continent, date=startDate)
    except getRealTimeWeatherData.WeatherDownloadError as exc:
        raise RuntimeError(
            f"Live weather data is unavailable for {startDate}. "
            f"CarbonCast will not use weather files from a different date. {exc}"
        ) from exc
    
    # aggregate weather forecasts
    weather_root = _get_real_time_weather_root_dir()
    real_time_root = _get_real_time_root_dir()
    inFilePath = [
        os.path.join(weather_root, "ugrd_vgrd") + "/",
        os.path.join(weather_root, "tmp_dpt") + "/",
        os.path.join(weather_root, "dswrf") + "/",
        os.path.join(weather_root, "apcp") + "/",
    ]
    outFilePath = real_time_root + "/"
    separateWeatherByRegion.startScript(continent=continent, regionList=baList, index=0, pid=os.getpid(), 
                                        inFilePath=inFilePath, outFilePath=outFilePath, 
                                        isRealTime=True, startDate=startDate) # index 0 is wind
    separateWeatherByRegion.startScript(continent=continent, regionList=baList, index=1, pid=os.getpid(), 
                                        inFilePath=inFilePath, outFilePath=outFilePath, 
                                        isRealTime=True, startDate=startDate) # index 1 is tmp/dpt
    separateWeatherByRegion.startScript(continent=continent, regionList=baList, index=2, pid=os.getpid(), 
                                        inFilePath=inFilePath, outFilePath=outFilePath, 
                                        isRealTime=True, startDate=startDate) # index 2 is dswrf
    separateWeatherByRegion.startScript(continent=continent, regionList=baList, index=3, pid=os.getpid(), 
                                        inFilePath=inFilePath, outFilePath=outFilePath, 
                                        isRealTime=True, startDate=startDate) # index 3 is apcp

    # clean weather forecasts
    columnNames = ["forecast_avg_wind_speed_wMean", "forecast_avg_temperature_wMean", "forecast_avg_dewpoint_wMean", 
                    "forecast_avg_dswrf_wMean", "forecast_avg_precipitation_wMean"]
    cleanWeatherData.startScript(regionList=baList, fileDir=real_time_root + "/", 
                                    columnNames=columnNames, isRealTime=True, startDate=startDate,
                                    creationTimeInUTC=creationTimeInUTC, version=version)
    print("Generated weather forecasts")
    return

def fetchSolarWindForecastsForCISO(filePath, startDate, creationTimeInUTC, version):
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d")
    endDateObj = startDateObj + timedelta(days=1)
    endDate = endDateObj.strftime("%Y-%m-%d")
    solWindFcstFileName, solWindFcstDataset = cisosolwndfcst.startScript(FILE_PATH=filePath+"CISO/", 
                                                                         startDate=startDate, endDate=endDate,
                                                                         dayJump=1, creationTimeInUTC=creationTimeInUTC,
                                                                         version=version)
    return solWindFcstFileName, solWindFcstDataset

def generateSourceProductionForecasts(baList, startDate, electricityDataDate, solWindFcstDataset, 
                                      creationTimeInUTC, version):
    # generate source production forecasts for each source & aggregate them in 1 file along with weather forecasts
    return ftf.runFirstTierInRealTime(configFileName=_get_src_path("firstTierConfig.json"), regionList=baList, startDate=startDate,
                                      electricityDataDate=electricityDataDate, solWindFcstData=solWindFcstDataset,
                                      realTimeFileDir=_get_real_time_root_dir() + "/", 
                                      realTimeWeatherFileDir=_get_real_time_root_dir() + "/",
                                      creationTimeInUTC=creationTimeInUTC, version=version)

def generateCIForecasts(baList, startDate, electricityDataDate, aggregatedForecastFileName, 
                        creationTimeInUTC, version):
    # generate lifecycle & direct CI forecasts & write them to respective files
    stf.runSecondTierInRealTime(configFileName=_get_src_path("secondTierConfig.json"), 
                                regionList=baList, cefType="-l", startDate=startDate,
                                electricityDataDate=electricityDataDate,
                                realTimeFileDir=_get_real_time_root_dir() + "/", 
                                realTimeWeatherFileDir=_get_real_time_root_dir() + "/",
                                realTimeForeCastFileName = aggregatedForecastFileName,
                                creationTimeInUTC=creationTimeInUTC, version=version)
    stf.runSecondTierInRealTime(configFileName=_get_src_path("secondTierConfig.json"), 
                                regionList=baList, cefType="-d", startDate=startDate,
                                electricityDataDate=electricityDataDate,                                                           
                                realTimeFileDir=_get_real_time_root_dir() + "/", 
                                realTimeWeatherFileDir=_get_real_time_root_dir() + "/",
                                realTimeForeCastFileName = aggregatedForecastFileName,
                                creationTimeInUTC=creationTimeInUTC, version=version)
    return

def startScript(continent, baList, startDate, creationTimeInUTC, version):
    runPreflightChecks(continent, baList, startDate)
    startDateObj = datetime.strptime(startDate, "%Y-%m-%d")
    electricityDataDateObj = startDateObj - timedelta(days=1)
    electricityDataDate = electricityDataDateObj.strftime("%Y-%m-%d")
    # forecast date is in the future, so real time electricity data needs to be from the previous date
    fetchElectricityData(continent, baList, electricityDataDate, creationTimeInUTC, version)
    fetchWeatherData(continent, baList, startDate, creationTimeInUTC, version)
    solWindFcstDataset = None
    if ("CISO" in baList):
        print("Fetching solar wind forecasts")
        solWindFcstFileName, solWindFcstDataset = fetchSolarWindForecastsForCISO(REAL_TIME_FILE_DIR, startDate, 
                                                                                 creationTimeInUTC, version)
    aggregatedForecastFileNames = generateSourceProductionForecasts(baList, startDate, 
                                                                    electricityDataDate, solWindFcstDataset, 
                                                                    creationTimeInUTC, version) # first tier
    generateCIForecasts(baList, startDate, electricityDataDate, aggregatedForecastFileNames, 
                        creationTimeInUTC, version) # second tier
    return



if __name__ == "__main__":

    startDate = None
    continent = None
    startTime = datetime.now()
    creationTimeInUTC = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    version = "3.0"
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
    startScript(continent, baList, startDate, creationTimeInUTC, version)
    endTime = datetime.now()
    diffTime = (endTime - startTime).total_seconds()
    print("Total time taken for CarbonCast to run end to end = ", diffTime, " secs, = ", diffTime/60, " mins")
