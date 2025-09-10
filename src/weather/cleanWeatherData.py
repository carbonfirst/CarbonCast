import csv
import math
from datetime import datetime as dt
# from datetime import timedelta
from datetime import timezone as tz
# import matplotlib.dates as mdates  # Not used in this script
# import matplotlib.pyplot as plt  # Not used in this script
import numpy as np
import pandas as pd
import pytz as pytz
import os
import sys

US_REGION_LIST = ["AECI"] # add US regions here
EU_REGION_LIST = ["BE"] # add EU regions here]

COLUMN_NAME = ["forecast_avg_wind_speed_wMean", "forecast_avg_temperature_wMean", "forecast_avg_dewpoint_wMean", 
                "forecast_avg_dswrf_wMean", "forecast_avg_precipitation_wMean"]


PREDICTION_PERIOD_DAYS = 7
PREDICTION_WINDOW_HOURS = 24 * PREDICTION_PERIOD_DAYS

def readFile(inFileName):
    print("Filename: ", inFileName)
    
    # First, check if the file has proper headers
    try:
        # Try reading first line to check for headers
        first_line = pd.read_csv(inFileName, nrows=0)
        
        if 'datetime' in first_line.columns:
            # File has proper headers with datetime column
            dataset = pd.read_csv(inFileName, header=0, parse_dates=['datetime'], index_col=['datetime'])
            dataset = dataset.iloc[:, 1:]  # Remove extra columns if needed
        else:
            # File doesn't have 'datetime' in header, read without parsing
            # Check if first column looks like dates
            test_df = pd.read_csv(inFileName, nrows=1, header=None)
            first_val = str(test_df.iloc[0, 0])
            
            # If first value looks like a date, treat first row as data, not header
            if '-' in first_val and ':' in first_val:  # Simple date check
                dataset = pd.read_csv(inFileName, header=None)
                # Set column names based on expected pattern
                num_cols = len(dataset.columns)
                col_names = ['datetime', 'param', 'level', 'latitude', 'longitude']
                
                # Add forecast columns
                if num_cols > 5:
                    # Check if there's an Analysis column (6th column)
                    remaining = num_cols - 5
                    if remaining == 57:  # 1 Analysis + 56 forecast columns
                        col_names.append('Analysis')
                        col_names.extend([f'{i} hr fcst' for i in range(3, 169, 3)])
                    else:  # Just forecast columns
                        col_names.extend([f'{i} hr fcst' for i in range(3, 169, 3)])
                
                dataset.columns = col_names[:num_cols]
                dataset['datetime'] = pd.to_datetime(dataset['datetime'])
                dataset = dataset.set_index('datetime')
                # Remove param, level, lat, lon columns
                dataset = dataset.iloc[:, 3:]
            else:
                # Has headers but no 'datetime' column, use first column as datetime
                dataset = pd.read_csv(inFileName, header=0)
                dataset.iloc[:, 0] = pd.to_datetime(dataset.iloc[:, 0])
                dataset = dataset.set_index(dataset.columns[0])
                dataset.index.name = 'datetime'
                dataset = dataset.iloc[:, 1:]  # Remove extra columns
                
    except Exception as e:
        print(f"Warning reading {inFileName}: {e}, trying alternative approach")
        # Fallback: assume no headers and first column is datetime
        dataset = pd.read_csv(inFileName, header=None)
        dataset.iloc[:, 0] = pd.to_datetime(dataset.iloc[:, 0])
        dataset = dataset.set_index(0)
        dataset.index.name = 'datetime'
        # Remove param, level, lat, lon columns (columns 1-4)
        dataset = dataset.iloc[:, 4:]
        # Rename remaining columns as forecast hours
        num_fcst_cols = len(dataset.columns)
        if num_fcst_cols == 57:  # Has Analysis column
            dataset.columns = ['Analysis'] + [f'{i} hr fcst' for i in range(3, 169, 3)]
        else:
            dataset.columns = [f'{i} hr fcst' for i in range(3, 169, 3)][:num_fcst_cols]
    
    print(dataset.head())
    print(dataset.columns)
    dateTime = dataset.index.values
    return dataset, dateTime

def getDatesInLocalTimeZone(dateTime):
    global LOCAL_TIMEZONE
    dates = []
    fromZone = pytz.timezone("UTC")
    for i in range(0, len(dateTime)):
        day = pd.to_datetime(dateTime[i]).replace(tzinfo=fromZone)
        day = day.astimezone(LOCAL_TIMEZONE)
        dates.append(day)
    return dates

def writeLocalTimeToFile(dataset, dateTime, outFileName):
    localDates = getDatesInLocalTimeZone(dateTime)
    modifiedDataset = pd.DataFrame(index=dateTime)
    modifiedDataset["local_time"] = localDates
    modifiedDataset.index.name = "datetime"
    for col in dataset.columns.values:
        modifiedDataset[col] = dataset[col]
    print(modifiedDataset.head())
    modifiedDataset.to_csv(outFileName)
    return

def createHourlyTimeCol(dateTime):
    global PREDICTION_WINDOW_HOURS
    global PREDICTION_PERIOD_DAYS
    hourlyDateTime = []
    
    # FIXED: Create proper sliding windows
    # Only use daily forecasts (at 00:00) for sliding windows, not every 6-hour forecast
    print(f"DEBUG: Input dateTime has {len(dateTime)} total forecast starting points")
    
    if len(dateTime) == 0:
        return hourlyDateTime
    
    # Filter to only use daily forecasts (at midnight/00:00)
    # Forecasts come every 6 hours, but we only want one per day for sliding windows
    daily_forecasts = []
    for dt in dateTime:
        # Check if this is a midnight forecast (hour == 0)
        dt_as_pd = pd.to_datetime(dt)
        if dt_as_pd.hour == 0:
            daily_forecasts.append(dt)
    
    print(f"DEBUG: Filtered to {len(daily_forecasts)} daily forecasts (at 00:00)")
    
    # For each daily forecast, create a 168-hour window
    for forecast_idx in range(len(daily_forecasts)):
        start_time = daily_forecasts[forecast_idx]
        # Create 168 hours for this forecast window
        for hour in range(PREDICTION_WINDOW_HOURS):
            hourlyDateTime.append(start_time + np.timedelta64(hour, 'h'))
    
    print(f"DEBUG: Created {len(hourlyDateTime)} hourly timestamps for {len(daily_forecasts)} sliding windows")
    print(f"DEBUG: Each window is {PREDICTION_WINDOW_HOURS} hours, sliding by 24 hours")
    return hourlyDateTime

def createForecastColumns(dataset, modifiedDataset, colName):
    global PREDICTION_PERIOD_DAYS
    global PREDICTION_WINDOW_HOURS
    
    # FIXED: Only use daily forecasts (at 00:00) for sliding windows
    print(f"DEBUG createForecastColumns for '{colName}':")
    print(f"  - Dataset has {len(dataset)} total forecast starting points")
    print(f"  - ModifiedDataset expected to have {len(modifiedDataset)} rows")
    
    # Filter dataset to only use daily forecasts (at midnight/00:00)
    daily_indices = []
    for idx in range(len(dataset)):
        dt_as_pd = pd.to_datetime(dataset.index[idx])
        if dt_as_pd.hour == 0:
            daily_indices.append(idx)
    
    print(f"  - Using {len(daily_indices)} daily forecasts (at 00:00)")
    
    # For each daily forecast starting point (sliding by 24 hours each time)
    for window_idx, forecast_idx in enumerate(daily_indices):
        # Calculate the starting index in modifiedDataset for this window
        window_start_idx = window_idx * PREDICTION_WINDOW_HOURS
        
        # Fill in the 168-hour window for this forecast
        for hour in range(PREDICTION_WINDOW_HOURS):
            output_idx = window_start_idx + hour
            
            if output_idx >= len(modifiedDataset):
                break
            
            # Find the appropriate forecast value for this hour
            # Forecasts come in 3-hour intervals: 3, 6, 9, ..., 168
            # For hour h, use the forecast at the next 3-hour interval
            forecast_hour = ((hour // 3) + 1) * 3
            if forecast_hour > PREDICTION_WINDOW_HOURS:
                forecast_hour = PREDICTION_WINDOW_HOURS
            
            fcst_col_name = str(forecast_hour) + " hr fcst"
            
            if fcst_col_name in dataset.columns:
                modifiedDataset[colName].iloc[output_idx] = dataset[fcst_col_name].iloc[forecast_idx]
            else:
                # If column doesn't exist, use the last available forecast
                print(f"WARNING: Missing column '{fcst_col_name}' for hour {hour}")
    
    # Handle wind speed (make absolute)
    if "wind" in colName:
        modifiedDataset[colName] = np.abs(modifiedDataset[colName].values)
    
    return modifiedDataset

def createAvgOrAccForecastColumns(dataset, modifiedDataset, colName, avgOrAcc):
    global PREDICTION_PERIOD_DAYS
    global PREDICTION_WINDOW_HOURS
    
    timePeriodSuffix = " hr " + avgOrAcc
    
    print(f"DEBUG createAvgOrAccForecastColumns for '{colName}' ({avgOrAcc}):")
    print(f"  - Dataset has {len(dataset)} total forecast starting points")
    print(f"  - ModifiedDataset expected to have {len(modifiedDataset)} rows")
    
    # Filter dataset to only use daily forecasts (at midnight/00:00)
    daily_indices = []
    for idx in range(len(dataset)):
        dt_as_pd = pd.to_datetime(dataset.index[idx])
        if dt_as_pd.hour == 0:
            daily_indices.append(idx)
    
    print(f"  - Using {len(daily_indices)} daily forecasts (at 00:00)")
    
    # FIXED: Only use daily forecasts for sliding window implementation
    for window_idx, forecast_idx in enumerate(daily_indices):
        # Calculate the starting index in modifiedDataset for this window
        window_start_idx = window_idx * PREDICTION_WINDOW_HOURS
        
        # Fill in the 168-hour window for this forecast
        for hour in range(PREDICTION_WINDOW_HOURS):
            output_idx = window_start_idx + hour
            
            if output_idx >= len(modifiedDataset):
                break
            
            # Map hours to the correct column names based on actual data structure
            # The pattern is: 0-3, 0-6, 6-9, 6-12, 12-15, 12-18, 18-21, 18-24, etc.
            timePeriod = ""
            
            if hour < 3:
                timePeriod = "0-3" + timePeriodSuffix
            elif hour < 6:
                timePeriod = "0-6" + timePeriodSuffix
            else:
                # For hours 6 and beyond, find the appropriate interval
                # Pattern repeats every 6 hours: n-(n+3), n-(n+6) where n is multiple of 6
                base_hour = (hour // 6) * 6
                if hour < base_hour + 3:
                    timePeriod = str(base_hour) + "-" + str(base_hour + 3) + timePeriodSuffix
                else:
                    timePeriod = str(base_hour) + "-" + str(base_hour + 6) + timePeriodSuffix
            
            # Get the value for this time period
            if timePeriod in dataset.columns:
                modifiedDataset[colName].iloc[output_idx] = dataset[timePeriod].iloc[forecast_idx]
            else:
                # If column not found, use the 0-6 value as fallback for early hours
                if hour < 6 and "0-6" + timePeriodSuffix in dataset.columns:
                    modifiedDataset[colName].iloc[output_idx] = dataset["0-6" + timePeriodSuffix].iloc[forecast_idx]
    
    return modifiedDataset

def createRTAvgOrAccForecastColumns(dataset, modifiedDataset, colName, avgOrAcc):
    global PREDICTION_PERIOD_DAYS
    global PREDICTION_WINDOW_HOURS
    
    timePeriodSuffix = " hr " + avgOrAcc
    
    print(f"DEBUG createRTAvgOrAccForecastColumns for '{colName}' ({avgOrAcc}):")
    print(f"  - Dataset has {len(dataset)} total forecast starting points")
    
    # Filter dataset to only use daily forecasts (at midnight/00:00)
    daily_indices = []
    for idx in range(len(dataset)):
        dt_as_pd = pd.to_datetime(dataset.index[idx])
        if dt_as_pd.hour == 0:
            daily_indices.append(idx)
    
    print(f"  - Using {len(daily_indices)} daily forecasts (at 00:00)")
    
    # FIXED: Only use daily forecasts for sliding window implementation
    for window_idx, forecast_idx in enumerate(daily_indices):
        # Calculate the starting index in modifiedDataset for this window
        window_start_idx = window_idx * PREDICTION_WINDOW_HOURS
        
        # Fill in the 168-hour window for this forecast
        for hour in range(PREDICTION_WINDOW_HOURS):
            output_idx = window_start_idx + hour
            
            if output_idx >= len(modifiedDataset):
                break
            
            # For real-time, we use cumulative periods: 3 hr, 6 hr, 9 hr, etc.
            # Find the next 3-hour interval that covers this hour
            forecast_hour = ((hour // 3) + 1) * 3
            if forecast_hour > PREDICTION_WINDOW_HOURS:
                forecast_hour = PREDICTION_WINDOW_HOURS
            
            timePeriod = str(forecast_hour) + timePeriodSuffix
            
            # Get the value for this time period
            if timePeriod in dataset.columns:
                modifiedDataset[colName].iloc[output_idx] = dataset[timePeriod].iloc[forecast_idx]
            else:
                # Try using the previous interval's value
                print(f"WARNING: Missing column '{timePeriod}' for hour {hour}")
    
    return modifiedDataset

def calcluateWindSpeed(dataset):
    dataset["forecast_wind_speed"] = [None]*len(dataset)
    for i in range(len(dataset)):
        u = dataset["forecast_u_wind"].iloc[i]
        v = dataset["forecast_v_wind"].iloc[i]
        dataset["forecast_wind_speed"].iloc[i] = round(math.sqrt(u*u * v*v), 5)
    return dataset


def startScript(regionList, fileDir, columnNames, isRealTime, startDate, creationTimeInUTC=None, version=None):
    for region in regionList:
        IN_FILE_NAMES = [region+"_WIND_SPEED.csv", region+"_TEMP.csv", region+"_DPT.csv", 
                         region+"_DSWRF.csv", region+"_APCP.csv"]
        regionFileDir = fileDir
        if (isRealTime is True):
            regionFileDir = fileDir + region + "/weather_data/"
            IN_FILE_NAMES = [region+"_WIND_SPEED_"+str(startDate)+".csv", 
                             region+"_TEMP_"+str(startDate)+".csv", 
                             region+"_DPT_"+str(startDate)+".csv", 
                             region+"_DSWRF_"+str(startDate)+".csv", 
                             region+"_APCP_"+str(startDate)+".csv"]
        dataset, dateTime = readFile(regionFileDir+IN_FILE_NAMES[0])
        # writeLocalTimeToFile(dataset, dateTime, OUT_FILE_NAMES[i])
        hourlyDateTime = createHourlyTimeCol(dateTime)
        modifiedDataset = pd.DataFrame(index=hourlyDateTime, 
                columns=columnNames)
        modifiedDataset.index.name = "datetime"
        for i in range(len(IN_FILE_NAMES)):
            dataset, dateTime = readFile(regionFileDir+IN_FILE_NAMES[i])
            colName = modifiedDataset.columns.values[i]
            modifiedDataset[colName].iloc[0] = 0
            if "dswrf" in colName:
                if (isRealTime is True):
                    modifiedDataset = createRTAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "avg")
                else:
                    modifiedDataset = createAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "avg")
            elif "precipitation" in colName:
                if (isRealTime is True):
                    modifiedDataset = createRTAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "acc")
                else:
                    modifiedDataset = createAvgOrAccForecastColumns(dataset, modifiedDataset, colName, "acc")
            else:
                modifiedDataset = createForecastColumns(dataset, modifiedDataset, colName)
            modifiedDataset[colName].iloc[0] = modifiedDataset[colName].iloc[1]
            
        outFileName = regionFileDir+region+"_aggregated_weather_data_2023.csv"
        if (startDate is not None):
            outFileName = regionFileDir+"/../"+region+"_weather_forecast_"+str(startDate)+".csv"
        if (creationTimeInUTC is not None and version is not None):
            modifiedDataset.insert(0, "creation_time (UTC)", creationTimeInUTC)
            modifiedDataset.insert(1, "version", version)
        modifiedDataset.to_csv(outFileName)
    return

def aggregateWeatherDataAcrossYears(inFileDir, outFileDir, years):
    
    dataset = [None]*len(years)
    weatherVariables = ["apcp", "dpt", "dswrf", "temp", "wind_speed"]

    for region in ISO_LIST:
        for wv in weatherVariables:
            for i in range(len(years)):
                
                inFileName = inFileDir+str(years[i])+"/"+region+"_"+wv.upper()+".csv"
                outFileName = outFileDir+region+"_"+wv.upper()+".csv"
                print(inFileName)  
                if (not os.path.exists(inFileName)):
                    print(inFileName, "does not exist")
                    continue                
                dataset[i] = pd.read_csv(inFileName, header=0)
            for i in range(1, len(years)):
                dataset[0] = pd.concat([dataset[0], dataset[i]])
            modifiedDataset = pd.DataFrame(dataset[0])
            modifiedDataset.set_index("datetime")
            
            # print(modifiedDataset.head())
            modifiedDataset.to_csv(outFileName)

def moveForecastsAheadByADay(region, inFileDir, outFileDir):
    print(region)
    inFileName = inFileDir+region+"_aggregated_weather_data_2023.csv"
    outFileName = outFileDir+region+"_weather_forecast_2023.csv"
    dataset = pd.read_csv(inFileName, header=0, index_col=["datetime"])
    # Changed from 96 to 168 hours for proper 7-day sliding window
    modifiedDataset = np.array(dataset.iloc[168:, :])
    zeroVal = np.zeros((168, len(dataset.columns)))
    modifiedDataset = np.vstack((modifiedDataset, zeroVal))

    modifiedDataset = pd.DataFrame(modifiedDataset, columns=dataset.columns.values, index=dataset.index)
    modifiedDataset.to_csv(outFileName)
    return

if __name__ == "__main__":
    print("Cleaning up weather data by CarbonCast regions...")
    print("Usage: python3 cleanWeatherData <continent> <infileDir>")
    print("Continent: US/EU") # curently, only US is supported
    if (len(sys.argv) < 3):
        print("Wrong no. of arguments!")
        exit(0)

    continent = sys.argv[1]
    inFileDir = sys.argv[2]
    # startYear = 2023
    # endYear = 2023
    ISO_LIST = US_REGION_LIST
    if (continent == "EU"):
        ISO_LIST = EU_REGION_LIST


    startScript(ISO_LIST, inFileDir, COLUMN_NAME, isRealTime=False, startDate=None, creationTimeInUTC=None, version=None)

    # years = [2019, 2020, 2021, 2022]
    # inFileDir = "EU_"
    # outFileDir = "./EU_total_aggregated_weather_data/"
    # aggregateWeatherDataAcrossYears(inFileDir, outFileDir, years)

    for region in ISO_LIST:
        moveForecastsAheadByADay(region, inFileDir=inFileDir, outFileDir=inFileDir)