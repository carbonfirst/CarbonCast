'''
File to generate 96-hour carbon intensity forecasts.
Multivariate multi-step time series forecasting
'''

import csv
import math
import sys
from datetime import datetime as dt
from datetime import timezone as tz

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz as pytz
from keras.layers import Dense, Flatten, LSTM
from keras.layers import Conv1D, MaxPooling1D
from keras.layers import Activation, Dropout
from keras.models import Sequential
import tensorflow as tf
from keras.callbacks import EarlyStopping
from keras.callbacks import ModelCheckpoint, ReduceLROnPlateau
from keras.models import load_model, save_model
from keras.layers import RepeatVector

import json5 as json

import common
import utility


# [DM] Sweden "unknown" carbon emission factor is different. Refer ElectricityMap github for details

############################# MACRO START #######################################
DAY_INTERVAL = 1
MONTH_INTERVAL = 1
DEPENDENT_VARIABLE_COL = 0

TRAINING_WINDOW_HOURS = None
PREDICTION_WINDOW_HOURS = None
MAX_PREDICTION_WINDOW_HOURS = None
MODEL_SLIDING_WINDOW_LEN = None
BUFFER_HOURS = None
SAVED_MODEL_LOCATION = None
TOP_N_FEATURES = 0
############################# MACRO END #########################################

def runSecondTier(configFileName, cefType, loadFromSavedModel):
    global TRAINING_WINDOW_HOURS
    global PREDICTION_WINDOW_HOURS
    global MAX_PREDICTION_WINDOW_HOURS
    global MODEL_SLIDING_WINDOW_LEN
    global BUFFER_HOURS
    global DEPENDENT_VARIABLE_COL
    global SAVED_MODEL_LOCATION
    global TOP_N_FEATURES

    secondTierConfig = {}

    with open(configFileName, "r") as configFile:
        secondTierConfig = json.load(configFile)
        # print(secondTierConfig)

    numTestDays = secondTierConfig["NUM_TEST_DAYS"]
    numValDays = secondTierConfig["NUM_VAL_DAYS"]
    TRAINING_WINDOW_HOURS = secondTierConfig["TRAINING_WINDOW_HOURS"]
    MODEL_SLIDING_WINDOW_LEN = secondTierConfig["MODEL_SLIDING_WINDOW_LEN"]
    PREDICTION_WINDOW_HOURS = secondTierConfig["PREDICTION_WINDOW_HOURS"]
    MAX_PREDICTION_WINDOW_HOURS = secondTierConfig["MAX_PREDICTION_WINDOW_HOURS"]
    TOP_N_FEATURES = secondTierConfig["TOP_N_FEATURES"]
    NUMBER_OF_EXPERIMENTS = secondTierConfig["NUMBER_OF_EXPERIMENTS_PER_REGION"]
    BUFFER_HOURS = PREDICTION_WINDOW_HOURS - 24

    regionList = secondTierConfig["TMP_REGION"]
    if (loadFromSavedModel is True):
        NUMBER_OF_EXPERIMENTS = 1
    if (cefType == "-l"):
        SAVED_MODEL_LOCATION = secondTierConfig["LIFECYCLE_SAVED_MODEL_LOCATION"]
    else:
        SAVED_MODEL_LOCATION = secondTierConfig["DIRECT_SAVED_MODEL_LOCATION"]
    writeCIForecastsToFile = secondTierConfig["WRITE_CI_FORECASTS_TO_FILE"]

    for region in regionList:
        print("CarbonCast: CNN-LSTM model for region:", region)
        regionConfig = secondTierConfig[region]
        inFileName = regionConfig["DIRECT_CEF_IN_FILE_NAME"]
        outFileNamePrefix = regionConfig["DIRECT_CEF_OUT_FILE_NAME_PREFIX"]
        if (cefType == "-l"):
            inFileName = regionConfig["LIFECYCLE_CEF_IN_FILE_NAME"]
            outFileNamePrefix = regionConfig["LIFECYCLE_CEF_OUT_FILE_NAME_PREFIX"]
        forecastInFileName = regionConfig["FORECAST_IN_FILE_NAME"]
        numHistoricalAndDateTimeFeatures = secondTierConfig["NUM_FEATURES"]
        numForecastFeatures = regionConfig["NUM_FORECAST_FEATURES"]
        startCol = secondTierConfig["START_COL"]
        trainTestPeriodConfig = secondTierConfig["TRAIN_TEST_PERIOD"]

        
        for exptNum in range(NUMBER_OF_EXPERIMENTS):
            periodIdx = 0 
            for period in trainTestPeriodConfig: 
                print(trainTestPeriodConfig[period])
                datasetLimiter = trainTestPeriodConfig[period]["DATASET_LIMITER"]
                numTestDays = trainTestPeriodConfig[period]["NUM_TEST_DAYS"]
                numValDays = secondTierConfig["NUM_VAL_DAYS"]
                forecastDatasetLimiter = datasetLimiter//24*PREDICTION_WINDOW_HOURS
                print(numTestDays)

                print("Initializing...")
                dataset, dateTime, forecastDataset = initialize(inFileName, forecastInFileName, startCol)
                print(dataset.tail())
                dataset = dataset[:datasetLimiter]
                dateTime = dateTime[:datasetLimiter]
                print(dataset.tail())
                specializedForecasts = None

                if ("NUM_SPECIALIZED_FORECAST_FEATURES" in regionConfig): # weather + subset of source production forecasts
                    numForecastFeatures = regionConfig["NUM_SPECIALIZED_FORECAST_FEATURES"]
                    specializedForecasts = regionConfig["SPECIALIZED_FORECASTS"]
                    modifiedForecastDataset = forecastDataset.iloc[:, :5].copy()
                    for source in specializedForecasts:
                        modifiedForecastDataset["avg_"+source.lower()+"_production_forecast"] = forecastDataset["avg_"+source.lower()+"_production_forecast"]
                    forecastDataset = modifiedForecastDataset
                print("***** Initialization done *****")

                # split into train and test
                print("Spliting dataset into train/test...")
                # dataset = dataset[:-BUFFER_HOURS]
                trainData, valData, testData, _ = common.splitDataset(dataset.values, 
                                                        (numTestDays+BUFFER_HOURS//24), numValDays, 
                                                        MAX_PREDICTION_WINDOW_HOURS-PREDICTION_WINDOW_HOURS)
                trainDates = dateTime[: -((numTestDays+BUFFER_HOURS//24)*24):]
                print(f'The train dates for {period} {trainDates[-10:]}')
                trainDates, validationDates = trainDates[: -(numValDays*24)], trainDates[-(numValDays*24):]
                testDates = dateTime[-((numTestDays+BUFFER_HOURS//24)*24):]
                print(f'The test dates for {period} {testDates[-10:]}')

                trainData = trainData[:, startCol: startCol+numHistoricalAndDateTimeFeatures]
                valData = valData[:, startCol: startCol+numHistoricalAndDateTimeFeatures]
                testData = testData[:, startCol: startCol+numHistoricalAndDateTimeFeatures]

                #bufferPeriod = bufferPeriod[:, startCol: startCol + numHistoricalAndDateTimeFeatures]
                #if len((bufferDates)>0):
                #    testDates = np.append(testDates,bufferDates)
                #    testData = np.vstack(testData,bufferPeriod)

                print("TrainData shape: ", trainData.shape) # days x hour x features
                print("ValData shape: ", valData.shape) # days x hour x features
                print("TestData shape: ", testData.shape) # days x hour x features

                wTrainData, wValData, wTestData, wFullTrainData = common.splitWeatherDataset(
                        forecastDataset.values, numTestDays, numValDays, MAX_PREDICTION_WINDOW_HOURS)
                wTrainData = wTrainData[:, :numForecastFeatures]
                wValData = wValData[:, :numForecastFeatures]
                wTestData = wTestData[:, :numForecastFeatures]
                print("WeatherTrainData shape: ", wTrainData.shape) # (days x hour) x features
                print("WeatherValData shape: ", wValData.shape) # (days x hour) x features
                print("WeatherTestData shape: ", wTestData.shape) # (days x hour) x features

                trainData = fillMissingData(trainData)
                valData = fillMissingData(valData)
                testData = fillMissingData(testData)

                wTrainData = fillMissingData(wTrainData)
                wValData = fillMissingData(wValData)
                wTestData = fillMissingData(wTestData)

                print("***** Dataset split done *****")

                featureList = dataset.columns.values
                featureList = featureList[startCol:startCol+numHistoricalAndDateTimeFeatures].tolist()
                featureList.extend(forecastDataset.columns.values[:numForecastFeatures])
                print("Features: ", featureList)

                print("Scaling data...")
                # unscaledTestData = np.zeros(testData.shape[0])
                unscaledTrainCarbonIntensity = np.zeros(trainData.shape[0])
                # for i in range(testData.shape[0]):
                #     unscaledTestData[i] = testData[i, DEPENDENT_VARIABLE_COL]
                for i in range(trainData.shape[0]):
                    unscaledTrainCarbonIntensity[i] = trainData[i, DEPENDENT_VARIABLE_COL]
                trainData, valData, testData, ftMin, ftMax = common.scaleDataset(trainData, valData, testData)
                print(trainData.shape, valData.shape, testData.shape)
                wTrainData, wValData, wTestData, wFtMin, wFtMax = common.scaleDataset(wTrainData, wValData, wTestData)
                print(wTrainData.shape, wValData.shape, wTestData.shape)
                print("***** Data scaling done *****")

                if (periodIdx == len(trainTestPeriodConfig)-1):
                    print("Saving min & max values for each column in file...")
                    with open(SAVED_MODEL_LOCATION+region+"/"+region+"_min_max_values.txt", "w") as f:
                        f.writelines(str(ftMin))
                        f.write("\n")
                        f.writelines(str(ftMax))
                        f.write("\n")
                        f.writelines(str(wFtMin))
                        f.write("\n")
                        f.writelines(str(wFtMax))
                        f.write("\n")
                    print("Min-max values saved")

                ######################## START #####################
                bestRMSE, bestMAPE = [], []
                predictedData = None
                print("Iteration: ", exptNum)
                regionDailyMape = {}
                bestModel, numFeaturesInTraining = trainingandValidationPhase(region, trainData, wTrainData, 
                                                valData, wValData, secondTierConfig, exptNum, loadFromSavedModel)            
                history = valData[-TRAINING_WINDOW_HOURS:, :]
                weatherData = None
                weatherData = wValData[-MAX_PREDICTION_WINDOW_HOURS:, :]
                print("weatherData shape:", weatherData.shape)
                history = history.tolist()
                
                predictedData = getDayAheadForecasts(bestModel, history, testData, 
                                    TRAINING_WINDOW_HOURS, numFeaturesInTraining, DEPENDENT_VARIABLE_COL,
                                    wFtMin[5:], wFtMax[5:], ftMin[DEPENDENT_VARIABLE_COL], ftMax[DEPENDENT_VARIABLE_COL],
                                    wTestData, weatherData, forecastDataset.columns.values[:numForecastFeatures])
                print("***** Forecast done *****")

                unscaledTestData, unscaledPredictedData, formattedTestDates, rmseScore, mapeScore, dailyMapeScore = getUnscaledForecastsAndForecastAccuracy(
                                                                            testData, testDates, predictedData, 
                                                                            ftMin, ftMax)
                regionDailyMape[region] = dailyMapeScore

                # print("**** Important features based on valData:")
                # topNFeatures = findImportantFeatures(bestModel, valData, featureList, testDates)
                print("**** Important features based on testData:")
                modTestData = manipulateTestDataShape(testData, MODEL_SLIDING_WINDOW_LEN, PREDICTION_WINDOW_HOURS, False)
                modTestData = np.reshape(modTestData, (modTestData.shape[0]*modTestData.shape[1], modTestData.shape[2]))
                print(modTestData.shape, wTestData.shape)
                modTestData = np.append(modTestData, wTestData, axis=1)
                print("modtestdata shape: ", modTestData.shape)
                #topNFeatures = findImportantFeatures(bestModel, modTestData, featureList, testDates)

                print("[BESTMODEL] Overall RMSE score: ", rmseScore)
                print("[BESTMODEL] Overall MAPE score: ", mapeScore)
                # print(scores)
                bestRMSE.append(rmseScore)
                bestMAPE.append(mapeScore)
                print("Overall Mean MAPE: ", mapeScore)
                print("Daywise statistics...")
                mapeByDay = []
                for i in range(0, PREDICTION_WINDOW_HOURS//24):
                    print("Prediction day ", i+1, "(", (i*24), " - ", (i+1)*24, " hrs)")
                    print("Mean MAPE: ", np.mean(regionDailyMape[region][:, i]))
                    print("Median MAPE: ", np.percentile(regionDailyMape[region][:, i], 50))
                    print("90th percentile MAPE: ", np.percentile(regionDailyMape[region][:, i], 90))
                    print("95th percentile MAPE: ", np.percentile(regionDailyMape[region][:, i], 95))
                    print("99th percentile MAPE: ", np.percentile(regionDailyMape[region][:, i], 99))
                    mapeByDay.append([i+1, np.mean(regionDailyMape[region][:, i]), np.percentile(regionDailyMape[region][:, i], 50),
                                        np.percentile(regionDailyMape[region][:, i], 90), 
                                        np.percentile(regionDailyMape[region][:, i], 95),
                                        np.percentile(regionDailyMape[region][:, i], 99)])

                print("Saving MAPE values by day in file...")
                with open("../data/EU_DATA/"+region+"/"+region+"_MAPE_iter"+str(exptNum)+".txt", "w") as f: 
                #with open("../data/"+region+"/"+region+"_MAPE_iter"+str(exptNum)+".txt", "w") as f:
                    for item in mapeByDay:
                        f.writelines(str(item))
                        f.write("\n")
                print("MAPE values by day saved")

                data = []
                for i in range(len(unscaledTestData)):
                    row = []
                    row.append(str(formattedTestDates[i]))
                    row.append(str(unscaledTestData[i]))
                    row.append(str(unscaledPredictedData[i]))
                    data.append(row)
                    #print(data)

                if (writeCIForecastsToFile == "True"):
                    common.writeOutFile(outFileNamePrefix+"_"+str(exptNum)+ period +".csv", data, "carbon_intensity", "w")

                print("[BEST] Average RMSE after ", NUMBER_OF_EXPERIMENTS, " expts: ", np.mean(bestRMSE))
                print("[BEST] Average MAPE after ", NUMBER_OF_EXPERIMENTS, " expts: ", np.mean(bestMAPE))
                print(bestRMSE)
                print(bestMAPE)
            periodIdx +=1 

        ######################## END #####################
        
        print("####################", region, " done ####################\n\n")

    return

def runSecondTierInRealTime(configFileName, regionList, cefType, startDate, electricityDataDate, 
                               realTimeFileDir, realTimeWeatherFileDir,
                               realTimeForeCastFileName):
    global TRAINING_WINDOW_HOURS
    global PREDICTION_WINDOW_HOURS
    global MAX_PREDICTION_WINDOW_HOURS
    global MODEL_SLIDING_WINDOW_LEN
    global DEPENDENT_VARIABLE_COL
    global SAVED_MODEL_LOCATION
    global TOP_N_FEATURES

    secondTierConfig = {}

    with open(configFileName, "r") as configFile:
        secondTierConfig = json.load(configFile)
        # print(secondTierConfig)

    TRAINING_WINDOW_HOURS = secondTierConfig["TRAINING_WINDOW_HOURS"]
    MODEL_SLIDING_WINDOW_LEN = secondTierConfig["MODEL_SLIDING_WINDOW_LEN"]
    PREDICTION_WINDOW_HOURS = secondTierConfig["PREDICTION_WINDOW_HOURS"]
    MAX_PREDICTION_WINDOW_HOURS = secondTierConfig["MAX_PREDICTION_WINDOW_HOURS"]
    TOP_N_FEATURES = secondTierConfig["TOP_N_FEATURES"]

    if (cefType == "-l"):
        SAVED_MODEL_LOCATION = secondTierConfig["LIFECYCLE_SAVED_MODEL_LOCATION"]
    else:
        SAVED_MODEL_LOCATION = secondTierConfig["DIRECT_SAVED_MODEL_LOCATION"]
    writeCIForecastsToFile = secondTierConfig["WRITE_CI_FORECASTS_TO_FILE"]

    for region in regionList:
        print("CarbonCast: CNN-LSTM model for region:", region)
        if (cefType == "-l"):
            print("Lifecycle CEF")
        else:
            print("Direct CEF")
        regionConfig = secondTierConfig[region]
        inFileName = realTimeFileDir+region+"/"+region+"_"+str(electricityDataDate)+"_direct_emissions.csv"
        outFileName = realTimeFileDir+region+"/"+region+"_direct_CI_forecasts_"+str(startDate)+".csv"
        if (cefType == "-l"):
            inFileName = realTimeFileDir+region+"/"+region+"_"+str(electricityDataDate)+"_lifecycle_emissions.csv"
            outFileName = realTimeFileDir+region+"/"+region+"_lifecycle_CI_forecasts_"+str(startDate)+".csv"
        forecastInFileName = realTimeForeCastFileName[region]
        numHistoricalAndDateTimeFeatures = secondTierConfig["NUM_FEATURES"]
        numForecastFeatures = regionConfig["NUM_FORECAST_FEATURES"]
        startCol = secondTierConfig["START_COL"]

        print("Initializing...")
        print(inFileName, forecastInFileName)
        dataset, testDates, forecastDataset = initializeInRealTime(inFileName, forecastInFileName, startCol)
        print("***** Initialization done *****")

        testData = np.array(dataset.values[:, startCol:startCol+1])
        testData = fillMissingData(testData)
        wTestData = np.array(forecastDataset.values[:, 0:numHistoricalAndDateTimeFeatures+numForecastFeatures-1])
        wTestData = fillMissingData(wTestData)
        print("Total no. of features = ", numHistoricalAndDateTimeFeatures+numForecastFeatures)
        print(testData.shape, wTestData.shape)

        print("Scaling data...")
        minMaxFeatureFileName = SAVED_MODEL_LOCATION+region+"/"+region+"_min_max_values.txt"
        ftMin, ftMax, wFtMin, wFtMax = common.getMinMaxFeatureValues(minMaxFeatureFileName, areForecastsFeatures=True)
        testData = common.scaleTestDataWithTrainingValues(testData, ftMin, ftMax)
        wTestData= common.scaleTestDataWithTrainingValues(wTestData, wFtMin, wFtMax)
        
        # unscaledTrainCarbonIntensity = np.zeros(trainData.shape[0])
        print("***** Data scaling done *****")

        ######################## START #####################
        savedModelName = SAVED_MODEL_LOCATION+region+"/"+region+".h5"
        model = load_model(savedModelName)
        # model.summary()

        history = testData[-TRAINING_WINDOW_HOURS:, :]
        weatherData = wTestData[-PREDICTION_WINDOW_HOURS:, :]
        history = history.tolist()
        predictedData = getCIForecastsInRealTime(model, history, testData, 
                                    numHistoricalAndDateTimeFeatures+numForecastFeatures, 
                                    wTestData, weatherData)
        print("***** Forecast done *****")
        ######################## END #####################
        
        print("####################", region, " done ####################\n\n")

    predictedData = predictedData.astype(np.float64)
    predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
    unscaledPredictedData = common.inverseDataScaling(predicted, ftMax[DEPENDENT_VARIABLE_COL], 
                                                      ftMin[DEPENDENT_VARIABLE_COL])

    writeRealTimeCIForecastsToFile(testDates, unscaledPredictedData, outFileName)
    return outFileName

def initialize(inFileName, forecastInFileName, startCol):
    print(inFileName)
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])    
    dataset = dataset[8760:-72]
    print(dataset.head())
    print(dataset.columns)
    dateTime = dataset.index.values

    print(forecastInFileName)
    # forecastDataset = pd.read_csv(forecastInFileName, header=0, infer_datetime_format=True, 
    #                         parse_dates=['UTC time'], index_col=['UTC time']) # old data files
    forecastDataset = pd.read_csv(forecastInFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['datetime'], index_col=['datetime']) # new data files in data

    for i in range(startCol, len(dataset.columns.values)):
        col = dataset.columns.values[i]
        dataset[col] = dataset[col].astype(np.float64)
        print(col, dataset[col].dtype)

    print("\nAdding features related to date & time...")
    modifiedDataset = addDateTimeFeatures(dataset, dateTime, startCol)
    dataset = modifiedDataset
    print("Features related to date & time added")


    return dataset, dateTime, forecastDataset

def initializeInRealTime(inFileName, forecastInFileName, startCol):
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])

    forecastDataset = pd.read_csv(forecastInFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['datetime'], index_col=['datetime'])
    forecastDateTime = forecastDataset.index.values
    
    print("\nAdding features related to date & time...")
    # Adding in weather dataset, as we need for 96 hours
    modifiedForecastDataset = common.addDateTimeFeatures(forecastDataset, forecastDateTime, -1)
    forecastDataset = modifiedForecastDataset
    print(forecastDataset.head())
    print("Features related to date & time added")
    
    for i in range(startCol, len(dataset.columns.values)):
        col = dataset.columns.values[i]
        dataset[col] = dataset[col].astype(np.float64)

    return dataset, forecastDateTime, forecastDataset

# Date time feature engineering
def addDateTimeFeatures(dataset, dateTime, startCol):
    global DEPENDENT_VARIABLE_COL
    dates = []
    hourList = []
    hourSin, hourCos = [], []
    monthList = []
    monthSin, monthCos = [], []
    weekendList = []
    columns = dataset.columns
    secInDay = 24 * 60 * 60 # Seconds in day 
    secInYear = year = (365.25) * secInDay # Seconds in year 

    day = pd.to_datetime(dateTime[0])
    isWeekend = 0
    zero = 0
    one = 0
    for i in range(0, len(dateTime)):
        day = pd.to_datetime(dateTime[i])
        dates.append(day)
        hourList.append(day.hour)
        hourSin.append(np.sin(day.hour * (2 * np.pi / 24)))
        hourCos.append(np.cos(day.hour * (2 * np.pi / 24)))
        monthList.append(day.month)
        monthSin.append(np.sin(day.timestamp() * (2 * np.pi / secInYear)))
        monthCos.append(np.cos(day.timestamp() * (2 * np.pi / secInYear)))
        if (day.weekday() < 5):
            isWeekend = 0
            zero +=1
        else:
            isWeekend = 1
            one +=1
        weekendList.append(isWeekend)        
    loc = startCol+1
    print(zero, one)
    # hour of day feature
    dataset.insert(loc=loc, column="hour_sin", value=hourSin)
    dataset.insert(loc=loc+1, column="hour_cos", value=hourCos)
    # month of year feature
    dataset.insert(loc=loc+2, column="month_sin", value=monthSin)
    dataset.insert(loc=loc+3, column="month_cos", value=monthCos)
    # is weekend feature
    dataset.insert(loc=loc+4, column="weekend", value=weekendList)

    # print(dataset.columns)
    print(dataset.head())
    return dataset

# convert history into inputs and outputs
def manipulateTrainingDataShape(data, trainWindowHours, labelWindowHours, weatherData = None): 
    print("Data shape: ", data.shape)
    global MAX_PREDICTION_WINDOW_HOURS
    global PREDICTION_WINDOW_HOURS
    X, y, weatherX = list(), list(), list()
    weatherIdx = 0
    hourIdx = 0
    # step over the entire history one time step at a time
    for i in range(len(data)-(trainWindowHours+labelWindowHours)+1):
        # define the end of the input sequence
        trainWindow = i + trainWindowHours
        labelWindow = trainWindow + labelWindowHours
        xInput = data[i:trainWindow, :]
        # xInput = xInput.reshape((len(xInput), 1))
        X.append(xInput)
        weatherX.append(weatherData[weatherIdx:weatherIdx+trainWindowHours])
        weatherIdx +=1
        hourIdx +=1
        if(hourIdx ==24):
            hourIdx = 0
            weatherIdx += (MAX_PREDICTION_WINDOW_HOURS-24)
        y.append(data[trainWindow:labelWindow, DEPENDENT_VARIABLE_COL])
    X = np.array(X, dtype=np.float64)
    y = np.array(y, dtype=np.float64)
    weatherX = np.array(weatherX, dtype=np.float64)
    X = np.append(X, weatherX, axis=2)
    return X, y

def manipulateTestDataShape(data, slidingWindowLen, predictionWindowHours, isDates=False): 
    X = list()
    # step over the entire history one time step at a time
    for i in range(0, len(data)-(predictionWindowHours)+1, slidingWindowLen):
        # define the end of the input sequence
        predictionWindow = i + predictionWindowHours
        X.append(data[i:predictionWindow])
    if (isDates is False):
        X = np.array(X, dtype=np.float64)
    else:
        X = np.array(X)
    return X

# train the model
def trainModel(trainX, trainY, valX, valY, hyperParams, iteration, region, loadFromSavedModel):
    global SAVED_MODEL_LOCATION

    # define parameters
    print("Training...")
    verbose = 2
    hist = None
    bestModel = None
    n_timesteps, n_features, n_outputs = trainX.shape[1], trainX.shape[2], trainY.shape[1]
    print("Timesteps: ", n_timesteps, "No. of features: ", n_features, "No. of outputs: ", n_outputs)

    if (loadFromSavedModel is True):
        print("-s parameter specified. Loading model from ", SAVED_MODEL_LOCATION+region+"/"+region+".h5")
        bestModel = load_model(SAVED_MODEL_LOCATION+region+"/"+region+".h5")
        return bestModel, n_features

    epochs = hyperParams["epoch"]    
    batchSize = hyperParams["batchsize"]
    activationFunc = hyperParams["actv"]
    lossFunc = hyperParams["loss"]
    learningRate = hyperParams["lr"]
    minLearningRate = hyperParams["minlr"]
    kernel1Size = hyperParams["kernel1"]
    kernel2Size = hyperParams["kernel2"]
    numFilters1 = hyperParams["filter1"]
    numFilters2 = hyperParams["filter2"]
    cnnPoolSize = hyperParams["poolsize"]
    dropoutRate = hyperParams["dropoutRate"]    
    
#################################### CNN LSTM model #################################
    model = Sequential()
    model.add(Conv1D(filters=numFilters1, kernel_size=kernel1Size, padding="same",
            activation=activationFunc, input_shape=(n_timesteps,n_features)))
    model.add(MaxPooling1D(pool_size=cnnPoolSize))
    model.add(Conv1D(filters=numFilters2, kernel_size=kernel2Size,
            activation=activationFunc, input_shape=(n_timesteps,n_features)))
    
    model.add(Flatten())
    model.add(RepeatVector(n_outputs))
    model.add(LSTM(n_outputs))
    model.add(Dropout(dropoutRate))
    model.add(Dense(n_outputs))
################################################################################

    opt = tf.keras.optimizers.Adam(learning_rate = learningRate)
    model.compile(loss=lossFunc, optimizer=opt, metrics=['mean_absolute_error'])
    # simple early stopping
    es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=10)
    mc = ModelCheckpoint(SAVED_MODEL_LOCATION+region+"/"+region+".h5", monitor='val_loss', mode='min', verbose=1, save_best_only=True)
    rlr = ReduceLROnPlateau(monitor="val_loss", mode="min", factor=0.1, patience=6, verbose=1, min_lr=minLearningRate)

# fit network
    hist = model.fit(trainX, trainY, epochs=epochs, batch_size=batchSize[0], verbose=verbose,
                        validation_data=(valX, valY), callbacks=[rlr, es, mc])

    # bestModel = load_model(region+"_best_model_iter"+str(iteration)+".h5")
    bestModel = load_model(SAVED_MODEL_LOCATION+region+"/"+region+".h5")
    # showModelSummary(hist, bestModel, "CNN")
    # print("Training the best model...")
    # hist = bestModel.fit(trainX, trainY, epochs=100, batch_size=trainParameters['batchsize'], verbose=verbose)
    return bestModel, n_features

def showModelSummary(history, model, architecture=None):
    print("Showing model summary...")
    model.summary()
    print("***** Model summary shown *****")
    # list all data in history
    print(history.history.keys()) # ['loss', 'mean_absolute_error', 'val_loss', 'val_mean_absolute_error']
    return

def getDayAheadForecasts(model, history, testData, 
                            trainWindowHours, numFeatures, depVarColumn,
                            wFtMin, wFtMax, ciMin, ciMax,
                            wTestData = None, weatherData = None,
                            forecastColumns=None):
    global MODEL_SLIDING_WINDOW_LEN
    global PREDICTION_WINDOW_HOURS
    global MAX_PREDICTION_WINDOW_HOURS
    global BUFFER_HOURS
    # walk-forward validation over each day
    print("Testing (day ahead forecasts)...")
    # print(ciMin, ciMax)
    predictions = list()
    weatherIdx = 0
    avgTimeToForecast = 0
    for i in range(0, ((len(testData)//24)-(BUFFER_HOURS//24))):
        beforeForecast = dt.now()
        dayAheadPredictions = list()
        # predict n days, 1 day at a time
        tempHistory = history.copy()
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
        for j in range(0, MAX_PREDICTION_WINDOW_HOURS, 24):
            if (j >= PREDICTION_WINDOW_HOURS):
                continue
            yhat_sequence, _ = getForecasts(model, tempHistory, 
                            trainWindowHours, numFeatures, weatherData[j:j+24])
            dayAheadPredictions.extend(yhat_sequence)
            # add current prediction to history for predicting the next day
            latestHistory = testData[currentDayHours+j:currentDayHours+j+24, :].tolist()
            for k in range(24):
                latestHistory[k][depVarColumn] = yhat_sequence[k]
            tempHistory.extend(latestHistory)
        # get real observation and add to history for predicting the next day
        
        history.extend(testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN, :].tolist())
        predictions.append(dayAheadPredictions)
        weatherData = wTestData[weatherIdx:weatherIdx+MAX_PREDICTION_WINDOW_HOURS, :]
        weatherIdx += MAX_PREDICTION_WINDOW_HOURS
        afterForecast = dt.now()
        timeTakenToForecast = (afterForecast - beforeForecast).total_seconds()
        # print("Day: ", i, ", time to forecast = ", timeTakenToForecast)
        avgTimeToForecast +=timeTakenToForecast

    avgTimeToForecast /= ((len(testData)//24)-(BUFFER_HOURS//24))
    print("Average time taken for a 96-hour forecast = ", avgTimeToForecast)

    # evaluate predictions days for each day
    predictedData = np.array(predictions, dtype=np.float64)
    return predictedData

def getCIForecastsInRealTime(model, history, testData, numFeatures, 
                   wTestData = None, weatherData = None):
    # walk-forward validation over each day
    print("Testing...")
    predictions = list()
    weatherIdx = 0
    for i in range(0, ((len(testData)//24))):
        dayAheadPredictions = list()
        tempHistory = history.copy()
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
        for j in range(0, MAX_PREDICTION_WINDOW_HOURS, 24):
            if (j >= PREDICTION_WINDOW_HOURS):
                continue
            yhat_sequence = getForecastsInRealTime(model, tempHistory, 
                                         numFeatures, weatherData[j:j+24])
            dayAheadPredictions.extend(yhat_sequence)
            # add current prediction to history for predicting the next day
            for k in range(24):
                tempHistory[k] = yhat_sequence[k]
        # get real observation and add to history for predicting the next day
        
        history.extend(testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN, :].tolist())
        predictions.append(dayAheadPredictions)
        weatherData = wTestData[weatherIdx:weatherIdx+MAX_PREDICTION_WINDOW_HOURS, :]
        weatherIdx += MAX_PREDICTION_WINDOW_HOURS
    # evaluate predictions days for each day
    predictedData = np.array(predictions, dtype=np.float64)
    return predictedData

def getForecasts(model, history, trainWindowHours, numFeatures, weatherData):
    # flatten data
    data = np.array(history, dtype=np.float64)
    # retrieve last observations for input data
    input_x = data[-trainWindowHours:]
    input_x = np.append(input_x, weatherData, axis=1)
    # reshape into [1, n_input, num_features]
    input_x = input_x.reshape((1, len(input_x), numFeatures))
    yhat = model.predict(input_x, verbose=0)
    # we only want the vector forecast
    yhat = yhat[0]
    return yhat, input_x

def getForecastsInRealTime(model, history, numFeatures, weatherData):
    # flatten data
    data = np.array(history, dtype=np.float64)
    data = np.reshape(data, (data.shape[0], 1))
    # retrieve last observations for input data
    input_x = data[-TRAINING_WINDOW_HOURS:]
    input_x = np.append(input_x, weatherData, axis=1)
    # reshape into [1, n_input, num_features]
    input_x = input_x.reshape((1, len(input_x), numFeatures))
    yhat = model.predict(input_x, verbose=0)
    # we only want the vector forecast
    yhat = yhat[0]
    return yhat

def featureImportance(seq, model, features, testDates):
    # print(seq.shape)
    id_=1
    seq = tf.Variable(seq[np.newaxis,:,:], dtype=tf.float32)
    with tf.GradientTape() as tape:
        predictions = model(seq)
    grads = tape.gradient(predictions, seq)
    grads = tf.reduce_mean(grads, axis=1).numpy()[0]
    return grads

def findImportantFeatures(model, valData, featureList, testDates):
    # print(model.summary())
    # print(valData.shape)
    global TOP_N_FEATURES
    global PREDICTION_WINDOW_HOURS
    global MODEL_SLIDING_WINDOW_LEN
    topNFeatures = {}
    featureImp = {}
    valDataReshaped = np.reshape(valData, (valData.shape[0]//MODEL_SLIDING_WINDOW_LEN, MODEL_SLIDING_WINDOW_LEN, valData.shape[1]))
    print(valDataReshaped.shape)

    # dailydata = np.zeros((PREDICTION_WINDOW_HOURS//24, valDataReshaped.shape[0], valDataReshaped.shape[1], valDataReshaped.shape[2]))
    dailydata = [[] for _ in range(PREDICTION_WINDOW_HOURS//24)]
    # print(dailydata.shape)
    for i in range(0, valDataReshaped.shape[0], PREDICTION_WINDOW_HOURS//24):
        for j in range(PREDICTION_WINDOW_HOURS//24):
            # print(j, ": ", i+j)
            dailydata[j].append(valDataReshaped[i+j])

    dailydata = np.array(dailydata)
    print(dailydata.shape)

    for day in range(PREDICTION_WINDOW_HOURS//24):
        topNFeatures = {}
        featureImp = {}

        grads = [None] * len(dailydata[day])
        for i in range(len(dailydata[day])):
            grads[i] = featureImportance(dailydata[day][i], model, featureList, testDates)
        gradAvg = np.array(grads)
        gradAvg = np.mean(gradAvg, axis=0)
        # print(gradAvg, np.sum(gradAvg))

        for i in range(len(gradAvg)):
            featureImp[featureList[i]] = gradAvg[i]
        featureImp = dict(sorted(featureImp.items(), key=lambda item: item[1]))

        tmp=[]
        for ft, grad in featureImp.items():
            tmp.append([ft, grad])
        left = 0
        right = len(tmp)-1
        idx = 0
        for i in range(len(tmp)):
            if (idx == TOP_N_FEATURES):
                break
            if (abs(tmp[left][1]) > abs(tmp[right][1])):
                topNFeatures[tmp[left][0]] = tmp[left][1]
                left +=1
            else:
                topNFeatures[tmp[right][0]] = tmp[right][1]
                right -=1
            idx +=1

        print("Day ", day+1, ": Top ", TOP_N_FEATURES, " features:")
        for key, val in topNFeatures.items():
            print(key, ": ", val)
    
    xLabel = ["carbon_intensity", "hour_sin", "hour_cos", "month_sin", "month_cos", "weekend",
            "coal", "nat_gas", "nuclear", "hydro",
            "solar", "wind", "other", "fcst_wind_speed", "fcst_temp", 
            "fcst_dewpoint", "fcst_dswrf", "fcst_precip",
            "coal_fcst", "nat_gas_fcst", "nuclear_fcst", "hydro_fcst",
            "wind_fcst", "solar_fcst", "other_fcst"]

    # plt.figure()
    # plt.bar(range(len(gradAvg)), gradAvg, color=(0.1, 0.1, 0.1, 0.1),  edgecolor='blue')
    # # plt.xticks(range(len(featureList)), featureList, rotation=90)
    # plt.xticks(range(len(featureList)), xLabel[:len(featureList)], rotation=80, fontsize=21)
    # plt.yticks(fontsize=20)
    # for i in range(len(gradAvg)):
    #     plt.text(i,gradAvg[i],round(gradAvg[i], 2), fontsize=16)
    # plt.ylabel('Gradients', fontsize=22) 
    # # plt.xlabel('Features', fontsize=22)
    # plt.show() 
    # plt.title("Feature importance - " + region)
    return topNFeatures

def getScores(scaledActual, scaledPredicted, unscaledActual, unscaledPredicted, dates):
    global PREDICTION_WINDOW_HOURS
    print("Actual data shape, Predicted data shape: ", scaledActual.shape, scaledPredicted.shape)

    mse = tf.keras.losses.MeanSquaredError()
    rmseScore = round(math.sqrt(mse(scaledActual, scaledPredicted).numpy()), 6)

    unscaledRMSEScore = round(math.sqrt(mse(unscaledActual, unscaledPredicted).numpy()), 6)
    print("***** Unscaled RMSE: ", unscaledRMSEScore)

    mape = tf.keras.losses.MeanAbsolutePercentageError()

    rows, cols = len(unscaledActual)//PREDICTION_WINDOW_HOURS, PREDICTION_WINDOW_HOURS//24
    dailyMapeScore = np.zeros((rows, cols))

    # for i in range(len(unscaledActual)):
    #     print(unscaledActual[i], unscaledPredicted[i])

    outlierDays = {}
    for i in range(0, len(unscaledActual), PREDICTION_WINDOW_HOURS):
        for j in range(0, PREDICTION_WINDOW_HOURS, 24):
            mapeTensor =  mape(unscaledActual[i+j:i+j+24], unscaledPredicted[i+j:i+j+24])
            mapeScore = mapeTensor.numpy()
            # print("Day: ", dates[i], "MAPE: ", mapeScore)
            # if(mapeScore>15):
            #     # for j in range(24):
            #     #     print(unscaledActual[i+j], unscaledPredicted[i+j])
            #     outlierDays[dates[i]] = mapeScore
            dailyMapeScore[i//PREDICTION_WINDOW_HOURS][j//24] = mapeScore
    
    # outlierDays = sorted(outlierDays.items(), key=lambda x: x[1], reverse=True)
    # for k,v in outlierDays: # Printing outlier days
    #     print(k,": ", v)


    mapeTensor =  mape(unscaledActual, unscaledPredicted)
    mapeScore = mapeTensor.numpy()

    return rmseScore, mapeScore, dailyMapeScore

def getHyperParams(secondTierConfig):
    hyperParams = {}
    modelHyperparamsFromConfigFile = secondTierConfig["SECOND_TIER_CNN_LSTM_MODEL_HYPERPARAMS"]
    hyperParams["epoch"] = modelHyperparamsFromConfigFile["EPOCH"]
    hyperParams["batchsize"] = modelHyperparamsFromConfigFile["BATCH_SIZE"]
    hyperParams["actv"] = modelHyperparamsFromConfigFile["ACTIVATION_FUNC"]
    hyperParams["loss"] = modelHyperparamsFromConfigFile["LOSS_FUNC"]
    hyperParams["lr"] = modelHyperparamsFromConfigFile["LEARNING_RATE"]
    hyperParams["minlr"] = modelHyperparamsFromConfigFile["MIN_LEARNING_RATE"]

    hyperParams["kernel1"] = modelHyperparamsFromConfigFile["CNN_KERNEL1"] # 4
    hyperParams["kernel2"] = modelHyperparamsFromConfigFile["CNN_KERNEL2"] # 4
    hyperParams["filter1"] = modelHyperparamsFromConfigFile["CNN_NUM_FILTERS1"] # 4
    hyperParams["filter2"] = modelHyperparamsFromConfigFile["CNN_NUM_FILTERS2"] # 16
    hyperParams["poolsize"] = modelHyperparamsFromConfigFile["CNN_POOL_SIZE"] # 2

    hyperParams["dropoutRate"] = modelHyperparamsFromConfigFile["LSTM_DROPOUT_RATE"] # 2


    return hyperParams

def fillMissingData(data): # If some data is missing (NaN), use the same value as that of the previous row
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if(np.isnan(data[i, j])):
                data[i, j] = data[i-1, j]
    return data

def trainingandValidationPhase(region, trainData, wTrainData, valData, wValData, secondTierConfig, 
                               exptNum, loadFromSavedModel):
    global TRAINING_WINDOW_HOURS

    print("\nManipulating training data...")
    X, y = manipulateTrainingDataShape(trainData, TRAINING_WINDOW_HOURS, TRAINING_WINDOW_HOURS, wTrainData)
    # Next line actually labels validation data
    valX, valY = manipulateTrainingDataShape(valData, TRAINING_WINDOW_HOURS, TRAINING_WINDOW_HOURS, wValData)
    print("***** Training data manipulation done *****")
    print("X.shape, y.shape: ", X.shape, y.shape)

    hyperParams = getHyperParams(secondTierConfig)
    print("\n[BESTMODEL] Starting training...")
    bestTrainedModel, numFeatures = trainModel(X, y, valX, valY, hyperParams, exptNum, region, loadFromSavedModel)
    print("***** Training done *****")
    return bestTrainedModel, numFeatures

def getUnscaledForecastsAndForecastAccuracy(testData, testDates, predictedData, ftMin, ftMax):
    global MODEL_SLIDING_WINDOW_LEN
    global PREDICTION_WINDOW_HOURS

    actualData = manipulateTestDataShape(testData[:, DEPENDENT_VARIABLE_COL], 
            MODEL_SLIDING_WINDOW_LEN, PREDICTION_WINDOW_HOURS, False)
    formattedTestDates = manipulateTestDataShape(testDates, 
            MODEL_SLIDING_WINDOW_LEN, PREDICTION_WINDOW_HOURS, True)
    formattedTestDates = np.reshape(formattedTestDates, 
            formattedTestDates.shape[0]*formattedTestDates.shape[1])
    actualData = actualData.astype(np.float64)
    print("ActualData shape: ", actualData.shape)
    actual = np.reshape(actualData, actualData.shape[0]*actualData.shape[1])
    predictedData = predictedData.astype(np.float64)
    predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
    unscaledPredictedData = common.inverseDataScaling(predicted, ftMax[DEPENDENT_VARIABLE_COL], 
                        ftMin[DEPENDENT_VARIABLE_COL])
    unscaledTestData = common.inverseDataScaling(actual, ftMax[DEPENDENT_VARIABLE_COL], 
                        ftMin[DEPENDENT_VARIABLE_COL])
    print(actualData.shape, predictedData.shape, unscaledTestData.shape, unscaledPredictedData.shape)
    rmseScore, mapeScore, dailyMapeScore = getScores(actualData, predictedData, 
                                unscaledTestData, unscaledPredictedData, testDates)   
   
    return unscaledTestData, unscaledPredictedData, formattedTestDates, rmseScore, mapeScore, dailyMapeScore

def writeRealTimeCIForecastsToFile(formattedTestDates, unscaledPredictedData, outFileName):
    data = []
    for i in range(len(unscaledPredictedData)):
        row = []
        row.append(str(formattedTestDates[i]))
        row.append(str(unscaledPredictedData[i]))
        data.append(row)
    writeMode = "w"
    print("Writing to ", outFileName, "...")
    fields = ["UTC time", "forecasted_avg_carbon_intensity"]
    
    with open(outFileName, writeMode) as csvfile: 
        csvwriter = csv.writer(csvfile)   
        csvwriter.writerow(fields) 
        csvwriter.writerows(data)
    return

if __name__ == "__main__":
    print("CarbonCast second tier. Refer github repo for regions & sources.")
    loadFromSavedModel = False
    if (len(sys.argv) < 3):
        print("Usage: python3 secondTierForecasts.py <configFileName> <-l (lifecycle)/ -d (direct)> <-s>")
        print("-s is optional. If provided, CarbonCast will load an already saved model.")
        print("Otherwise, CarbonCast will train the second tier model.")
        print("")
        exit(0)
    else:
        if (len(sys.argv) == 4 and sys.argv[3] == "-s"):
            loadFromSavedModel = True
    configFileName = sys.argv[1]
    cefType = sys.argv[2]
    
    runSecondTier(configFileName, cefType, loadFromSavedModel)
    print("End")