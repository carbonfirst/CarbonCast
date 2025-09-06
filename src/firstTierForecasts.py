'''
File to generate source production forecasts for different sources across regions.
'''

import csv
from datetime import datetime as dt
from datetime import timezone as tz

import numpy as np
import pandas as pd
import pytz as pytz
from keras.layers import Dense, Flatten
from keras.models import Sequential
import tensorflow as tf
from tensorflow import keras
from keras.callbacks import EarlyStopping
from keras.callbacks import ModelCheckpoint
from keras.models import load_model

import common
import sys
import json5 as json


############################# MACRO START #######################################
BUFFER = -1
DAY_INTERVAL = 1
MONTH_INTERVAL = 1
DEPENDENT_VARIABLE_COL = 0

TRAINING_WINDOW_HOURS = None
PREDICTION_WINDOW_HOURS = None
MODEL_SLIDING_WINDOW_LEN = None
BUFFER_HOURS = None
WEATHER_STRIDE_HOURS = None  # configurable cadence between successive weather forecast issuance blocks

############################# MACRO END #########################################

def runFirstTier(configFileName):
    global TRAINING_WINDOW_HOURS
    global PREDICTION_WINDOW_HOURS
    global MODEL_SLIDING_WINDOW_LEN
    global BUFFER_HOURS
    global WEATHER_STRIDE_HOURS

    firstTierConfig = {}

    with open(configFileName, "r") as configFile:
        firstTierConfig = json.load(configFile)
        # print(configurationData)

    NUMBER_OF_EXPERIMENTS = firstTierConfig["NUMBER_OF_EXPERIMENTS_PER_REGION"]
    TRAINING_WINDOW_HOURS = firstTierConfig["TRAINING_WINDOW_HOURS"]
    PREDICTION_WINDOW_HOURS = firstTierConfig["PREDICTION_WINDOW_HOURS"]
    MODEL_SLIDING_WINDOW_LEN = firstTierConfig["MODEL_SLIDING_WINDOW_LEN"]
    BUFFER_HOURS = PREDICTION_WINDOW_HOURS - 24
    # Optional stride parameter (default: horizon -> legacy behavior). When set < horizon (e.g. 24),
    # weather forecast blocks are assumed to be issued every WEATHER_STRIDE_HOURS with length PREDICTION_WINDOW_HOURS.
    WEATHER_STRIDE_HOURS = firstTierConfig.get("WEATHER_STRIDE_HOURS", PREDICTION_WINDOW_HOURS)

    regionList = firstTierConfig["REGION"]
    for region in regionList:
        print("CarbonCast: ANN model for region:", region)
        regionConfig = firstTierConfig[region]
        sourceList = regionConfig["SOURCES"]
        sourceColList = regionConfig["SOURCE_COL"]
        trainTestPeriodConfig = firstTierConfig["TRAIN_TEST_PERIOD"]
        weatherForecastInFileName = regionConfig["WEATHER_FORECAST_IN_FILE_NAME"]
        SAVED_MODEL_LOCATION = firstTierConfig["SAVED_MODEL_LOCATION"]+region+"/"
        aggregatedForecastFileName = regionConfig["AGGREGATED_FORECAST_OUT_FILE_NAME"]


        sourceIdx = 0
        outFileNamePrefix = regionConfig["OUT_FILE_NAME_PREFIX"]
        for source in sourceList:
            inFileName = regionConfig["IN_FILE_NAME_PREFIX"] + "source_prod" + firstTierConfig["IN_FILE_NAME_SUFFIX"]
            sourceCol = sourceColList[sourceIdx]
            partialSourceProductionForecastAvailable = regionConfig["PARTIAL_FORECAST_AVAILABILITY_LIST"][sourceIdx]
            partialForecastHours =  regionConfig["PARTIAL_FORECAST_HOURS"]
            print(inFileName)
            print(weatherForecastInFileName)
            isRenewableSource = False
            numFeatures = firstTierConfig["NUM_FEATURES"]
            numWeatherFeatures = 0
            if (source == "SOLAR" or source == "WIND" or source == "HYDRO"):
                isRenewableSource = True
            if (isRenewableSource == True):
                numWeatherFeatures = firstTierConfig["NUM_WEATHER_FEATURES"]

            for exptNum in range(NUMBER_OF_EXPERIMENTS):
                outFileName = outFileNamePrefix + "_" + source.lower() + "_iter" + str(exptNum) + ".csv"
                periodRMSE, periodMAPE = [], []
                
                periodIdx = 0
                for period in trainTestPeriodConfig:
                    print(trainTestPeriodConfig[period])
                    datasetLimiter = trainTestPeriodConfig[period]["DATASET_LIMITER"]
                    numTestDays = trainTestPeriodConfig[period]["NUM_TEST_DAYS"]
                    numValDays = firstTierConfig["NUM_VAL_DAYS"]
                    # Dynamically compute number of weather rows required.
                    # If stride == horizon (legacy), this collapses to num_days * horizon.
                    # General formula for flattened concatenated forecast blocks with overlap:
                    #   total_rows = horizon + (num_blocks-1)*stride, where num_blocks ≈ num_days (one issuance per day)
                    num_days = datasetLimiter // 24
                    num_blocks = num_days  # one issuance per day assumption consistent with previous logic
                    weatherDatasetLimiter = 0
                    if num_blocks > 0:
                        weatherDatasetLimiter = PREDICTION_WINDOW_HOURS + (num_blocks - 1) * WEATHER_STRIDE_HOURS
                    # Cap to available length implicitly when slicing later
                    print(numTestDays)

                    print("Initializing...")
                    dataset, dateTime, bufferPeriod, bufferDates, weatherDataset = initialize(
                                inFileName, weatherForecastInFileName, sourceCol,
                                datasetLimiter, weatherDatasetLimiter)
                    # bufferPeriod is for the last test date, if prediction period is beyond 24 hours
                    print("***** Initialization done *****")

                    # split into train and test
                    print("Spliting dataset into train/test...")
                    trainData, valData, testData, fullTrainData = common.splitDataset(dataset.values, numTestDays, 
                                                            numValDays)
                    trainDates = dateTime[: -(numTestDays*24)]
                    fullTrainDates = np.copy(trainDates)
                    trainDates, validationDates = trainDates[: -(numValDays*24)], trainDates[-(numValDays*24):]
                    testDates = dateTime[-(numTestDays*24):]
                    bufferPeriod = bufferPeriod.values
                    trainData = trainData[:, sourceCol: sourceCol+numFeatures]
                    valData = valData[:, sourceCol: sourceCol+numFeatures]
                    testData = testData[:, sourceCol: sourceCol+numFeatures]
                    partialSourceProductionForecast = None
                        
                    bufferPeriod = bufferPeriod[:, sourceCol: sourceCol+numFeatures]
                    if(len(bufferDates)>0):
                        testDates = np.append(testDates, bufferDates)
                        testData = np.vstack((testData, bufferPeriod))

                    print("TrainData shape: ", trainData.shape) # (days x hour) x features
                    print("ValData shape: ", valData.shape) # (days x hour) x features
                    print("TestData shape: ", testData.shape) # (days x hour) x features

                    wTrainData, wValData, wTestData, wFullTrainData = None, None, None, None
                    if (isRenewableSource):
                        wTrainData, wValData, wTestData, wFullTrainData = common.splitWeatherDataset(
                                weatherDataset.values, numTestDays, numValDays, PREDICTION_WINDOW_HOURS)
                        print("WeatherTrainData shape: ", wTrainData.shape) # (days x hour) x features
                        print("WeatherValData shape: ", wValData.shape) # (days x hour) x features
                        print("WeatherTestData shape: ", wTestData.shape) # (days x hour) x features

                    print("***** Dataset split done *****")

                    trainData = fillMissingData(trainData)
                    valData = fillMissingData(valData)
                    testData = fillMissingData(testData)
                    featureList = dataset.columns.values
                    featureList = featureList[sourceCol:sourceCol+numFeatures].tolist()

                    print("Scaling data...")
                    trainData, valData, testData, ftMin, ftMax = common.scaleDataset(trainData, valData, testData)
                    print(trainData.shape, valData.shape, testData.shape)

                    wFtMin = []
                    wFtMax = []
                    if(isRenewableSource):
                        wTrainData = fillMissingData(wTrainData)
                        wValData = fillMissingData(wValData)
                        wTestData = fillMissingData(wTestData)
                        featureList.extend(weatherDataset.columns.values)
                        wTrainData, wValData, wTestData, wFtMin, wFtMax = common.scaleDataset(wTrainData, wValData, wTestData)
                        print(wTrainData.shape, wValData.shape, wTestData.shape)

                    print("Features: ", featureList)
                        
                    if (partialSourceProductionForecastAvailable):
                        print("Partial forecast available for source: ", source)
                        partialSourceProductionForecast = dataset["avg_"+source.lower()+"_production_forecast"].iloc[-numTestDays*24:].values
                        partialSourceProductionForecast = common.scaleColumn(partialSourceProductionForecast, 
                                ftMin[DEPENDENT_VARIABLE_COL], ftMax[DEPENDENT_VARIABLE_COL])
                        # print(partialSourceProductionForecast, ftMax[DEPENDENT_VARIABLE_COL], ftMin[DEPENDENT_VARIABLE_COL])
                    print("***** Data scaling done *****")


                    if (periodIdx == len(trainTestPeriodConfig)-1):
                        print("Saving min & max values for each column in file...")
                        with open(SAVED_MODEL_LOCATION+region+"_"+source+"_min_max_values.txt", "w") as f:
                            f.writelines(str(ftMin))
                            f.write("\n")
                            f.writelines(str(ftMax))
                            f.write("\n")
                            if (isRenewableSource):
                                f.writelines(str(wFtMin))
                                f.write("\n")
                                f.writelines(str(wFtMax))
                                f.write("\n")
                        print("Min-max values saved")

                    ######################## START #####################                    
                    print("Iteration: ", exptNum)
                    bestModel = trainingandValidationPhase(trainData, wTrainData, valData, wValData, 
                                                           firstTierConfig, SAVED_MODEL_LOCATION, region, source)

                    history = valData[-TRAINING_WINDOW_HOURS:, :]
                    weatherData = None
                    if (isRenewableSource):
                        weatherData = wValData[-PREDICTION_WINDOW_HOURS:, :]
                        print("weatherData shape:", weatherData.shape)
                    history = history.tolist()

                    bestRMSE, bestMAPE = [], []
                    predictedData = getDayAheadForecasts(bestModel, history, testData, 
                                        numFeatures+numWeatherFeatures, wTestData, weatherData, partialSourceProductionForecast)
                    print("***** Forecast done *****")
                    
                    unscaledTestData, unscaledPredictedData, formattedTestDates, rmseScore, mapeScore = getUnscaledForecastsAndForecastAccuracy(
                                                                        testData, testDates, predictedData, 
                                                                        ftMin, ftMax)
                    
                    print("[BESTMODEL] Overall RMSE score: ", rmseScore)
                    print("[BESTMODEL] Overall MAPE score: ", mapeScore)
                    # print(scores)
                    bestRMSE.append(rmseScore)
                    bestMAPE.append(mapeScore)

                    
                    print("[BEST] Average RMSE after ", NUMBER_OF_EXPERIMENTS, " expts: ", np.mean(bestRMSE))
                    print("[BEST] Average MAPE after ", NUMBER_OF_EXPERIMENTS, " expts: ", np.mean(bestMAPE))
                    print(bestRMSE)
                    print(bestMAPE)
                    periodRMSE.append(bestRMSE)
                    periodMAPE.append(bestMAPE)

                    writeSourceProductionForecastsToFile(formattedTestDates, unscaledTestData, unscaledPredictedData,
                                                        periodIdx, source, outFileName)
                    periodIdx +=1
                    ######################## END #####################

                ###
                # common.dumpRandomDataToFile("../data/"+region+"/fuel_forecast/"+region+
                #         "_RMSE_iter"+str(exptNum)+source.lower()+".txt", str(periodRMSE), "w")
                # common.dumpRandomDataToFile("../data/"+region+"/fuel_forecast/"+region+
                #         "_MAPE_iter"+str(exptNum)+source.lower()+".txt", str(periodMAPE), "w")
                ###

                print("RMSE: ", periodRMSE)
                print("MAPE: ", periodMAPE)
            sourceIdx += 1

            print("####################", region, source, " done ####################\n\n")
        print("Source production forecast for region: ", region, " done.")
        aggregateDataAndGenerateForecastFile(firstTierConfig, sourceList, weatherForecastInFileName,
                                             outFileNamePrefix, aggregatedForecastFileName, 
                                             isRealTime=False, startDate=None)
        issuanceOut = regionConfig.get("AGGREGATED_FORECAST_OUT_FILE_NAME_ISSUANCE")
        if issuanceOut:
            aggregateDataAndGenerateForecastIssuanceFile(firstTierConfig, sourceList, weatherForecastInFileName,
                                                         outFileNamePrefix, issuanceOut,
                                                         isRealTime=False, startDate=None)
    return

def runFirstTierInRealTime(configFileName, regionList, startDate, electricityDataDate, solWindFcstData,
                           realTimeFileDir, realTimeWeatherFileDir, creationTimeInUTC, version):
    global TRAINING_WINDOW_HOURS
    global PREDICTION_WINDOW_HOURS
    global MODEL_SLIDING_WINDOW_LEN

    firstTierConfig = {}

    with open(configFileName, "r") as configFile:
        firstTierConfig = json.load(configFile)
        # print(configurationData)

    TRAINING_WINDOW_HOURS = firstTierConfig["TRAINING_WINDOW_HOURS"]
    PREDICTION_WINDOW_HOURS = firstTierConfig["PREDICTION_WINDOW_HOURS"]
    MODEL_SLIDING_WINDOW_LEN = firstTierConfig["MODEL_SLIDING_WINDOW_LEN"]

    aggregatedForecastFileNames = {}

    for region in regionList:
        print("CarbonCast: ANN model for region:", region)
        regionConfig = firstTierConfig[region]
        sourceList = regionConfig["SOURCES"]
        sourceColList = regionConfig["SOURCE_COL"]
        weatherForecastInFileName = realTimeWeatherFileDir+region+"/"+region+"_weather_forecast_"+str(startDate)+".csv"
        SAVED_MODEL_LOCATION = firstTierConfig["SAVED_MODEL_LOCATION"]+region+"/"
        aggregatedForecastFileNames[region] = realTimeFileDir+region+"/"+region+"_96hr_forecasts_"+str(startDate)+".csv"
        partialSourceProductionForecast = None
        sourceIdx = 0
        inFileName = realTimeFileDir+region+"/"+region+"_"+str(electricityDataDate)+".csv"
        outFileNamePrefix = realTimeFileDir+region+"/fuel_forecast/"+region+"_ANN"
        for source in sourceList:
            sourceCol = sourceColList[sourceIdx]+2 # +2 because we have now added creation time & version for real-time files
            partialSourceProductionForecastAvailable = True if solWindFcstData is not None else False # partial forecasts only for SOLAR and WIND
            print(inFileName)
            print(weatherForecastInFileName)
            isRenewableSource = False
            numFeatures = firstTierConfig["NUM_FEATURES"]
            numWeatherFeatures = 0
            if (source == "SOLAR" or source == "WIND" or source == "HYDRO"):
                isRenewableSource = True
            if (isRenewableSource == True):
                numWeatherFeatures = firstTierConfig["NUM_WEATHER_FEATURES"]
                numFeatures += numWeatherFeatures

            print("No. of features = ", numFeatures)

            outFileName = outFileNamePrefix + "_" + source.lower() + "_" + str(startDate) + ".csv"
            

            print("Initializing...")
            dataset, testDates, weatherDataset = initializeInRealTime(inFileName, weatherForecastInFileName, 
                                                                    sourceCol, isRenewableSource)
            # bufferPeriod is for the last test date, if prediction period is beyond 24 hours
            print("***** Initialization done *****")

            testData = np.array(dataset.values[:, sourceCol:sourceCol+1])
            testData = fillMissingData(testData)
            wTestData = np.array(weatherDataset.values)
            wTestData = fillMissingData(wTestData)
            # print(testData.shape, wTestData.shape)
            

            print("Scaling data...")
            minMaxFeatureFileName = SAVED_MODEL_LOCATION+region+"_"+source+"_min_max_values.txt"
            ftMin, ftMax, wFtMin, wFtMax = common.getMinMaxFeatureValues(minMaxFeatureFileName, 
                                                                         areForecastsFeatures=isRenewableSource)
            testData = common.scaleTestDataWithTrainingValues(testData, ftMin, ftMax)
            wTestData= common.scaleTestDataWithTrainingValues(wTestData, wFtMin, wFtMax)
            if (partialSourceProductionForecastAvailable and (source == "SOLAR" or source == "WIND")):
                print("Partial forecast available for source: ", source)
                dataset["avg_"+source.lower()+"_production_forecast"] = solWindFcstData["avg_"+source.lower()+"_production_forecast"].values
                partialSourceProductionForecast = dataset["avg_"+source.lower()+"_production_forecast"].iloc[-24:].values
                partialSourceProductionForecast = common.scaleColumn(partialSourceProductionForecast, 
                        ftMin[DEPENDENT_VARIABLE_COL], ftMax[DEPENDENT_VARIABLE_COL])
                # print(partialSourceProductionForecast, ftMax[DEPENDENT_VARIABLE_COL], ftMin[DEPENDENT_VARIABLE_COL])
            print("***** Data scaling done *****")

            ######################## START #####################                    
            savedModelName = SAVED_MODEL_LOCATION+"/"+region+"_"+source.upper()+"_best_model_ann.h5"
            model = load_model(savedModelName)

            history = testData[-TRAINING_WINDOW_HOURS:, :]
            weatherData = wTestData[-PREDICTION_WINDOW_HOURS:, :]
            history = history.tolist()
            predictedData = getSourceProductionForecastsInRealTime(model, history, testData, numFeatures, wTestData, 
                        weatherData, partialSourceProductionForecast, isRenewableSource)
            print("***** Forecast done *****")

            predictedData = predictedData.astype(np.float64)
            # print("PredictedData shape: ", predictedData.shape)
            predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
            # print("predicted.shape: ", predicted.shape)
            unscaledPredictedData = common.inverseDataScaling(predicted, 
                                                              ftMax[DEPENDENT_VARIABLE_COL], 
                                                              ftMin[DEPENDENT_VARIABLE_COL])
            
            writeRealTimeSourceProductionForecastsToFile(testDates, unscaledPredictedData,
                                                source, outFileName, creationTimeInUTC, version)
            
            ######################## END #####################
            sourceIdx += 1

            print("####################", region, source, " done ####################\n\n")
        print("Source production forecast for region: ", region, " done.")
        aggregateDataAndGenerateForecastFile(firstTierConfig, sourceList, weatherForecastInFileName,
                                             outFileNamePrefix, aggregatedForecastFileNames[region], 
                                             isRealTime=True, startDate=startDate)
    return aggregatedForecastFileNames

def aggregateDataAndGenerateForecastFile(firstTierConfig, sourceList, weatherForecastFile,
                                         sourceForecastFileNamePrefix, aggregatedForecastFileName,
                                         isRealTime = False, startDate=None):
    # Offline (training/evaluation) case: retain overlapping forecast rows (original 96hr-style behavior).
    weatherDatasetStartRow = firstTierConfig["ROW_START_FOR_2020"]
    weatherDatasetEndRow = firstTierConfig["ROW_END_FOR_2022"]
    sourceForecastDatasetEndRow = firstTierConfig["SOURCE_FORECAST_ROW_END_FOR_2022"]
    horizon = firstTierConfig["PREDICTION_WINDOW_HOURS"]

    # Read weather
    weatherDataset = pd.read_csv(weatherForecastFile, header=0, parse_dates=["datetime"], index_col=["datetime"])    
    weatherDataset.index = pd.to_datetime(weatherDataset.index).tz_localize(None)
    # Preserve original order (do not sort) to keep issuance sequence intact.
    if (isRealTime is False):
        weatherDataset = weatherDataset[weatherDatasetStartRow:weatherDatasetEndRow]

    if isRealTime:
        # Preserve legacy real-time aggregation (unique hourly timeline)
        modifiedDataset = weatherDataset.copy()
        for source in sourceList:
            sourceForecastFileName = sourceForecastFileNamePrefix + "_" + source.lower() + (f"_{startDate}" if startDate is not None else "") + (".csv" if startDate is not None else "_iter0.csv")
            srcDF = pd.read_csv(sourceForecastFileName, header=0, parse_dates=["datetime"], index_col=["datetime"])
            srcDF.index = pd.to_datetime(srcDF.index).tz_localize(None)
            srcDF = srcDF[~srcDF.index.duplicated(keep="first")]
            srcDF.sort_index(inplace=True)
            fc_col = "avg_" + source.lower() + "_production_forecast"
            modifiedDataset = modifiedDataset.join(srcDF[[fc_col]], how="inner")
        print("Aggregated (real-time) rows, cols:", modifiedDataset.shape)
        modifiedDataset.to_csv(aggregatedForecastFileName)
        return

    # Overlapping stacked output path (always used offline)
    print("Producing overlapping stacked DA output (horizon=", horizon, ") ...")
    # Build a master timeline from the first source forecast file preserving its row order (with duplicates)
    master_timeline = None
    source_data = {}
    for idx, source in enumerate(sourceList):
        sourceForecastFileName = sourceForecastFileNamePrefix + "_" + source.lower() + "_iter0.csv"
        srcDF = pd.read_csv(sourceForecastFileName, header=0, parse_dates=["datetime"], dtype={})
        if sourceForecastDatasetEndRow is not None:
            srcDF = srcDF[:sourceForecastDatasetEndRow]
        if master_timeline is None:
            master_timeline = srcDF['datetime'].tolist()
        else:
            # Basic validation: length & per-row datetime equality (best effort)
            if len(srcDF['datetime']) != len(master_timeline):
                print(f"[WARN] Source {source} forecast length {len(srcDF)} doesn't match master timeline {len(master_timeline)}; will align by position up to min length.")
            # Could add deeper validation if needed.
        fc_col = "avg_" + source.lower() + "_production_forecast"
        if fc_col not in srcDF.columns:
            print(f"[WARN] Missing forecast column {fc_col} in {sourceForecastFileName}; filling NaNs")
            source_data[fc_col] = pd.Series([np.nan]*len(srcDF))
        else:
            source_data[fc_col] = srcDF[fc_col].reset_index(drop=True)
    if master_timeline is None:
        print("[ERROR] No source forecast files found; abort overlapping aggregation.")
        return
    master_len = min(len(v) for v in source_data.values()) if source_data else 0
    master_timeline = master_timeline[:master_len]
    # Prepare weather lookup (first occurrence per timestamp)
    weatherCols = [c for c in weatherDataset.columns if c.startswith('forecast_avg_')]
    if not weatherCols:
        weatherCols = list(weatherDataset.columns)
    weather_unique = weatherDataset[weatherCols].copy()
    if weather_unique.index.has_duplicates:
        weather_unique = weather_unique.groupby(level=0).first()
    # Map weather for each timeline datetime
    weather_rows = []
    missing_weather = 0
    for ts in master_timeline:
        row = weather_unique.loc[ts] if ts in weather_unique.index else None
        if row is None or (isinstance(row, pd.Series) and row.isna().all()):
            missing_weather += 1
            weather_rows.append([np.nan]*len(weatherCols))
        else:
            if isinstance(row, pd.DataFrame):  # unlikely after groupby.first
                row = row.iloc[0]
            weather_rows.append(row.values.tolist())
    if missing_weather:
        print(f"[WARN] {missing_weather} timestamps missing weather; filled NaNs")
    import pandas as _pd
    assembled = _pd.DataFrame(weather_rows, columns=weatherCols)
    # Attach forecast columns
    for col, series in source_data.items():
        if len(series) > master_len:
            series = series.iloc[:master_len]
        assembled[col] = series.values
    assembled.insert(0, 'datetime', master_timeline)
    # Forward-fill any remaining weather NaNs to mimic original behavior of having filled values
    weather_only_cols = [c for c in assembled.columns if c.startswith('forecast_avg_')]
    if weather_only_cols:
        before_na = assembled[weather_only_cols].isna().sum().sum()
        if before_na:
            assembled[weather_only_cols] = assembled[weather_only_cols].fillna(method='ffill').fillna(method='bfill')
            after_na = assembled[weather_only_cols].isna().sum().sum()
            if after_na == 0:
                print(f"[INFO] Filled {before_na} weather NaN cells via ffill/bfill")
            else:
                print(f"[WARN] {after_na} weather NaN cells remain after fill attempts")
    print("Aggregated (overlapping) rows, cols:", assembled.shape)
    assembled.to_csv(aggregatedForecastFileName, index=False)
    return

def aggregateDataAndGenerateForecastIssuanceFile(firstTierConfig, sourceList, weatherForecastFile,
                                         sourceForecastFileNamePrefix, aggregatedForecastIssuanceFileName,
                                         isRealTime = False, startDate=None):
    """Create issuance-long file preserving overlapping 168h (or configured horizon) blocks.
    Each source forecast CSV already stores flattened daily walk-forward predictions. Here we
    vertically stack them without inner-joining on datetime (which collapses duplicates).
    Assumes each per-source forecast file keeps chronological order matching weather file.
    """
    horizon = firstTierConfig["PREDICTION_WINDOW_HOURS"]
    frames = []
    for source in sourceList:
        sourceForecastFileName = sourceForecastFileNamePrefix + "_" + source.lower() + "_iter0.csv"
        if (isRealTime is True and startDate is not None):
            sourceForecastFileName = sourceForecastFileNamePrefix + "_" + source.lower() + "_" + str(startDate) + ".csv"
        srcDF = pd.read_csv(sourceForecastFileName, header=0, parse_dates=["datetime"], index_col=["datetime"])
        srcDF.index = pd.to_datetime(srcDF.index).tz_localize(None)
        # Keep only forecast column
        fc_col = "avg_" + source.lower() + "_production_forecast"
        srcDF = srcDF[[fc_col]].copy()
        frames.append(srcDF)
    # Concatenate on columns to produce wide layout of sources, preserving duplicate datetimes
    issuanceDF = pd.concat(frames, axis=1)
    issuanceDF.sort_index(kind="stable", inplace=True)
    print("Issuance-long rows, cols:", issuanceDF.shape)
    issuanceDF.to_csv(aggregatedForecastIssuanceFileName)
    return

def initialize(inFileName, weatherForecastInFileName, startCol, datasetLimiter,
                weatherDatasetLimiter):

    global BUFFER_HOURS
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])

    # print(dataset.head())
    # print(dataset.columns)
    dateTime = dataset.index.values

    # weatherDataset = pd.read_csv(weatherForecastInFileName, header=0, infer_datetime_format=True, 
    #                         parse_dates=['UTC time'], index_col=['UTC time'])
    weatherDataset = pd.read_csv(weatherForecastInFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['datetime'], index_col=['datetime'])
    # print(weatherDataset.head())
    
    print("\nAdding features related to date & time...")
    modifiedDataset = common.addDateTimeFeatures(dataset, dateTime, startCol)
    dataset = modifiedDataset
    print("Features related to date & time added")

    bufferPeriod = dataset[datasetLimiter:datasetLimiter+BUFFER_HOURS]
    dataset = dataset[:datasetLimiter]
    bufferDates = dateTime[datasetLimiter:datasetLimiter+BUFFER_HOURS]
    dateTime = dateTime[:datasetLimiter]

    weatherDataset = weatherDataset[:weatherDatasetLimiter]
    
    for i in range(startCol, len(dataset.columns.values)):
        col = dataset.columns.values[i]
        dataset[col] = dataset[col].astype(np.float64)
        # print(col, dataset[col].dtype)

    # print("Getting contribution of each energy source...")
    # contribution = getAvgContributionBySource(dataset)
    # print(contribution)

    return dataset, dateTime, bufferPeriod, bufferDates, weatherDataset

def initializeInRealTime(inFileName, weatherForecastInFileName, startCol, isRenewableSource):
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])

    weatherDataset = pd.read_csv(weatherForecastInFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['datetime'], index_col=['datetime'])
    weatherDateTime = weatherDataset.index.values
    # Adding in weather dataset, as we need for 96 hours
    weatherDataset = weatherDataset.iloc[:, 2:] # this is because we have now added creation time & version
    modifiedWeatherDataset = common.addDateTimeFeatures(weatherDataset, weatherDateTime, -1)
    if (isRenewableSource is True):
        weatherDataset = modifiedWeatherDataset
    else:
        weatherDataset = modifiedWeatherDataset.iloc[:, :5]
    print("Features related to date & time added")
    
    for i in range(startCol, len(dataset.columns.values)):
        col = dataset.columns.values[i]
        dataset[col] = dataset[col].astype(np.float64)

    return dataset, weatherDateTime, weatherDataset

def fillMissingData(data): # If some data is missing (NaN), use the same value as that of the previous row
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if(np.isnan(data[i, j])):
                data[i, j] = data[i-1, j]
    return data

def trainingandValidationPhase(trainData, wTrainData, valData, wValData, 
                               firstTierConfig, savedModelLocation, region, source):
    global TRAINING_WINDOW_HOURS
    print("\nManipulating training data...")
    X, y = manipulateTrainingDataShape(trainData, TRAINING_WINDOW_HOURS, wTrainData)
    print("\nManipulating validation data...")
    # Next line actually labels validation data
    valX, valY = manipulateTrainingDataShape(valData, TRAINING_WINDOW_HOURS, wValData)
                    
    print("***** Training and validation data manipulation done *****")
    print("X.shape, y.shape: ", X.shape, y.shape)
    hyperParams = getANNHyperParams(firstTierConfig)                
    print("\n[BESTMODEL] Starting training...")
    bestTrainedModel = trainANN(X, y, valX, valY, hyperParams, savedModelLocation, region, source)
    print("***** Training done *****")
    return bestTrainedModel

# convert training data into inputs and outputs (labels)
def manipulateTrainingDataShape(data, labelWindowHours, weatherData = None):
    global TRAINING_WINDOW_HOURS
    global PREDICTION_WINDOW_HOURS

    print("Data shape: ", data.shape)
    X, y, weatherX = list(), list(), list()
    weatherIdx = 0
    hourIdx = 0
    # step over the entire history one time step at a time
    for i in range(len(data)-(TRAINING_WINDOW_HOURS+labelWindowHours)+1):
        # Bounds check BEFORE processing to ensure exact alignment
        if(weatherData is not None):
            if weatherIdx + TRAINING_WINDOW_HOURS > len(weatherData):
                # Stop processing when weather data runs out
                break
                
        # define the end of the input sequence
        trainWindow = i + TRAINING_WINDOW_HOURS
        labelWindow = trainWindow + labelWindowHours
        xInput = data[i:trainWindow, :]
        X.append(xInput)
        if(weatherData is not None):
            weatherX.append(weatherData[weatherIdx:weatherIdx+TRAINING_WINDOW_HOURS])
            weatherIdx += 1
            hourIdx += 1
            if(hourIdx == 24):
                hourIdx = 0
                weatherIdx += (PREDICTION_WINDOW_HOURS-24)
        y.append(data[trainWindow:labelWindow, DEPENDENT_VARIABLE_COL])
    X = np.array(X, dtype=np.float64)
    y = np.array(y, dtype=np.float64)
    if(weatherData is not None):
        weatherX = np.array(weatherX, dtype=np.float64)
        X = np.append(X, weatherX, axis=2)
    return X, y

def manipulateTestDataShape(data, isDates=False):
    global MODEL_SLIDING_WINDOW_LEN
    global PREDICTION_WINDOW_HOURS
    X = list()
    # step over the entire history one time step at a time
    for i in range(0, len(data)-(PREDICTION_WINDOW_HOURS)+1, MODEL_SLIDING_WINDOW_LEN):
        # define the end of the input sequence
        predictionWindow = i + PREDICTION_WINDOW_HOURS
        X.append(data[i:predictionWindow])
    if (isDates is False):
        X = np.array(X, dtype=np.float64)
    else:
        X = np.array(X)
    return X


def trainANN(trainX, trainY, valX, valY, hyperParams, savedModelLocation, region, source):
    n_timesteps, n_features, n_outputs = trainX.shape[1], trainX.shape[2], trainY.shape[1]
    epochs = hyperParams["epoch"]
    batchSize = hyperParams["batchsize"]
    lossFunc = hyperParams["loss"]
    actvFunc = hyperParams["actv"]
    hiddenDims = hyperParams["hidden"]
    learningRates = hyperParams["lr"]
    model = Sequential()
    model.add(Flatten())
    model.add(Dense(hiddenDims[0], input_shape=(n_timesteps, n_features), activation=actvFunc)) # 50
    model.add(Dense(hiddenDims[1], activation=actvFunc)) # 34
    model.add(Dense(n_outputs))
    
    opt = tf.keras.optimizers.Adam(learning_rate = learningRates)
    model.compile(loss=lossFunc, optimizer=opt,
                    metrics=["mean_absolute_error"])
    es = EarlyStopping(monitor="val_loss", mode="min", verbose=1, patience=10)
    mc = ModelCheckpoint(savedModelLocation+region+"_"+source+"_best_model_ann.h5", monitor="val_loss", mode="min", verbose=1, save_best_only=True)
    # fit network
    # hist = model.fit(trainX, trainY, epochs=epochs, batch_size=bSize, verbose=verbose)
    hist = model.fit(trainX, trainY, epochs=epochs, batch_size=batchSize[0], verbose=2,
                        validation_data=(valX, valY), callbacks=[es, mc])
    model = load_model(savedModelLocation+region+"_"+source+"_best_model_ann.h5")
    common.showModelSummary(hist, model)
    print("Number of features used in training: ", n_features)
    return model

def getDayAheadForecasts(model, history, testData, 
                            numFeatures,
                            wTestData = None, weatherData = None, 
                            partialSourceProductionForecast = None):
    global TRAINING_WINDOW_HOURS
    global MODEL_SLIDING_WINDOW_LEN
    global PREDICTION_WINDOW_HOURS
    global BUFFER_HOURS
    # walk-forward validation over each day
    print("Testing (day ahead forecasts)...")
    predictions = list()
    weatherIdx = 0
    for i in range(0, ((len(testData)//24)-(BUFFER_HOURS//24))):
        dayAheadPredictions = list()
        # predict n days, 1 day at a time
        tempHistory = history.copy()
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
        for j in range(0, PREDICTION_WINDOW_HOURS, 24):
            if (weatherData is not None):
                yhat_sequence, newTrainingData = getForecasts(model, tempHistory, 
                            numFeatures, weatherData[j:j+24])
            else:
                yhat_sequence, newTrainingData = getForecasts(model, tempHistory, 
                            numFeatures, None)
            # add current prediction to history for predicting the next day
            if (j==0 and partialSourceProductionForecast is not None):
                for k in range(24):
                    yhat_sequence[k] = partialSourceProductionForecast[currentDayHours+k]
            dayAheadPredictions.extend(yhat_sequence)
            latestHistory = testData[currentDayHours+j:currentDayHours+j+24, :].tolist()
            for k in range(24):
                latestHistory[k][DEPENDENT_VARIABLE_COL] = yhat_sequence[k]
            tempHistory.extend(latestHistory)

        # get real observation and add to history for predicting the next day
        
        history.extend(testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN, :].tolist())
        predictions.append(dayAheadPredictions)
        if (wTestData is not None):
            weatherData = wTestData[weatherIdx:weatherIdx+PREDICTION_WINDOW_HOURS, :]
            weatherIdx +=PREDICTION_WINDOW_HOURS

    # evaluate predictions days for each day
    predictedData = np.array(predictions, dtype=np.float64)
    return predictedData

def getSourceProductionForecastsInRealTime(model, history, testData, 
                            numFeatures,
                            wTestData = None, weatherData = None, 
                            partialSourceProductionForecast = None,
                            isRenewableSource=False):
    # walk-forward validation over each day
    print("Testing...")
    predictions = list()
    weatherIdx = 0
    for i in range(0, ((len(testData)//24))):
        dayAheadPredictions = list()
        tempHistory = history.copy()
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
        for j in range(0, PREDICTION_WINDOW_HOURS, 24):
            if (isRenewableSource is True):
                yhat_sequence = getForecastsInRealTime(model, tempHistory, 
                            numFeatures, weatherData[j:j+24])
            else:
                yhat_sequence = getForecastsInRealTime(model, tempHistory, 
                            numFeatures, weatherData[j:j+24, :5])
            # add current prediction to history for predicting the next day
            if (j==0 and partialSourceProductionForecast is not None):
                for k in range(24):
                    yhat_sequence[k] = partialSourceProductionForecast[currentDayHours+k]
            dayAheadPredictions.extend(yhat_sequence)
            for k in range(24):
                tempHistory[k] = yhat_sequence[k]
        # get real observation and add to history for predicting the next day
        history.extend(testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN, :].tolist())
        predictions.append(dayAheadPredictions)
        if (wTestData is not None):
            weatherData = wTestData[weatherIdx:weatherIdx+PREDICTION_WINDOW_HOURS, :]
            weatherIdx +=PREDICTION_WINDOW_HOURS

    # evaluate predictions days for each day
    predictedData = np.array(predictions, dtype=np.float64)
    return predictedData


def getForecasts(model, history, numFeatures, weatherData):
    global TRAINING_WINDOW_HOURS
    # flatten data
    data = np.array(history, dtype=np.float64)
    # retrieve last observations for input data
    input_x = data[-TRAINING_WINDOW_HOURS:]
    if (weatherData is not None):
        input_x = np.append(input_x, weatherData, axis=1)
    # reshape into [1, n_input, num_features]
    input_x = input_x.reshape((1, len(input_x), numFeatures))
    yhat = model.predict(input_x, verbose=0)
    # we only want the vector forecast
    yhat = yhat[0]
    return yhat, input_x

def getForecastsInRealTime(model, history, numFeatures, weatherData):
    global TRAINING_WINDOW_HOURS
    # flatten data
    data = np.array(history, dtype=np.float64)
    data = np.reshape(data, (data.shape[0], 1))
    # retrieve last observations for input data
    input_x = data[-TRAINING_WINDOW_HOURS:]
    if (weatherData is not None):
        input_x = np.append(input_x, weatherData, axis=1)
    # reshape into [1, n_input, num_features]
    input_x = input_x.reshape((1, len(input_x), numFeatures))
    yhat = model.predict(input_x, verbose=0)
    yhat = yhat[0]
    return yhat

def getANNHyperParams(firstTierConfig):
    hyperParams = {}
    modelHyperparamsFromConfigFile = firstTierConfig["FIRST_TIER_ANN_MODEL_HYPERPARAMS"]
    hyperParams["epoch"] = modelHyperparamsFromConfigFile["EPOCH"]
    hyperParams["batchsize"] = modelHyperparamsFromConfigFile["BATCH_SIZE"]
    hyperParams["actv"] = modelHyperparamsFromConfigFile["ACTIVATION_FUNC"]
    hyperParams["loss"] = modelHyperparamsFromConfigFile["LOSS_FUNC"]
    hyperParams["lr"] = modelHyperparamsFromConfigFile["LEARNING_RATE"]
    hyperParams["hidden"] = modelHyperparamsFromConfigFile["HIDDEN_UNITS"]
    return hyperParams

def getUnscaledForecastsAndForecastAccuracy(testData, testDates, predictedData, ftMin, ftMax):
    global MODEL_SLIDING_WINDOW_LEN
    global PREDICTION_WINDOW_HOURS
    actualData = manipulateTestDataShape(testData[:, DEPENDENT_VARIABLE_COL], False)
    formattedTestDates = manipulateTestDataShape(testDates, True)
    formattedTestDates = np.reshape(formattedTestDates, 
            formattedTestDates.shape[0]*formattedTestDates.shape[1])
    actualData = actualData.astype(np.float64)
    print("ActualData shape: ", actualData.shape)
    actual = np.reshape(actualData, actualData.shape[0]*actualData.shape[1])
    print("actual.shape: ", actual.shape)
    unscaledTestData = common.inverseDataScaling(actual, ftMax[DEPENDENT_VARIABLE_COL], 
                        ftMin[DEPENDENT_VARIABLE_COL])
    predictedData = predictedData.astype(np.float64)
    print("PredictedData shape: ", predictedData.shape)
    predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
    print("predicted.shape: ", predicted.shape)
    unscaledPredictedData = common.inverseDataScaling(predicted, 
                ftMax[DEPENDENT_VARIABLE_COL], ftMin[DEPENDENT_VARIABLE_COL])
    rmseScore, mapeScore = common.getScores(actualData, predictedData, 
                                unscaledTestData, unscaledPredictedData)    
    return unscaledTestData, unscaledPredictedData, formattedTestDates, rmseScore, mapeScore

def writeSourceProductionForecastsToFile(formattedTestDates, unscaledTestData, unscaledPredictedData,
                                        period, source, outFileName):
    data = []
    
    for i in range(len(unscaledPredictedData)):
        row = []
        row.append(str(formattedTestDates[i]))
        row.append(str(unscaledTestData[i]))
        row.append(str(unscaledPredictedData[i]))
        data.append(row)
    writeMode = "w"
    if (period > 0):
        writeMode = "a"
    common.writeOutFile(outFileName, data, source.lower(), writeMode)
    return

def writeRealTimeSourceProductionForecastsToFile(formattedTestDates, unscaledPredictedData,
                                        source, outFileName, creationTimeInUTC, version):
    data = []
    for i in range(len(unscaledPredictedData)):
        row = []
        row.append(str(formattedTestDates[i]))
        row.append(creationTimeInUTC)
        row.append(version)
        row.append(str(unscaledPredictedData[i]))
        data.append(row)
    print("Writing to ", outFileName, "...")
    fields = ["datetime", "creation_time (UTC)", "version", "avg_"+source.lower()+"_production_forecast"] # TODO:[DM] Change this & legacy code to UTC time later if required
    with open(outFileName, "w") as csvfile: 
        csvwriter = csv.writer(csvfile)   
        csvwriter.writerow(fields) 
        csvwriter.writerows(data)
    return

if __name__ == "__main__":
    print("CarbonCast first tier. Refer github repo for regions & sources.")
    if (len(sys.argv) !=2):
        print("Usage: python3 firstTierForecasts.py <configFileName>")
        print("")
        exit(0)
    configFileName = sys.argv[1]
    runFirstTier(configFileName)
    print("End")