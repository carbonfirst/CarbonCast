import csv
from ctypes.wintypes import tagRECT
import math
from datetime import datetime as dt
from datetime import timezone as tz

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pmdarima as pm
import pytz as pytz
import seaborn as sns
from keras.layers import Dense, Flatten
from keras.layers import LSTM
from keras.layers.convolutional import AveragePooling1D, Conv1D, MaxPooling1D
from keras.layers.normalization.batch_normalization import BatchNormalization
from keras.models import Sequential
from scipy.sparse import data
from sklearn.utils import validation
from statsmodels.tsa.arima_model import ARIMA
from statsmodels.tsa.stattools import adfuller
import tensorflow as tf
from tensorflow import keras
from keras.callbacks import EarlyStopping
from keras.callbacks import ModelCheckpoint
from keras.models import load_model
from keras.layers import RepeatVector

import common


############################# MACRO START #######################################
print("Start")
# ISO_LIST = ["CISO", "ERCO", "ISNE", "PJM"]
# ISO_LIST = ["DE", "SE", "ISNE", "PJM"]
ISO_LIST = ["CISO", "ERCO"]

LOCAL_TIMEZONES = {"CISO": "US/Pacific", "ERCO": "US/Central", "ISNE": "US/Eastern", 
                    "PJM": "US/Eastern", "SE": "CET", "GB": "UTC", "DE": "CET"}
IN_FILE_NAME = None
OUT_FILE_NAME = None
LOCAL_TIMEZONE = None
PLOT_TITLE = None

BUFFER = -1
COAL = 3
NAT_GAS = 4
NUCLEAR = 5
OIL = 6
HYDRO = 7
SOLAR = 8
WIND = 9
OTHER = 10
DEMAND = 11

BIOMASS = 2
GEOTHERMAL = 5
UNKNOWN = 11

BIOMASS_GB = 2
HYDRO_GB = 3
COAL_GB = 4
NAT_GAS_GB = 5
NUCLEAR_GB = 6
UNKNOWN_GB = 7
WIND_GB = 8
SOLAR_GB = 9

BIOMASS_DE = 2
COAL_DE = 3
NAT_GAS_DE = 4
GEOTHERMAL_DE = 5
HYDRO_DE = 6
NUCLEAR_DE = 7
OIL_DE = 8
SOLAR_DE = 9
WIND_DE = 10
UNKNOWN_DE = 11

NUCLEAR_SE = 3
UNKNOWN_SE = 4
HYDRO_SE = 6
WIND_SE = 5

IS_RENEWABLE_SOURCE = False
FORECASTS_ONE_DAY_AT_A_TIME = True
PARTIAL_FORECAST_AVAILABLE = True # currently taking previously generated DA forecasts/ already available DA forecasts for day 1
PARTIAL_FORECAST_HOURS = 24
NUM_VAL_DAYS = 30
NUM_TEST_DAYS = 184
TRAINING_WINDOW_HOURS = 96
if (FORECASTS_ONE_DAY_AT_A_TIME is True):
    TRAINING_WINDOW_HOURS = 24
PREDICTION_WINDOW_HOURS = 96
MODEL_SLIDING_WINDOW_LEN = 24
BUFFER_HOURS = PREDICTION_WINDOW_HOURS - 24
DAY_INTERVAL = 1
MONTH_INTERVAL = 1
CARBON_INTENSITY_COL = 0
WEATHER_FEATURES = 0

NUMBER_OF_EXPERIMENTS = 1
# global NUCLEAR, COAL, SOLAR, WIND, NAT_GAS, GEOTHERMAL, HYDRO, UNKNOWN, BIOMASS, OIL

# NUM_FEATURES = 6
NUM_FEATURES_DICT = {"coal":6, "nat_gas":6, "nuclear":6, "oil":6, "hydro":11, "solar": 11,
                    "wind":11, "other":6, "unknown": 6, "biomass": 6, "geothermal":6, "demand":6}


# if (IS_RENEWABLE_SOURCE and START_COL != HYDRO):
#     PARTIAL_FORECAST_AVAILABLE = True # dip: make it inside indentation later

# if (START_COL == DEMAND):
#     PARTIAL_FORECAST_AVAILABLE = True

############################# MACRO END #########################################

def initialize(inFileName, weatherForecastInFileName, startCol):
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])

    # print(dataset.head())
    # print(dataset.columns)
    dateTime = dataset.index.values

    weatherDataset = pd.read_csv(weatherForecastInFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])
    # print(weatherDataset.head())
    
    print("\nAdding features related to date & time...")
    modifiedDataset = common.addDateTimeFeatures(dataset, dateTime, startCol)
    dataset = modifiedDataset
    print("Features related to date & time added")

    bufferPeriod = dataset[DATASET_LIMITER:DATASET_LIMITER+BUFFER_HOURS]
    dataset = dataset[:DATASET_LIMITER]
    bufferDates = dateTime[DATASET_LIMITER:DATASET_LIMITER+BUFFER_HOURS]
    dateTime = dateTime[:DATASET_LIMITER]

    weatherDataset = weatherDataset[:WEATHER_DATASET_LIMITER]
    
    for i in range(startCol, len(dataset.columns.values)):
        col = dataset.columns.values[i]
        dataset[col] = dataset[col].astype(np.float64)
        # print(col, dataset[col].dtype)

    # print("Getting contribution of each energy source...")
    # contribution = getAvgContributionBySource(dataset)
    # print(contribution)

    return dataset, dateTime, bufferPeriod, bufferDates, weatherDataset

# convert training data into inputs and outputs (labels)
def manipulateTrainingDataShape(data, trainWindowHours, labelWindowHours, weatherData = None): 
    print("Data shape: ", data.shape)
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
        if(weatherData is not None):
            weatherX.append(weatherData[weatherIdx:weatherIdx+trainWindowHours])
            weatherIdx +=1
            hourIdx +=1
            if(hourIdx ==24):
                hourIdx = 0
                weatherIdx += (PREDICTION_WINDOW_HOURS-24)
        y.append(data[trainWindow:labelWindow, CARBON_INTENSITY_COL])
    X = np.array(X, dtype=np.float64)
    y = np.array(y, dtype=np.float64)
    if(weatherData is not None):
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


def trainANN(trainX, trainY, valX, valY, hyperParams):
    n_timesteps, n_features, n_outputs = trainX.shape[1], trainX.shape[2], trainY.shape[1]
    epochs = hyperParams['epoch']
    batchSize = hyperParams['batchsize']
    kernelSize = hyperParams['kernel']
    numFilters = hyperParams['filter']
    activationFunc = hyperParams['actv']
    lossFunc = hyperParams['loss']
    optimizer = hyperParams['optim']
    poolSize = hyperParams['poolsize']
    hiddenDims = hyperParams['hidden']
    hd = hiddenDims[0]
    learningRates = hyperParams['lr']
    model = Sequential()
    model.add(Flatten())
    model.add(Dense(50, input_shape=(n_timesteps, n_features), activation='relu')) # 20 for coal, nat_gas, nuclear
    model.add(Dense(34, activation='relu')) # 50 for coal, nat_gas, nuclear
    model.add(Dense(n_outputs))
    # model.add(Conv1D(filters=4, kernel_size=4, padding="same",
    #         activation="relu", input_shape=(n_timesteps,n_features)))
       
    # model.add(Flatten())
    # model.add(RepeatVector(n_outputs))
    # model.add(LSTM(n_outputs, activation="sigmoid"))
    # model.add(Dense(n_outputs))
    opt = tf.keras.optimizers.Adam(learning_rate = 0.01)
    model.compile(loss=lossFunc, optimizer=opt,
                    metrics=['mean_absolute_error'])
    es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=10)
    mc = ModelCheckpoint('best_model_ann.h5', monitor='val_loss', mode='min', verbose=1, save_best_only=True)
    # fit network
    # hist = model.fit(trainX, trainY, epochs=epochs, batch_size=bSize, verbose=verbose)
    hist = model.fit(trainX, trainY, epochs=epochs, batch_size=batchSize[0], verbose=2,
                        validation_data=(valX, valY), callbacks=[es, mc])
    model = load_model("best_model_ann.h5")
    common.showModelSummary(hist, model)
    print("Number of features used in training: ", n_features)
    return model, n_features



# walk-forward validation
def getOneShotForecasts(trainX, trainY, model, history, testData, trainWindowHours, 
            numFeatures, wTestData = None, weatherData = None, partialSourceProductionForecast = None):
    global MODEL_SLIDING_WINDOW_LEN
    global BUFFER_HOURS
    # walk-forward validation over each day
    print("Testing (one shot forecasts)...")
    predictions = list()
    weatherIdx = 0
    for i in range(0, ((len(testData)//24)-(BUFFER_HOURS//24))):
        # predict n days in one shot
        yhat_sequence, newTrainingData = getForecasts(model, history, trainWindowHours, numFeatures, weatherData)
        predictions.append(yhat_sequence)
        # get real observation and add to history for predicting the next day
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
        if (wTestData is not None):
            weatherData = wTestData[weatherIdx:weatherIdx+trainWindowHours, :]
            weatherIdx +=trainWindowHours
        history.extend(testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN, :].tolist())
        newLabel = testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN,0].reshape(1, MODEL_SLIDING_WINDOW_LEN)
        np.append(trainX, newTrainingData)
        np.append(trainY, newLabel)

        valX = trainX[-(NUM_VAL_DAYS*TRAINING_WINDOW_HOURS):]
        trainX = trainX[:-(NUM_VAL_DAYS*TRAINING_WINDOW_HOURS)]
        valY = trainY[-(NUM_VAL_DAYS*TRAINING_WINDOW_HOURS):]
        trainY = trainY[:-(NUM_VAL_DAYS*TRAINING_WINDOW_HOURS)]

    # evaluate predictions days for each day
    predictedData = np.array(predictions, dtype=np.float64)
    return predictedData

def getDayAheadForecasts(trainX, trainY, model, history, testData, 
                            trainWindowHours, numFeatures, depVarColumn,
                            wTestData = None, weatherData = None, 
                            partialSourceProductionForecast = None):
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
                            trainWindowHours, numFeatures, weatherData[j:j+24])
            else:
                yhat_sequence, newTrainingData = getForecasts(model, tempHistory, 
                            trainWindowHours, numFeatures, None)
            # add current prediction to history for predicting the next day
            if (j==0 and partialSourceProductionForecast is not None):
                for k in range(24):
                    yhat_sequence[k] = partialSourceProductionForecast[currentDayHours+k]
            dayAheadPredictions.extend(yhat_sequence)
            latestHistory = testData[currentDayHours+j:currentDayHours+j+24, :].tolist()
            for k in range(24):
                latestHistory[k][depVarColumn] = yhat_sequence[k]
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


def getForecasts(model, history, trainWindowHours, numFeatures, weatherData):
    # flatten data
    data = np.array(history, dtype=np.float64)
    # retrieve last observations for input data
    input_x = data[-trainWindowHours:]
    if (weatherData is not None):
        # print(input_x.shape, weatherData.shape)
        input_x = np.append(input_x, weatherData, axis=1)
        # print("inputX shape, numFeatures: ", input_x.shape, numFeatures)
    # reshape into [1, n_input, num_features]
    input_x = input_x.reshape((1, len(input_x), numFeatures))
    # print("ip_x shape: ", input_x.shape)
    yhat = model.predict(input_x, verbose=0)
    # we only want the vector forecast
    yhat = yhat[0]
    return yhat, input_x

def getANNHyperParams():
    hyperParams = {}
    hyperParams['epoch'] = 100 # DIP
    hyperParams['batchsize'] = [10] # 10 for coal, nuclear, nat_gas
    hyperParams['kernel'] = [3] #[3, 4, 5] #[3, 6, 10]
    hyperParams['filter'] = [64] #, 32, 16] #[64, 32, 16]
    hyperParams['poolsize'] = 2
    hyperParams['actv'] = "relu"
    hyperParams['loss'] = "mse"
    hyperParams['optim'] = ["adam"] #, "rmsprop"]
    hyperParams['lr'] = [1e-2, 1e-3]
    hyperParams['hidden'] = [[100, 100]] #, [50, 50]]#, [20, 50]] #, [50, 50]]
    return hyperParams

#Start of execution
rmse = {}
isoIdx = 0

# WIND_DE, COAL_DE, NAT_GAS_DE, GEOTHERMAL_DE, HYDRO_DE, NUCLEAR_DE, OIL_DE, SOLAR_DE, UNKNOWN_DE, BIOMASS_DE,
SOURCE_LIST = [
                # WIND_DE, COAL_DE, NAT_GAS_DE, GEOTHERMAL_DE, HYDRO_DE, NUCLEAR_DE, OIL_DE, SOLAR_DE, UNKNOWN_DE, BIOMASS_DE,
                # BUFFER,
                # NUCLEAR_SE, UNKNOWN_SE, HYDRO_SE, WIND_SE,
                # BUFFER,
                # COAL, NAT_GAS, NUCLEAR, OIL, HYDRO, SOLAR, WIND, OTHER,
                # BUFFER,
                # COAL, NAT_GAS, NUCLEAR, OIL, HYDRO, SOLAR, WIND, OTHER,
                # BUFFER,
                # COAL, NAT_GAS, NUCLEAR, OIL, HYDRO, SOLAR, WIND, OTHER,
                WIND, OTHER,
                BUFFER,
                COAL, NAT_GAS, NUCLEAR, HYDRO, SOLAR, WIND, OTHER,
                ]

for SOURCE in SOURCE_LIST:
    if (SOURCE == BUFFER):
        isoIdx +=1
        continue
    ISO = ISO_LIST[isoIdx]

    if (ISO == "SE"):
        FUEL = {3:"nuclear", 4:"unknown", 5:"wind", 6:"hydro"} # SE
    elif (ISO == "GB"):
        FUEL = {2:"biomass", 3:"hydro", 4:"coal", 5:"nat_gas", 6:"nuclear", 7:"unknown",
                        8:"wind", 9:"solar"} # GB
    elif (ISO == "DE"):        
        FUEL = {2:"biomass", 3:"coal", 4:"nat_gas", 5:"geothermal", 6:"hydro", 7:"nuclear",
                        8:"oil", 9:"solar", 10:"wind", 11:"unknown"} # DE
    else:
        FUEL = {3:"coal", 4:"nat_gas", 5:"nuclear", 6:"oil", 7:"hydro", 8:"solar",
                    9:"wind", 10:"other", 11:"demand"}
    

    START_COL = SOURCE
    print(isoIdx, ISO, START_COL)

    NUM_FEATURES = NUM_FEATURES_DICT[FUEL[START_COL]]
    if (((START_COL == SOLAR_DE or START_COL == WIND_DE or START_COL == HYDRO_DE) and ISO == "DE") or
        ((START_COL == WIND_SE or START_COL == HYDRO_SE) and ISO == "SE") or 
        START_COL == SOLAR or START_COL == WIND or START_COL == HYDRO):
        WEATHER_FEATURES = 5
        NUM_FEATURES -=WEATHER_FEATURES
        IS_RENEWABLE_SOURCE = True

    # IN_FILE_NAME = "../final_weather_data/"+ISO+"/fuel_forecast/"+ISO+"_"+FUEL[START_COL]+"_2019_clean.csv"
    # OUT_FILE_NAME_PREFIX = "../final_weather_data/"+ISO+"/fuel_forecast/"+ISO+"_NR_Forecast"
    IN_FILE_NAME = "../extn/"+ISO+"/fuel_forecast/"+ISO+"_"+FUEL[START_COL]+"_2019_clean.csv"
    WEATHER_FORECAST_IN_FILE_NAME = "../extn/"+ISO+"/"+ISO+"_weather_forecast.csv"
    # OUT_FILE_NAME_PREFIX = "../extn/"+ISO+"/fuel_forecast/"+ISO+"_"+str(PREDICTION_WINDOW_HOURS)+"_hr_src_prod_forecast"
    OUT_FILE_NAME_PREFIX = "../extn/"+ISO+"/fuel_forecast/"+ISO+"_ANN_"
    if(FORECASTS_ONE_DAY_AT_A_TIME is True):
        OUT_FILE_NAME_PREFIX = OUT_FILE_NAME_PREFIX + "_DA"

    print(IN_FILE_NAME)
    
    LOCAL_TIMEZONE = pytz.timezone(LOCAL_TIMEZONES[ISO])
    if ISO == "SE":
        PLOT_TITLE = "SWEDEN"
        # IN_FILE_NAME = "SE_2020_filled.csv"
        # OUT_FILE_NAME = "SE_Forecast_nFeat.csv"
        # LOCAL_TIMEZONE = pytz.timezone("CET")

    periodRMSE, periodMAPE = [], []
    for period in range(4):

        ########################################################################
        #### Train - Jan - Dec 2019, Test - Jan - Jun 2020 ####
        if (period == 0):
            DATASET_LIMITER = 13128
            OUT_FILE_SUFFIX = "h1_2020"
            NUM_TEST_DAYS = 182
        #### Train - Jan 2019 - Jun 2020, Test - Jul - Dec 2020 ####
        if (period == 1):
            DATASET_LIMITER = 17544
            OUT_FILE_SUFFIX = "h2_2020"
            NUM_TEST_DAYS = 184
        #### Train - Jan 2020 - Dec 2020, Test - Jan - Jun 2021 ####
        if (period == 2):
            DATASET_LIMITER = 21888
            OUT_FILE_SUFFIX = "h1_2021"
            NUM_TEST_DAYS = 181
        #### Train - Jan 2020 - Jun 2021, Test - Jul - Dec 2021 ####
        if (period == 3):
            DATASET_LIMITER = 26304
            OUT_FILE_SUFFIX = "h2_2021"
            NUM_TEST_DAYS = 184
        ########################################################################
        WEATHER_DATASET_LIMITER = DATASET_LIMITER//24*PREDICTION_WINDOW_HOURS

        print("Initializing...")
        dataset, dateTime, bufferPeriod, bufferDates, weatherDataset = initialize(
                    IN_FILE_NAME, WEATHER_FORECAST_IN_FILE_NAME, START_COL)
        # bufferPeriod is for the last test date, if prediction period is beyond 24 hours
        print("***** Initialization done *****")

        # split into train and test
        print("Spliting dataset into train/test...")
        trainData, valData, testData, fullTrainData = common.splitDataset(dataset.values, NUM_TEST_DAYS, 
                                                NUM_VAL_DAYS)
        trainDates = dateTime[: -(NUM_TEST_DAYS*24)]
        fullTrainDates = np.copy(trainDates)
        trainDates, validationDates = trainDates[: -(NUM_VAL_DAYS*24)], trainDates[-(NUM_VAL_DAYS*24):]
        testDates = dateTime[-(NUM_TEST_DAYS*24):]
        bufferPeriod = bufferPeriod.values
        trainData = trainData[:, START_COL: START_COL+NUM_FEATURES]
        valData = valData[:, START_COL: START_COL+NUM_FEATURES]
        testData = testData[:, START_COL: START_COL+NUM_FEATURES]
        partialSourceProductionForecast = None
        if (PARTIAL_FORECAST_AVAILABLE):
            if (ISO == "DE"):
                if (START_COL == SOLAR_DE):
                    partialSourceProductionForecast = dataset["avg_solar_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == WIND_DE):
                    partialSourceProductionForecast = dataset["avg_wind_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == NAT_GAS_DE):
                    partialSourceProductionForecast = dataset["avg_nat_gas_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == NUCLEAR_DE):
                    partialSourceProductionForecast = dataset["avg_nuclear_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == COAL_DE):
                    partialSourceProductionForecast = dataset["avg_coal_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                # elif (START_COL == DEMAND):
                #     partialSourceProductionForecast = dataset["avg_demand_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == BIOMASS_DE):
                    partialSourceProductionForecast = dataset["avg_biomass_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == GEOTHERMAL_DE):
                    partialSourceProductionForecast = dataset["avg_geothermal_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == OIL_DE):
                    partialSourceProductionForecast = dataset["avg_oil_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == UNKNOWN_DE):
                    partialSourceProductionForecast = dataset["avg_unknown_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == HYDRO_DE):
                    partialSourceProductionForecast = dataset["avg_hydro_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
            elif (ISO == "SE"):
                if (START_COL == WIND_SE):
                    partialSourceProductionForecast = dataset["avg_wind_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == NUCLEAR_SE):
                    partialSourceProductionForecast = dataset["avg_nuclear_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                # elif (START_COL == DEMAND):
                #     partialSourceProductionForecast = dataset["avg_demand_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == UNKNOWN_SE):
                    partialSourceProductionForecast = dataset["avg_unknown_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == HYDRO_SE):
                    partialSourceProductionForecast = dataset["avg_hydro_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
            else:
                if (START_COL == SOLAR):
                    partialSourceProductionForecast = dataset["avg_solar_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == WIND):
                    partialSourceProductionForecast = dataset["avg_wind_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == NAT_GAS):
                    partialSourceProductionForecast = dataset["avg_nat_gas_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == NUCLEAR):
                    partialSourceProductionForecast = dataset["avg_nuclear_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == COAL):
                    partialSourceProductionForecast = dataset["avg_coal_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                # elif (START_COL == DEMAND):
                #     partialSourceProductionForecast = dataset["avg_demand_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == OTHER):
                    partialSourceProductionForecast = dataset["avg_other_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == OIL):
                    partialSourceProductionForecast = dataset["avg_oil_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == UNKNOWN):
                    partialSourceProductionForecast = dataset["avg_unknown_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values
                elif (START_COL == HYDRO):
                    partialSourceProductionForecast = dataset["avg_hydro_production_forecast"].iloc[-NUM_TEST_DAYS*24:].values

        bufferPeriod = bufferPeriod[:, START_COL: START_COL+NUM_FEATURES]
        if(len(bufferDates)>0):
            testDates = np.append(testDates, bufferDates)
            testData = np.vstack((testData, bufferPeriod))

        print("TrainData shape: ", trainData.shape) # (days x hour) x features
        print("ValData shape: ", valData.shape) # (days x hour) x features
        print("TestData shape: ", testData.shape) # (days x hour) x features

        wTrainData, wValData, wTestData, wFullTrainData = None, None, None, None
        if (IS_RENEWABLE_SOURCE):
            wTrainData, wValData, wTestData, wFullTrainData = common.splitWeatherDataset(
                    weatherDataset.values, NUM_TEST_DAYS, NUM_VAL_DAYS, PREDICTION_WINDOW_HOURS)
            print("WeatherTrainData shape: ", wTrainData.shape) # (days x hour) x features
            print("WeatherValData shape: ", wValData.shape) # (days x hour) x features
            print("WeatherTestData shape: ", wTestData.shape) # (days x hour) x features

        print("***** Dataset split done *****")

        for i in range(trainData.shape[0]):
            for j in range(trainData.shape[1]):
                if(np.isnan(trainData[i, j])):
                    trainData[i, j] = trainData[i-1, j]

        for i in range(valData.shape[0]):
            for j in range(valData.shape[1]):
                if(np.isnan(valData[i, j])):
                    valData[i, j] = valData[i-1, j]

        for i in range(testData.shape[0]):
            for j in range(testData.shape[1]):
                if(np.isnan(testData[i, j])):
                    testData[i, j] = testData[i-1, j]

        if(IS_RENEWABLE_SOURCE):
            for i in range(wTrainData.shape[0]):
                for j in range(wTrainData.shape[1]):
                    if(np.isnan(wTrainData[i, j])):
                        wTrainData[i, j] = wTrainData[i-1, j]

            for i in range(wValData.shape[0]):
                for j in range(wValData.shape[1]):
                    if(np.isnan(wValData[i, j])):
                        wValData[i, j] = wValData[i-1, j]

            for i in range(wTestData.shape[0]):
                for j in range(wTestData.shape[1]):
                    if(np.isnan(wTestData[i, j])):
                        wTestData[i, j] = wTestData[i-1, j]

        featureList = dataset.columns.values
        featureList = featureList[START_COL:START_COL+NUM_FEATURES].tolist()
        if (IS_RENEWABLE_SOURCE):
            featureList.extend(weatherDataset.columns.values)
        # OUT_FILE_NAME = OUT_FILE_NAME_PREFIX + "_" + featureList[0] + OUT_FILE_SUFFIX + ".csv"
        OUT_FILE_NAME = OUT_FILE_NAME_PREFIX + "_" + featureList[0] + ".csv"
        print("Features: ", featureList)

        print("Scaling data...")
        # unscaledTestData = np.zeros(testData.shape[0])
        # for i in range(testData.shape[0]):
        #     unscaledTestData[i] = testData[i, CARBON_INTENSITY_COL]
        trainData, valData, testData, ftMin, ftMax = common.scaleDataset(trainData, valData, testData)
        print(trainData.shape, valData.shape, testData.shape)
        if (IS_RENEWABLE_SOURCE):
            wTrainData, wValData, wTestData, wFtMin, wFtMax = common.scaleDataset(wTrainData, wValData, wTestData)
            print(wTrainData.shape, wValData.shape, wTestData.shape)
        if (PARTIAL_FORECAST_AVAILABLE):
                partialSourceProductionForecast = common.scaleColumn(partialSourceProductionForecast, 
                        ftMin[CARBON_INTENSITY_COL], ftMax[CARBON_INTENSITY_COL])
                print(partialSourceProductionForecast, ftMax[CARBON_INTENSITY_COL], ftMin[CARBON_INTENSITY_COL])
        print("***** Data scaling done *****")
        print("\nManipulating training data...")
        if (FORECASTS_ONE_DAY_AT_A_TIME is True):
            # [DIP] TODO: Check how to decouple dataset in this case
            X, y = manipulateTrainingDataShape(trainData, TRAINING_WINDOW_HOURS, TRAINING_WINDOW_HOURS, wTrainData)
            # Next line actually labels validation data
            valX, valY = manipulateTrainingDataShape(valData, TRAINING_WINDOW_HOURS, TRAINING_WINDOW_HOURS, wValData)
        else:
            # [DIP] TODO: Check correctness in this case
            X, y = manipulateTrainingDataShape(trainData, TRAINING_WINDOW_HOURS, 
                    PREDICTION_WINDOW_HOURS, wTrainData)
            # Next line actually labels validation data
            valX, valY = manipulateTrainingDataShape(valData, TRAINING_WINDOW_HOURS, 
                    PREDICTION_WINDOW_HOURS, wValData)
                                        
        print("***** Training data manipulation done *****")
        print("X.shape, y.shape: ", X.shape, y.shape)

        ######################## START #####################

        idx = 0
        baselineRMSE, baselineMAPE = [], []
        bestRMSE, bestMAPE = [], []
        predictedData = None
        
        hyperParams = getANNHyperParams()

        for xx in range(NUMBER_OF_EXPERIMENTS):
            print("\n[BESTMODEL] Starting training...")
            bestModel, numFeatures = trainANN(X, y, valX, valY, hyperParams)
            print("***** Training done *****")
            history = valData[-TRAINING_WINDOW_HOURS:, :]
            weatherData = None
            if (IS_RENEWABLE_SOURCE):
                weatherData = wValData[-PREDICTION_WINDOW_HOURS:, :]
                print("weatherData shape:", weatherData.shape)
            history = history.tolist()

            if (FORECASTS_ONE_DAY_AT_A_TIME is True):
                predictedData = getDayAheadForecasts(X, y, bestModel, history, testData, 
                                    TRAINING_WINDOW_HOURS, numFeatures, CARBON_INTENSITY_COL,
                                    wTestData, weatherData, partialSourceProductionForecast)
            else:
                predictedData = getOneShotForecasts(X, y, bestModel, history, testData, 
                                    TRAINING_WINDOW_HOURS, numFeatures, wTestData, weatherData,
                                    partialSourceProductionForecast)
            
            actualData = manipulateTestDataShape(testData[:, CARBON_INTENSITY_COL], 
                    MODEL_SLIDING_WINDOW_LEN, PREDICTION_WINDOW_HOURS, False)
            formattedTestDates = manipulateTestDataShape(testDates, 
                    MODEL_SLIDING_WINDOW_LEN, PREDICTION_WINDOW_HOURS, True)
            formattedTestDates = np.reshape(formattedTestDates, 
                    formattedTestDates.shape[0]*formattedTestDates.shape[1])
            actualData = actualData.astype(np.float64)
            print("ActualData shape: ", actualData.shape)
            actual = np.reshape(actualData, actualData.shape[0]*actualData.shape[1])
            print("actual.shape: ", actual.shape)
            unscaledTestData = common.inverseDataScaling(actual, ftMax[CARBON_INTENSITY_COL], 
                                ftMin[CARBON_INTENSITY_COL])
            predictedData = predictedData.astype(np.float64)
            print("PredictedData shape: ", predictedData.shape)
            predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
            print("predicted.shape: ", predicted.shape)
            unScaledPredictedData = common.inverseDataScaling(predicted, 
                        ftMax[CARBON_INTENSITY_COL], ftMin[CARBON_INTENSITY_COL])
            rmseScore, mapeScore = common.getScores(actualData, predictedData, 
                                        unscaledTestData, unScaledPredictedData)
            print("***** Forecast done *****")
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
        ######################## END #####################

        data = []
        for i in range(len(unScaledPredictedData)):
            row = []
            row.append(str(formattedTestDates[i]))
            row.append(str(unscaledTestData[i]))
            row.append(str(unScaledPredictedData[i]))
            data.append(row)
        writeMode = "w"
        if (period > 0):
            writeMode = "a"
        common.writeOutFile(OUT_FILE_NAME, data, featureList[0], writeMode)

    # plotTitle = PLOT_TITLE + "_" + str(featureList[0])
    # plotBaseline = False

    # actual = np.reshape(actualData, actualData.shape[0]*actualData.shape[1])
    # predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
    # unScaledPredictedData = inverseDataNormalization(predicted, ftMax[CARBON_INTENSITY_COL], 
    #                         ftMin[CARBON_INTENSITY_COL])

    print("RMSE: ", periodRMSE)
    print("MAPE: ", periodMAPE)
    print("####################", ISO, SOURCE, " done ####################\n\n")

print("End")
