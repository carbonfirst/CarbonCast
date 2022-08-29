import csv
import math
from datetime import datetime as dt
from datetime import timezone as tz

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz as pytz
import seaborn as sns
from keras import metrics, optimizers, regularizers
from keras.initializers import initializers_v2
from keras.layers import Dense, Flatten, LSTM
from keras.layers.convolutional import AveragePooling1D, Conv1D, MaxPooling1D, Conv2D
from keras.layers.core import Activation, Dropout
from keras.layers.normalization.batch_normalization import BatchNormalization
from keras.models import Sequential
from statsmodels.tsa.stattools import adfuller
import tensorflow as tf
from keras.callbacks import EarlyStopping
from keras.callbacks import ModelCheckpoint, ReduceLROnPlateau
from keras.models import load_model, save_model
from keras.layers import RepeatVector
from keras.layers import TimeDistributed
import keras_tuner as kt

import shap
import json5 as json

import common
import utility


# [DM] Sweden "unknown" carbon emission factor is different. Refer electricityMap github for details
# Change later

############################# MACRO START #######################################
# Multivariate multi-step time series forecasting
print("Start")
configurationData = {}

with open("config.json", "r") as configFile:
    configurationData = json.load(configFile)
    # print(configurationData)

ISO_LIST = configurationData["ISO_LIST"]

NUM_TEST_DAYS = configurationData["NUM_TEST_DAYS"] # last 6 months of 2021
NUM_VAL_DAYS = configurationData["NUM_VAL_DAYS"] # first 6 months of 2021
TRAINING_WINDOW_HOURS = configurationData["TRAINING_WINDOW_HOURS"]
MODEL_SLIDING_WINDOW_LEN = configurationData["MODEL_SLIDING_WINDOW_LEN"]
PREDICTION_WINDOW_HOURS = configurationData["PREDICTION_WINDOW_HOURS"]
MAX_PREDICTION_WINDOW_HOURS = configurationData["MAX_PREDICTION_WINDOW_HOURS"]
TOP_N_FEATURES = configurationData["TOP_N_FEATURES"]
DAY_INTERVAL = 1
MONTH_INTERVAL = 1
CARBON_INTENSITY_COL = 0
NUMBER_OF_EXPERIMENTS = configurationData["NUMBER_OF_EXPERIMENTS_PER_ISO"]

FORECASTS_ONE_DAY_AT_A_TIME = True
if (FORECASTS_ONE_DAY_AT_A_TIME is True):
    TRAINING_WINDOW_HOURS = 24
BUFFER_HOURS = PREDICTION_WINDOW_HOURS - 24


# only energy forecast
# NUM_FEATURES_MAP = {"CISO": 20, "PJM": 20, "ERCO": 18, "ISNE": 18, 
#                     "SE": 14, "GB":22, "DK-DK2": 23, "DE": 26} # ERCO except solar & other forecast
# only weather forecast
# NUM_FEATURES_MAP = {"CISO": 19, "PJM": 19, "ERCO": 18, "ISNE": 19, 
#                     "SE": 15, "GB":22, "DK-DK2": 23, "DE": 21} # ERCO 24 -> solar forecast, 25 -> other forecast
#all data
# NUM_FEATURES_MAP = {"CISO": 24, "PJM": 25, "ERCO": 23, "ISNE": 24, 
                    # "SE": 19, "GB":22, "DK-DK2": 23, "DE": 31} # ERCO 24 -> solar forecast, 25 -> other forecast
# only historical data
# NUM_FEATURES_MAP = {"CISO": 14, "PJM": 14, "ERCO": 13, "ISNE": 14, 
#                     "SE": 10, "GB":22, "DK-DK2": 23, "DE": 16} # ERCO 24 -> solar forecast, 25 -> other forecast 
############################# MACRO END #########################################

def initialize(inFileName, forecastInFileName):
    print(inFileName)
    global START_COL
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])    
    # dataset = dataset[:8784]
    print(dataset.head())
    print(dataset.columns)
    dateTime = dataset.index.values

    print(forecastInFileName)
    forecastDataset = pd.read_csv(forecastInFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])    
    # dataset = dataset[:8784]
    print(forecastDataset.head())
    print(forecastDataset.columns)

    for i in range(START_COL, len(dataset.columns.values)):
        col = dataset.columns.values[i]
        dataset[col] = dataset[col].astype(np.float64)
        print(col, dataset[col].dtype)

    # print("Getting contribution of each energy source...")
    # contribution = getAvgContributionBySource(dataset)
    # print(contribution)

    print("\nAdding features related to date & time...")
    modifiedDataset = addDateTimeFeatures(dataset, dateTime)
    dataset = modifiedDataset
    print("Features related to date & time added")

    return dataset, forecastDataset, dateTime

# Date time feature engineering
def addDateTimeFeatures(dataset, dateTime):
    global CARBON_INTENSITY_COL
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
    loc = START_COL+1
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
        y.append(data[trainWindow:labelWindow, CARBON_INTENSITY_COL])
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

def buildModel(hp):
    global TRAINING_WINDOW_HOURS
    global NUM_FEATURES
    global NUM_FORECAST_FEATURES
    global PREDICTION_WINDOW_HOURS
    global MODEL_SLIDING_WINDOW_LEN
    # n_timesteps, n_features, n_outputs = trainX.shape[1], trainX.shape[2], trainY.shape[1]
    model = Sequential()
    # model.add(Conv1D(filters=hp.Int('conv_1_filter', min_value=4, max_value=16, step=4),
    #                 kernel_size=hp.Choice('conv_1_kernel', values = [4,5,6]), 
    #                 padding="same",
    #                 activation="relu", input_shape=(TRAINING_WINDOW_HOURS,NUM_FEATURES),
    #         ))
    # model.add(MaxPooling1D(pool_size=2))
    # model.add(Conv1D(filters=hp.Int('conv_2_filter', min_value=4, max_value=16, step=4),
    #                 kernel_size=hp.Choice('conv_2_kernel', values = [4,6]), 
    #                 activation="relu", input_shape=(TRAINING_WINDOW_HOURS,NUM_FEATURES),
    #         ))

    model.add(LSTM(hp.Int('input_unit',min_value=16,max_value=96,step=16),return_sequences=True, 
            input_shape=(TRAINING_WINDOW_HOURS, NUM_FEATURES+NUM_FORECAST_FEATURES)))
    n_layers = hp.Int('n_layers', 1, 3)
    lstm_units = []
    for i in range(n_layers):
        lstm_units.append("lstm_"+str(i)+"_units")
        model.add(LSTM(hp.Int(lstm_units[i],min_value=16,max_value=64,step=16),return_sequences=True))
        # print(lstm_units[i])
    model.add(LSTM(hp.Int('layer_2_neurons',min_value=16,max_value=32,step=16)))
    model.add(Dropout(hp.Float('Dropout_rate',min_value=0,max_value=0.5,step=0.1)))
    # model.add(Dense(hp.Int("dense_unit", min_value=32, max_value=64, step=16), 
    #         activation=hp.Choice('dense_activation',values=['relu', 'sigmoid'],default='relu')))
    model.add(Dense(TRAINING_WINDOW_HOURS, activation=hp.Choice('dense_activation',values=['relu', 'sigmoid'],default='relu')))

    # model.add(Flatten())
    # model.add(Dense(units=hp.Int("dense_units", min_value=20, max_value=100, step=10),
    #         activation="relu",))
    # model.add(Dense(PREDICTION_WINDOW_HOURS))
    model.compile(loss="mse", 
                optimizer = tf.keras.optimizers.Adam(hp.Choice('learning_rate', values=[1e-2, 1e-3])),
                metrics=['mean_absolute_error'])

    # print("$$$$$$$$$$$$$$")
    # hyperParams = [hp.get("input_unit"), hp.get("n_layers"), hp.get("layer_2_neurons"), 
    #         hp.get("Dropout_rate"), hp.get("dense_unit"), hp.get("dense_activation")]
    # for kk in range(hp.get("n_layers")):
    #     hyperParams.append(hp.get("lstm_"+str(kk)+"_units"))

    # print(model.summary())
    # print("$$$$$$$$$$$$$$")
    return model

# train the model
def getBestModelArch(trainX, trainY, valX, valY):
    # [ 10 6 6 16 4 0.001 70 ] lifecycle best hp

    # define parameters
    print("Training...")
    global NUM_VAL_DAYS
    verbose = 2
    bestModel = None
    n_timesteps, n_features, n_outputs = trainX.shape[1], trainX.shape[2], trainY.shape[1]
    epochs = 25 #dip
    
    tuner = kt.RandomSearch(hypermodel=buildModel,
                            objective="val_loss",
                            max_trials=300,
                            executions_per_trial=1,
                            overwrite=True,
                            directory="kt_dir",
                            project_name="test1")
    
    # simple early stopping
    es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=12)
    # mc = ModelCheckpoint('best_model_kt.h5', monitor='val_loss', mode='min', verbose=1, save_best_only=True)

    hist = tuner.search(trainX, trainY, epochs=epochs, batch_size=10, verbose=verbose,
                        validation_data=(valX, valY), callbacks=[es])
    tuner.search_space_summary()

    best_hps=tuner.get_best_hyperparameters(num_trials=1)[0]
    print(best_hps)
    print(best_hps.values)
    # print(best_hps.get("conv_1_filter"), best_hps.get("conv_1_kernel"), best_hps.get("conv_2_filter"),
    #         best_hps.get("conv_2_kernel"), best_hps.get("dense_units"), best_hps.get("learning_rate"))

    print(best_hps.get("input_unit"), best_hps.get("n_layers"), best_hps.get("layer_2_neurons"),
            best_hps.get("Dropout_rate"), best_hps.get("dense_activation"), best_hps.get("learning_rate"))
    for i in range(best_hps.get("n_layers")):
        print(best_hps.get(f'lstm_{i}_units'))
    print("*********************************************************************************")

    # hyperParams = [10, best_hps.get("conv_1_kernel"), best_hps.get("conv_2_kernel"),
    #                 best_hps.get("conv_1_filter"), best_hps.get("conv_2_filter"),
    #                 best_hps.get("learning_rate"), best_hps.get("dense_units")]

    lstm_units = []
    for i in range(best_hps.get("n_layers")):
        lstm_units.append(best_hps.get(f'lstm_{i}_units'))

    hyperParams = [10, best_hps.get("learning_rate"), best_hps.get("input_unit"), best_hps.get("n_layers"),
                    lstm_units, best_hps.get("layer_2_neurons"), best_hps.get("Dropout_rate"),
                    best_hps.get("actv")] #  best_hps.get("dense_unit"),

    
    
    # best_model, n_features = trainModel(trainX, trainY, valX, valY, hyperParams)
    best_model, n_features = trainLSTM(trainX, trainY, valX, valY, hyperParams)
    return best_model, n_features

# train the model
def trainModel(trainX, trainY, valX, valY, hyperParams, iteration):
    # define parameters
    print("Training...")
    global NUM_SPLITS
    global NUM_VAL_DAYS
    verbose = 2
    hist = None
    bestModel = None
    minLoss, maxAccuracy = 1e7, 0
    n_timesteps, n_features, n_outputs = trainX.shape[1], trainX.shape[2], trainY.shape[1]
    print("Timesteps: ", n_timesteps, "No. of features: ", n_features, "No. of outputs: ", n_outputs)
    epochs = 100 #dip
    bs, k1, k2, nf1, nf2, lr, h = hyperParams
    # batchSize = hyperParams['batchsize']
    # kernelSize = hyperParams['kernel']
    # numFilters = hyperParams['filter']
    # hiddenDims = hyperParams['hidden']
    # hd = hiddenDims[0]
    # learningRates = hyperParams['lr']
    trainParameters = {}
    # define model
    
    print("[", bs, k1, k2, nf1, nf2, lr, h, "]")
#################################### CNN model #################################
    model = Sequential()
    model.add(Conv1D(filters=nf1, kernel_size=k1, padding="same",
            activation="relu", input_shape=(n_timesteps,n_features),
            ))
    model.add(MaxPooling1D(pool_size=2))
    model.add(Conv1D(filters=nf2, kernel_size=k2,
            activation="relu", input_shape=(n_timesteps,n_features),
            ))
    
    model.add(Flatten())
    # model.add(Dense(h, activation="relu"))
    # model.add(Dense(n_outputs))
    model.add(RepeatVector(n_outputs))
    model.add(LSTM(n_outputs))
    model.add(Dropout(0.1))
    model.add(Dense(n_outputs))
    # model.summary()
################################################################################

################################################################################

    # for layer in model.layers:
    #     print(layer.name)
    #     print(layer.input_shape)
    #     print(layer.output_shape)

    opt = tf.keras.optimizers.Adam(learning_rate = lr)
    model.compile(loss="mse", optimizer=opt, metrics=['mean_absolute_error'])
    # simple early stopping
    es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=10)
    mc = ModelCheckpoint("best_model_iter"+str(iteration)+".h5", monitor='val_loss', mode='min', verbose=1, save_best_only=True)
    rlr = ReduceLROnPlateau(monitor="val_loss", mode="min", factor=0.1, patience=6, verbose=1, min_lr=0.001)

# fit network
    hist = model.fit(trainX, trainY, epochs=epochs, batch_size=bs, verbose=verbose,
                        validation_data=(valX, valY), callbacks=[rlr, es, mc])

    bestModel = load_model("best_model_iter"+str(iteration)+".h5")
# showModelSummary(hist, model)
# print("Loss history: ", hist.history)
    # showModelSummary(hist, bestModel, "CNN")
    # print("Training the best model...")
    # hist = bestModel.fit(trainX, trainY, epochs=100, batch_size=trainParameters['batchsize'], verbose=verbose)
    return bestModel, n_features

# train the model
def trainLSTM(trainX, trainY, valX, valY, hyperParams):
    # define parameters
    print("Training...")
    global NUM_SPLITS
    verbose = 2
    hist = None
    bestModel = None
    minLoss, maxAccuracy = 1e7, 0
    n_timesteps, n_features, n_outputs = trainX.shape[1], trainX.shape[2], trainY.shape[1]
    print("Timesteps: ", n_timesteps, "No. of features: ", n_features, "No. of outputs: ", n_outputs)
    epochs = 100 #dip
    # bs, k1, k2, nf1, nf2, lr, h = hyperParams
    trainParameters = {}
    # define model
    
    # print("[", bs, k1, k2, nf1, nf2, lr, h, "]")

    bs, lr, input_unit, n_layers, lstm_units, layer_2_neurons, dropout_rate, dense_units, actv = hyperParams
    lstm_0_units = 16
    lstm_1_units = 40
    lstm_2_units = 48
    lstm_3_units = 80
############################################################################################
    model = Sequential()

    model.add(LSTM(16, 
            input_shape=(n_timesteps, n_features)))
    # n_layers = hp.Int('n_layers', 1, 2)
    # lstm_units = []
    # for i in range(n_layers):
        # lstm_units.append("lstm_"+str(i)+"_units")
    # model.add(LSTM(lstm_0_units,return_sequences=True))
    # # model.add(LSTM(lstm_1_units,return_sequences=True))
    # # model.add(LSTM(lstm_2_units,return_sequences=True))
    # # model.add(LSTM(lstm_3_units,return_sequences=True))
    #     # print(lstm_units[i])
    # model.add(LSTM(layer_2_neurons))
    model.add(Dropout(dropout_rate))
    # model.add(Dense(dense_units, activation=actv))
    # model.add(Dense(n_outputs))
    model.add(Dense(n_outputs, activation=actv))
    model.summary()

    for layer in model.layers:
        print(layer.name)
        print(layer.input_shape)
        print(layer.output_shape)
    
                # Conclusion: 
############################################################################################

    opt = tf.keras.optimizers.Adam(learning_rate = lr)
    model.compile(loss="mse", optimizer=opt, metrics=['mean_absolute_error'])
    # simple early stopping
    es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=15)
    mc = ModelCheckpoint('best_model_lstm.h5', monitor='val_loss', mode='min', verbose=1, save_best_only=True)

# fit network
    hist = model.fit(trainX, trainY, epochs=epochs, batch_size=bs, verbose=verbose,
                        validation_data=(valX, valY), callbacks=[es, mc])

    bestModel = load_model("best_model_lstm.h5")
# showModelSummary(hist, model)
# print("Loss history: ", hist.history)
    # if (hist.history['loss'][-1] < minLoss):
    #     minLoss = hist.history['loss'][-1]
    #     bestModel = model
    # # print("Min loss in model.fit: ", minLoss)
    # print("Min loss in model.fit: ", minLoss)
    # # print("Training the best model...")
    # # hist = bestModel.fit(trainX, trainY, epochs=100, batch_size=trainParameters['batchsize'], verbose=verbose)
    return bestModel, n_features

def showModelSummary(history, model, architecture=None):
    print("Showing model summary...")
    model.summary()
    print("***** Model summary shown *****")
    # list all data in history
    print(history.history.keys()) # ['loss', 'mean_absolute_error', 'val_loss', 'val_mean_absolute_error']
    # fig = plt.figure()
    # subplt1 = fig.add_subplot(2, 1, 1)
    # subplt1.plot(history.history['mean_absolute_error'])
    # subplt1.plot(history.history['val_mean_absolute_error'])
    # subplt1.legend(['train MAE', 'val_MAE'], loc="upper left")
    # # summarize history for loss
    # subplt2 = fig.add_subplot(2, 1, 2)
    # subplt2.plot(history.history['loss'])
    # subplt2.plot(history.history['val_loss'])
    # subplt2.legend(['train RMSE '+architecture, 'val RMSE'+architecture], loc="upper left")
    
    # # plt.plot(history.history["loss"])
    # # plt.xlabel('epoch')
    # # plt.ylabel("RMSE")
    # # plt.title('Training loss (RMSE)')
    return

def get1stDayForecastUsingDACF(sourceForecasts, forecastColumns, wFtMin, wFtMax, ciMin, ciMax):
    forcast_carbonRateLifecycle = {"avg_coal_production_forecast": 820, "avg_biomass_production_forecast": 230, 
                "avg_nat_gas_production_forecast": 490, "avg_geothermal_production_forecast": 38, 
                "avg_hydro_production_forecast": 24, "avg_nuclear_production_forecast": 12, 
                "avg_oil_production_forecast": 650, "avg_solar_production_forecast": 45, 
                "avg_unknown_production_forecast": 700, "avg_other_production_forecast": 700, 
                "avg_wind_production_forecast": 11} # g/kWh

    forcast_carbonRateDirect = {"avg_coal_production_forecast": 760, "avg_biomass_production_forecast": 0, 
                "avg_nat_gas_production_forecast": 370, "avg_geothermal_production_forecast": 0, 
                "avg_hydro_production_forecast": 0, "avg_nuclear_production_forecast": 0, 
                "avg_oil_production_forecast": 406, "avg_solar_production_forecast": 0, 
                "avg_unknown_production_forecast": 575, "avg_other_production_forecast": 575, 
                "avg_wind_production_forecast": 0} # g/kWh # correct biomass

    forecast = []
    unscaledSourceForecasts = np.zeros_like(sourceForecasts)
    for i in range(sourceForecasts.shape[1]):
        unscaledSourceForecasts[:, i] = common.inverseScaleColumn(sourceForecasts[:, i], wFtMin[i], wFtMax[i])
        # print(forecastColumns[i])
        # print(unscaledSourceForecasts)
    for i in range(24):
        avgCI = 0.0
        totalElectricity = 0
        for j in range(len(forecastColumns)):
            avgCI += (unscaledSourceForecasts[i][j] * forcast_carbonRateDirect[forecastColumns[j]])
            totalElectricity += unscaledSourceForecasts[i][j]
        avgCI /= totalElectricity
        forecast.append(avgCI)
    # print(ciMin, ciMax)
    # print(forecast)
    forecast = common.scaleColumn(forecast, ciMin, ciMax)
    # print(forecast)
    # exit(0)
    return forecast

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
    for i in range(0, ((len(testData)//24)-(BUFFER_HOURS//24))):
        dayAheadPredictions = list()
        # predict n days, 1 day at a time
        tempHistory = history.copy()
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
        for j in range(0, MAX_PREDICTION_WINDOW_HOURS, 24):
            if (j >= PREDICTION_WINDOW_HOURS):
                continue
            yhat_sequence, _ = getForecasts(model, tempHistory, 
                            trainWindowHours, numFeatures, weatherData[j:j+24])
            # if (j==0):
            #     dacfForecast = get1stDayForecastUsingDACF(weatherData[j:j+24, 5:], forecastColumns[5:],
            #                 wFtMin, wFtMax, ciMin, ciMax)
            #     for k in range(24):
            #         yhat_sequence[k] = dacfForecast[k]
            #         # yhat_sequence[k] = testData[currentDayHours+k, 0]
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
    # print("ip_x shape: ", input_x.shape)
    yhat = model.predict(input_x, verbose=0)
    # we only want the vector forecast
    yhat = yhat[0]
    return yhat, input_x

def featureImportance(seq, model, features, testDates):
    # print(seq.shape)
    id_=1
    seq = tf.Variable(seq[np.newaxis,:,:], dtype=tf.float32)
    with tf.GradientTape() as tape:
        predictions = model(seq)
    grads = tape.gradient(predictions, seq)
    grads = tf.reduce_mean(grads, axis=1).numpy()[0]
    return grads

def findImportantFeatures(model, valData, featureList):
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
    # plt.title("Feature importance - " + ISO)
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

def getHyperParams():
    hyperParams = {}
    configList = []
    hyperParams['epoch'] = 100 # DIP
    hyperParams['batchsize'] = [24]#[5, 10]
    hyperParams['kernel1'] = [6]#[4, 6]
    hyperParams['kernel2'] = [4]#[3, 4]
    hyperParams['filter1'] = [4, 16]
    hyperParams['filter2'] = [4, 16]
    hyperParams['poolsize'] = 2
    hyperParams['lr'] = [1e-2, 1e-3]
    hyperParams['hidden'] = [20, 50]
    # for a in hyperParams['batchsize']:
    #     for b in hyperParams['kernel1']:
    #         for c in hyperParams['kernel2']:
    #             for d in hyperParams['filter1']:
    #                 for e in hyperParams['filter2']:
    #                     for f in hyperParams['lr']:
    #                         for g in hyperParams['hidden']:
    #                             tmpList = [a,b,c,d,e,f,g]
    #                             configList.append(tmpList)

    #Best config:  [10, 6, 4, 4, 4, 0.001, 20] best mean:  6.735857009887695
    #Best config:  [10, 4, 4, 4, 16, 0.001, 20] best mean:  7.342548370361328

    configList = [[10, 4, 4, 4, 16, 0.01, 20]] # final hyperparameters
            
    return hyperParams, configList

#Start of execution
rmse = {}

isoDailyMape = {}

for ISO in ISO_LIST:

    isoConfig = configurationData[ISO]

    PLOT_TITLE = ISO
    IN_FILE_NAME = isoConfig["IN_FILE_NAME"]
    FORECAST_IN_FILE_NAME = isoConfig["FORECAST_IN_FILE_NAME"]
    OUT_FILE_NAME = ISO+"/"+ISO+"_lifecycle_forecast"
    LOCAL_TIMEZONE = pytz.timezone(isoConfig["LOCAL_TIMEZONE"])
    NUM_FEATURES = isoConfig["NUM_FEATURES"]
    NUM_FORECAST_FEATURES = isoConfig["NUM_FORECAST_FEATURES"]
    START_COL = isoConfig["START_COL"]

    print("Initializing...")
    dataset, forecastDataset, dateTime = initialize(IN_FILE_NAME, FORECAST_IN_FILE_NAME)
    print("***** Initialization done *****")

    # split into train and test
    print("Spliting dataset into train/test...")
    # dataset = dataset[:-BUFFER_HOURS]
    print(dataset.tail())
    trainData, valData, testData, _ = common.splitDataset(dataset.values, 
                                            (NUM_TEST_DAYS+BUFFER_HOURS//24), NUM_VAL_DAYS, 
                                            MAX_PREDICTION_WINDOW_HOURS-PREDICTION_WINDOW_HOURS)
    trainDates = dateTime[: -((NUM_TEST_DAYS+BUFFER_HOURS//24)*24):]
    trainDates, validationDates = trainDates[: -(NUM_VAL_DAYS*24)], trainDates[-(NUM_VAL_DAYS*24):]
    testDates = dateTime[-((NUM_TEST_DAYS+BUFFER_HOURS//24)*24):]
    trainData = trainData[:, START_COL: START_COL+NUM_FEATURES]
    valData = valData[:, START_COL: START_COL+NUM_FEATURES]
    testData = testData[:, START_COL: START_COL+NUM_FEATURES]
    # fullTestData = np.copy(testData) # [DM]
    # testData = testData[: -BUFFER_HOURS] # [DM]
    print("TrainData shape: ", trainData.shape) # days x hour x features
    print("ValData shape: ", valData.shape) # days x hour x features
    print("TestData shape: ", testData.shape) # days x hour x features

    wTrainData, wValData, wTestData, wFullTrainData = common.splitWeatherDataset(
            forecastDataset.values, NUM_TEST_DAYS, NUM_VAL_DAYS, MAX_PREDICTION_WINDOW_HOURS)
    wTrainData = wTrainData[:, :NUM_FORECAST_FEATURES]
    wValData = wValData[:, :NUM_FORECAST_FEATURES]
    wTestData = wTestData[:, :NUM_FORECAST_FEATURES]
    print("WeatherTrainData shape: ", wTrainData.shape) # (days x hour) x features
    print("WeatherValData shape: ", wValData.shape) # (days x hour) x features
    print("WeatherTestData shape: ", wTestData.shape) # (days x hour) x features

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
    
    # for i in range(fullTestData.shape[0]):
    #     for j in range(fullTestData.shape[1]):
    #         if(np.isnan(fullTestData[i, j])):
    #             fullTestData[i, j] = fullTestData[i-1, j]

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

    print("***** Dataset split done *****")

    featureList = dataset.columns.values
    featureList = featureList[START_COL:START_COL+NUM_FEATURES].tolist()
    featureList.extend(forecastDataset.columns.values[:NUM_FORECAST_FEATURES])
    print("Features: ", featureList)

    print("Scaling data...")
    # unscaledTestData = np.zeros(testData.shape[0])
    unscaledTrainCarbonIntensity = np.zeros(trainData.shape[0])
    # for i in range(testData.shape[0]):
    #     unscaledTestData[i] = testData[i, CARBON_INTENSITY_COL]
    for i in range(trainData.shape[0]):
        unscaledTrainCarbonIntensity[i] = trainData[i, CARBON_INTENSITY_COL]
    trainData, valData, testData, ftMin, ftMax = common.scaleDataset(trainData, valData, testData)
    print(trainData.shape, valData.shape, testData.shape)
    wTrainData, wValData, wTestData, wFtMin, wFtMax = common.scaleDataset(wTrainData, wValData, wTestData)
    print(wTrainData.shape, wValData.shape, wTestData.shape)
    print("***** Data scaling done *****")
    
    # plotFeatures(trainData[24*60:24*70], trainDates[24*60:24*70], featureList, LOCAL_TIMEZONE , "wind")
    # plotFeatures(trainData, trainDates, featureList, LOCAL_TIMEZONE , "wind")
    # plotFeatures(testData, testDates, featureList, LOCAL_TIMEZONE , "nuclear")
    # plotFeatures(testData, testDates, featureList, LOCAL_TIMEZONE , "nat")
    # plotFeatures(testData, testDates, featureList, LOCAL_TIMEZONE , "oil")
    # plotFeatures(testData, testDates, featureList, LOCAL_TIMEZONE , "coal")
    # exit(0)

    # print("Analyzing time series data...")
    # analyzeTimeSeries(dataset, trainData, unscaledTrainCarbonIntensity, dateTime)
    # print("***** Data analysis done *****")
    # exit(0)

    # Pie chart of average fraction of electricity generated by each source
    # utility.plotPieChart(ISO, trainData[:, 6:16], featureList[6:16])
    # utility.plotPieChart(ISO, valData[:, 6:16], featureList[6:16])
    # utility.plotPieChart(ISO, testData[:, 6:16], featureList[6:16])
    # utility.showPlots()
    # exit(0)

    print("\nManipulating training data...")
    if (FORECASTS_ONE_DAY_AT_A_TIME is True):
        # [DIP] TODO: Check how to decouple dataset in this case
        X, y = manipulateTrainingDataShape(trainData, TRAINING_WINDOW_HOURS, TRAINING_WINDOW_HOURS, wTrainData)
        # Next line actually labels validation data
        valX, valY = manipulateTrainingDataShape(valData, TRAINING_WINDOW_HOURS, TRAINING_WINDOW_HOURS, wValData)
    print("***** Training data manipulation done *****")
    print("X.shape, y.shape: ", X.shape, y.shape)

    ######################## START #####################

    idx = 0
    baselineRMSE, baselineMAPE = [], []
    bestRMSE, bestMAPE = [], []
    predictedData = None
    
    hyperParams, configList = getHyperParams()

    bestMean = 100
    bestConfig = []
    configMapeDict = {}
    for config in configList:
        bestMAPE = []
        bestRMSE = []
        for xx in range(NUMBER_OF_EXPERIMENTS):
            print("\n[BESTMODEL] Starting training...")
            bestModel, numFeatures = trainModel(X, y, valX, valY, config, xx)
            # config = [24, 0.01, 64, 1,
            #         0, 32, 0.1,
            #         32, "sigmoid"] #bs, lr, input_unit, n_layers, lstm_units, layer_2_neurons, dropout_rate, dense_units, actv
            # bestModel, numFeatures = trainLSTM(X, y, valX, valY, config)
            # bestModel, numFeatures = getBestModelArch(X, y, valX, valY)
            print("***** Training done *****")
            history = valData[-TRAINING_WINDOW_HOURS:, :]
            weatherData = None
            weatherData = wValData[-MAX_PREDICTION_WINDOW_HOURS:, :]
            print("weatherData shape:", weatherData.shape)
            history = history.tolist()
            
            if (FORECASTS_ONE_DAY_AT_A_TIME is True):
                print("Calling getDayAheadForecasts()")
                predictedData = getDayAheadForecasts(bestModel, history, testData, 
                                    TRAINING_WINDOW_HOURS, numFeatures, CARBON_INTENSITY_COL,
                                    wFtMin[5:], wFtMax[5:], ftMin[CARBON_INTENSITY_COL], ftMax[CARBON_INTENSITY_COL],
                                    wTestData, weatherData, forecastDataset.columns.values[:NUM_FORECAST_FEATURES])
            
            actualData = manipulateTestDataShape(testData[:, CARBON_INTENSITY_COL], 
                    MODEL_SLIDING_WINDOW_LEN, PREDICTION_WINDOW_HOURS, False)
            formattedTestDates = manipulateTestDataShape(testDates, 
                    MODEL_SLIDING_WINDOW_LEN, PREDICTION_WINDOW_HOURS, True)
            formattedTestDates = np.reshape(formattedTestDates, 
                    formattedTestDates.shape[0]*formattedTestDates.shape[1])
            actualData = actualData.astype(np.float64)
            print("ActualData shape: ", actualData.shape)
            actual = np.reshape(actualData, actualData.shape[0]*actualData.shape[1])
            predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
            # print(predicted)
            unScaledPredictedData = common.inverseDataScaling(predicted, ftMax[CARBON_INTENSITY_COL], 
                                ftMin[CARBON_INTENSITY_COL])
            unscaledTestData = common.inverseDataScaling(actual, ftMax[CARBON_INTENSITY_COL], 
                                ftMin[CARBON_INTENSITY_COL])
            print(actualData.shape, predictedData.shape, unscaledTestData.shape, unScaledPredictedData.shape)
            rmseScore, mapeScore, dailyMapeScore = getScores(actualData, predictedData, 
                                        unscaledTestData, unScaledPredictedData, testDates)
            isoDailyMape[ISO] = dailyMapeScore
            print("***** Forecast done *****")
            data = []
            for i in range(len(unScaledPredictedData)):
                row = []
                row.append(str(formattedTestDates[i]))
                row.append(str(unscaledTestData[i]))
                row.append(str(unScaledPredictedData[i]))
                data.append(row)
            # common.writeOutFile("../extn/"+ISO+"/newdata/direct/testOut"+str(xx)+".csv", data, featureList[0], "w")

            # print("**** Important features based on valData:")
            # topNFeatures = findImportantFeatures(bestModel, valData, featureList)
            # print("**** Important features based on testData:")
            # modTestData = manipulateTestDataShape(testData, MODEL_SLIDING_WINDOW_LEN, PREDICTION_WINDOW_HOURS, False)
            # modTestData = np.reshape(modTestData, (modTestData.shape[0]*modTestData.shape[1], modTestData.shape[2]))
            # print(modTestData.shape, wTestData.shape)
            # modTestData = np.append(modTestData, wTestData, axis=1)
            # print("modtestdata shape: ", modTestData.shape)
            # topNFeatures = findImportantFeatures(bestModel, modTestData, featureList)

            print("[BESTMODEL] Overall RMSE score: ", rmseScore)
            print("[BESTMODEL] Overall MAPE score: ", mapeScore)
            # print(scores)
            bestRMSE.append(rmseScore)
            bestMAPE.append(mapeScore)
            print("Overall Mean MAPE: ", mapeScore)
            print("Daywise statistics...")
            for i in range(0, PREDICTION_WINDOW_HOURS//24):
                print("Prediction day ", i+1, "(", (i*24), " - ", (i+1)*24, " hrs)")
                print("Mean MAPE: ", np.mean(isoDailyMape[ISO][:, i]))
                print("Median MAPE: ", np.percentile(isoDailyMape[ISO][:, i], 50))
                print("90th percentile MAPE: ", np.percentile(isoDailyMape[ISO][:, i], 90))
                print("95th percentile MAPE: ", np.percentile(isoDailyMape[ISO][:, i], 95))
                print("99th percentile MAPE: ", np.percentile(isoDailyMape[ISO][:, i], 99))
            fileName = "../extn/"+ISO+"/buildsys/direct_final/file"+str(xx+1)+".csv"
            utility.writeDailyMapeToFile(xx, isoDailyMape[ISO], fileName)
            # data = []
            # for i in range(len(unscaledTestData)):
            #     row = []
            #     row.append(str(unscaledTestData[i]))
            #     row.append(str(unScaledPredictedData[i]))
            #     data.append(row)
            # common.writeOutFile(OUT_FILE_NAME+"_"+str(xx)+".csv", data, None)
            plotTitle = PLOT_TITLE + "_" + str(PREDICTION_WINDOW_HOURS) + "hr_" + str(NUM_FEATURES) + "ft"
            # plotGraphs(unscaledTestData[-24*7:], unScaledPredictedData[-24*7:], testDates[-24*7:], 
            #                     plotTitle, LOCAL_TIMEZONE, False)
            # for i in range(24*7-1, -1, -1):
            #     print(unScaledPredictedData[-i])
            # for mape in isoDailyMape[ISO]:
            #     print(mape)
    
    # configMapeDict = dict(sorted(configMapeDict.items(), key=lambda item: item[1]))
    # for k, v in configMapeDict:
    #     print(k, v)
    # print("Best config: ", bestConfig, "best mean: ", bestMean)

    # print(unscaledTestData)
    # print(unScaledPredictedData)

    print("[BEST] Average RMSE after ", NUMBER_OF_EXPERIMENTS, " expts: ", np.mean(bestRMSE))
    print("[BEST] Average MAPE after ", NUMBER_OF_EXPERIMENTS, " expts: ", np.mean(bestMAPE))
    print(bestRMSE)
    print(bestMAPE)

    ######################## END #####################

    plotTitle = PLOT_TITLE + "_" + str(PREDICTION_WINDOW_HOURS) + "hr_" + str(NUM_FEATURES) + "ft"
    plotBaseline = False
    
    # actual = np.reshape(actualData, actualData.shape[0]*actualData.shape[1])
    # predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
    # unScaledPredictedData = inverseDataScaling(predicted, ftMax[CARBON_INTENSITY_COL], 
    #                         ftMin[CARBON_INTENSITY_COL])
    # plotGraphs(unscaledTestData[-(62*24+1):-(59*24+1)], unScaledPredictedData[-(62*24+1):-(59*24+1)], testDates[-(62*24+1):-(59*24+1)], 
    #                     plotTitle, LOCAL_TIMEZONE, plotBaseline)

    
    

    # # Showing effect of forecasts
    # plotGraphs(unscaledTestData, unScaledPredictedData, testDates, 
    #                     plotTitle, LOCAL_TIMEZONE, plotBaseline, unScaledPredictedDataLSTM)
    
    print("####################", ISO, " done ####################\n\n")

# plotBoxplots(isoDailyMape)
utility.showPlots()

print("End")
