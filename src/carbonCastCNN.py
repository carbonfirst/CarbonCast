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
from keras.layers import Dense, Flatten
from keras.layers.convolutional import AveragePooling1D, Conv1D, MaxPooling1D, Conv2D
from keras.layers.core import Activation, Dropout
from keras.layers.normalization.batch_normalization import BatchNormalization
from keras.models import Sequential
from statsmodels.tsa.stattools import adfuller
import tensorflow as tf
from keras.callbacks import EarlyStopping
from keras.callbacks import ModelCheckpoint
from keras.models import load_model, save_model

import shap
import json5 as json

import common
import utility


############################# MACRO START #######################################
# Multivariate multi-step time series forecasting
print("Start")
configurationData = {}

with open("config.json", "r") as configFile:
    configurationData = json.load(configFile)
    print(configurationData)

ISO_LIST = configurationData["ISO_LIST"]

NUM_TEST_DAYS = configurationData["NUM_TEST_DAYS"] # last 6 months of 2021
NUM_VAL_DAYS = configurationData["NUM_VAL_DAYS"] # first 6 months of 2021
TRAINING_WINDOW_HOURS = configurationData["TRAINING_WINDOW_HOURS"]
MODEL_SLIDING_WINDOW_LEN = configurationData["MODEL_SLIDING_WINDOW_LEN"]
PREDICTION_WINDOW_HOURS = configurationData["PREDICTION_WINDOW_HOURS"]
TOP_N_FEATURES = configurationData["TOP_N_FEATURES"]
DAY_INTERVAL = 1
MONTH_INTERVAL = 1
CARBON_INTENSITY_COL = 0
NUM_SPLITS = 4
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

def initialize(inFileName, localTimezone):
    print(inFileName)
    global START_COL
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])    
    # dataset = dataset[:8784]
    print(dataset.head())
    print(dataset.columns)
    dateTime = dataset.index.values

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

    return dataset, dateTime

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
def manipulateTrainingDataShape(data, trainWindowHours, labelWindowHours): 
    # flatten data
    print("New data shape: ", data.shape)
    X, y = list(), list()
    # step over the entire history one time step at a time
    for i in range(len(data)-(trainWindowHours+labelWindowHours)+1):
        # define the end of the input sequence
        trainWindow = i + trainWindowHours
        labelWindow = trainWindow + labelWindowHours
        xInput = data[i:trainWindow, :]
        # xInput = xInput.reshape((len(xInput), 1))
        X.append(xInput)
        y.append(data[trainWindow:labelWindow, CARBON_INTENSITY_COL])
    return np.array(X, dtype=np.float64), np.array(y, dtype=np.float64)

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
def train(trainX, trainY, valX, valY, hyperParams):
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
############################################################################################
    model = Sequential()
    model.add(Conv1D(filters=nf1, kernel_size=k1, padding="same",
            activation="relu", input_shape=(n_timesteps,n_features),
            ))
    model.add(MaxPooling1D(pool_size=2))
    # model.add(Conv1D(filters=nf1, kernel_size=k2, padding = "same",
    #         activation="relu", input_shape=(n_timesteps,n_features),
    #         ))
    # model.add(MaxPooling1D(pool_size=2))
    model.add(Conv1D(filters=nf2, kernel_size=k2,
            activation="relu", input_shape=(n_timesteps,n_features),
            ))
    # model.add(Conv2D(filters=nf1, kernel_size=(1, k1), padding="same", 
    #                         activation="relu", input_shape=(n_timesteps,n_features, 1),
    #                         ))
    model.add(Flatten())
    model.add(Dense(h, activation="relu"))
    # model.add(Dense(50, activation="relu")) 
    model.add(Dense(n_outputs))
############################################################################################
    opt = tf.keras.optimizers.Adam(learning_rate = lr)
    model.compile(loss="mse", optimizer=opt, metrics=['mean_absolute_error'])
    # simple early stopping
    es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=15)
    mc = ModelCheckpoint('best_model.h5', monitor='val_loss', mode='min', verbose=1, save_best_only=True)

# fit network
    hist = model.fit(trainX, trainY, epochs=epochs, batch_size=bs, verbose=verbose,
                        validation_data=(valX, valY), callbacks=[es, mc])

    bestModel = load_model("best_model.h5")
# showModelSummary(hist, model)
# print("Loss history: ", hist.history)
    # showModelSummary(hist, bestModel, "CNN")
    # print("Training the best model...")
    # hist = bestModel.fit(trainX, trainY, epochs=100, batch_size=trainParameters['batchsize'], verbose=verbose)
    return bestModel, n_features

def showModelSummary(history, model, architecture):
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

# evaluate a single model
# walk-forward validation
def getOneShotForecasts(trainX, trainY, model, history, testData, trainWindowHours, numFeatures):
    # walk-forward validation over each day
    global MODEL_SLIDING_WINDOW_LEN
    global BUFFER_HOURS
    print("Testing...")
    predictions = list()
    for i in range(0, ((len(testData)//24)-(BUFFER_HOURS//24))):
        # predict the day
        yhat_sequence, newTrainingData = getForecasts(model, history, trainWindowHours, numFeatures)
        # store the predictions
        predictions.append(yhat_sequence)
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
        history.extend(testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN, :].tolist())
        newLabel = testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN,0].reshape(1, MODEL_SLIDING_WINDOW_LEN)
        np.append(trainX, newTrainingData)
        np.append(trainY, newLabel)
    # evaluate predictions days for each day
    predictedData = np.array(predictions)
    return predictedData

def getDayAheadForecasts(trainX, trainY, model, history, testData, 
                            trainWindowHours, numFeatures, depVarColumn):
    global MODEL_SLIDING_WINDOW_LEN
    global PREDICTION_WINDOW_HOURS
    global BUFFER_HOURS
    # walk-forward validation over each day
    print("Testing...")
    predictions = list()
    for i in range(0, ((len(testData)//24)-(BUFFER_HOURS//24))):
        dayAheadPredictions = list()
        # predict n days, 1 day at a time
        tempHistory = history.copy()
        for j in range(0, PREDICTION_WINDOW_HOURS, 24):
            yhat_sequence, newTrainingData = getForecasts(model, tempHistory, trainWindowHours, numFeatures)
            dayAheadPredictions.extend(yhat_sequence)
            # add current prediction to history for predicting the next day
            latestHistory = testData[i+j:i+j+24, :].tolist()
            for k in range(24):
                latestHistory[k][depVarColumn] = yhat_sequence[k]
            tempHistory.extend(latestHistory)

        # get real observation and add to history for predicting the next day
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
        history.extend(testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN, :].tolist())
        newLabel = testData[currentDayHours:currentDayHours+MODEL_SLIDING_WINDOW_LEN,0].reshape(1, MODEL_SLIDING_WINDOW_LEN)
        predictions.append(dayAheadPredictions)

    # evaluate predictions days for each day
    predictedData = np.array(predictions, dtype=np.float64)
    return predictedData

def updateModel(model, trainX, trainY):
    print("Updating model after each day")
    # opt = tf.keras.optimizers.Adam(learning_rate=0.001)
    model.compile(loss="mse", optimizer="adam",
                metrics=['mean_absolute_error'])
    # simple early stopping
    # es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=10)
    # mc = ModelCheckpoint('updated_best_model.h5', monitor='val_loss', mode='min', verbose=1, save_best_only=True)

# fit network
    # hist = model.fit(trainX, trainY, epochs=epochs, batch_size=bSize, verbose=verbose)
    hist = model.fit(trainX, trainY, epochs=5, batch_size=5, verbose=2)
                        # validation_data=(valX, valY), callbacks=[es, mc])

    # model = load_model("updated_best_model.h5")
    return model

def getForecasts(model, history, trainWindowHours, numFeatures):
    # flatten data
    data = np.array(history, dtype=np.float64)
    # retrieve last observations for input data
    input_x = data[-trainWindowHours:]
    # reshape into [1, n_input, num_features]
    input_x = input_x.reshape((1, len(input_x), numFeatures))
    # print("ip_x shape: ", input_x.shape)
    yhat = model.predict(input_x, verbose=0)
    # we only want the vector forecast
    yhat = yhat[0]
    return yhat, input_x

def featureImportance(seq, model, features, testDates):
    id_=1
    seq = tf.Variable(seq[np.newaxis,:,:], dtype=tf.float32)
    with tf.GradientTape() as tape:
        predictions = model(seq)
    grads = tape.gradient(predictions, seq)
    grads = tf.reduce_mean(grads, axis=1).numpy()[0]
    return grads

def findImportantFeatures(model, valData, featureList):
    global TOP_N_FEATURES
    topNFeatures = {}
    featureImp = {}
    grads = [None] * len(valData)
    for i in range(len(valData)):
        grads[i] = featureImportance(valData[i], model, featureList, testDates)
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

    print("Top ", TOP_N_FEATURES, " features:")
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
    print("Actual data shape, Predicted data shape: ", scaledActual.shape, scaledPredicted.shape)

    mse = tf.keras.losses.MeanSquaredError()
    rmseScore = round(math.sqrt(mse(scaledActual, scaledPredicted).numpy()), 6)

    unscaledRMSEScore = round(math.sqrt(mse(unscaledActual, unscaledPredicted).numpy()), 6)
    print("***** Unscaled RMSE: ", unscaledRMSEScore)

    mape = tf.keras.losses.MeanAbsolutePercentageError()

    dailyMapeScore = []
    outlierDays = {}
    for i in range(0, len(unscaledActual), 24):
        mapeTensor =  mape(unscaledActual[i:i+24], unscaledPredicted[i:i+24])
        mapeScore = mapeTensor.numpy()
        # print("Day: ", dates[i], "MAPE: ", mapeScore)
        if(mapeScore>15):
            # for j in range(24):
            #     print(unscaledActual[i+j], unscaledPredicted[i+j])
            outlierDays[dates[i]] = mapeScore
        dailyMapeScore.append(mapeScore)
    
    outlierDays = sorted(outlierDays.items(), key=lambda x: x[1], reverse=True)
    for k,v in outlierDays:
        print(k,": ", v)


    mapeTensor =  mape(unscaledActual, unscaledPredicted)
    mapeScore = mapeTensor.numpy()

    return rmseScore, mapeScore, dailyMapeScore

def getHyperParams():
    hyperParams = {}
    configList = []
    hyperParams['epoch'] = 100 # DIP
    hyperParams['batchsize'] = [10]#[5, 10]
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

    configList = [[10, 4, 4, 4, 16, 0.001, 20]] # final hyperparameters
            
    return hyperParams, configList

#Start of execution
rmse = {}

isoDailyMape = {}

for ISO in ISO_LIST:

    isoConfig = configurationData[ISO]

    PLOT_TITLE = ISO
    IN_FILE_NAME = isoConfig["IN_FILE_NAME"]
    OUT_FILE_NAME = ISO+"/"+ISO+"_Forecast.csv"
    LOCAL_TIMEZONE = pytz.timezone(isoConfig["LOCAL_TIMEZONE"])
    NUM_FEATURES = isoConfig["NUM_FEATURES"]
    START_COL = isoConfig["START_COL"]

    print("Initializing...")
    dataset, dateTime = initialize(IN_FILE_NAME, LOCAL_TIMEZONE)
    print("***** Initialization done *****")

    # split into train and test
    print("Spliting dataset into train/test...")
    trainData, valData, testData, _ = common.splitDataset(dataset.values, NUM_TEST_DAYS, NUM_VAL_DAYS)
    trainDates = dateTime[: -(NUM_TEST_DAYS*24)]
    trainDates, validationDates = trainDates[: -(NUM_VAL_DAYS*24)], trainDates[-(NUM_VAL_DAYS*24):]
    testDates = dateTime[-(NUM_TEST_DAYS*24):]
    trainData = trainData[:, START_COL: START_COL+NUM_FEATURES]
    valData = valData[:, START_COL: START_COL+NUM_FEATURES]
    testData = testData[:, START_COL: START_COL+NUM_FEATURES]
    print("TrainData shape: ", trainData.shape) # days x hour x features
    print("ValData shape: ", valData.shape) # days x hour x features
    print("TestData shape: ", testData.shape) # days x hour x features

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

    print("***** Dataset split done *****")

    featureList = dataset.columns.values[START_COL:START_COL+NUM_FEATURES]
    print("Features: ", featureList)

    print("Scaling data...")
    # unscaledTestData = np.zeros(testData.shape[0])
    unscaledTrainCarbonIntensity = np.zeros(trainData.shape[0])
    # for i in range(testData.shape[0]):
    #     unscaledTestData[i] = testData[i, CARBON_INTENSITY_COL]
    for i in range(trainData.shape[0]):
        unscaledTrainCarbonIntensity[i] = trainData[i, CARBON_INTENSITY_COL]
    trainData, valData, testData, ftMin, ftMax = common.scaleDataset(trainData, valData, testData)
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
    # plotPieChart(ISO, trainData[:, 6:14], featureList[6:14])
    # showPlots()

    print("\nManipulating training data...")
    X, y = manipulateTrainingDataShape(trainData, TRAINING_WINDOW_HOURS, PREDICTION_WINDOW_HOURS)
    # X = np.reshape(X, (X.shape[0], X.shape[1], X.shape[2], 1)) #CNN2D
    assert not np.any(np.isnan(X)), "X has nan"
    # Next line actually labels validation data
    valX, valY = manipulateTrainingDataShape(valData, TRAINING_WINDOW_HOURS, PREDICTION_WINDOW_HOURS)                                    
    # valX = np.reshape(valX, (valX.shape[0], valX.shape[1], valX.shape[2], 1)) #CNN2D
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
            bestModel, numFeatures = train(X, y, valX, valY, config)
            print("***** Training done *****")
            history = valData[-TRAINING_WINDOW_HOURS:, 0:numFeatures].tolist()
            if (FORECASTS_ONE_DAY_AT_A_TIME is True):
                print("Calling getDayAheadForecasts")
                predictedData = getDayAheadForecasts(X, y, bestModel, history, testData, 
                                    TRAINING_WINDOW_HOURS, numFeatures, CARBON_INTENSITY_COL)
            else:
                print("Calling getOneShotForecasts")
                predictedData = getOneShotForecasts(X, y, bestModel, history, testData, 
                                    TRAINING_WINDOW_HOURS, numFeatures)
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
            unScaledPredictedData = common.inverseDataScaling(predicted, ftMax[CARBON_INTENSITY_COL], 
                                ftMin[CARBON_INTENSITY_COL])
            unscaledTestData = common.inverseDataScaling(actual, ftMax[CARBON_INTENSITY_COL], 
                                ftMin[CARBON_INTENSITY_COL])
            print(actualData.shape, predictedData.shape, unscaledTestData.shape, unScaledPredictedData.shape)
            rmseScore, mapeScore, dailyMapeScore = getScores(actualData, predictedData, 
                                        unscaledTestData, unScaledPredictedData, testDates)
            isoDailyMape[ISO] = dailyMapeScore
            print("***** Forecast done *****")

            # print("**** Important features based on valData:")
            # topNFeatures = findImportantFeatures(bestModel, valData, featureList)
            # print("**** Important features based on testData:")
            # topNFeatures = findImportantFeatures(bestModel, testData, featureList)

            print("[BESTMODEL] Overall RMSE score: ", rmseScore)
            print("[BESTMODEL] Overall MAPE score: ", mapeScore)
            # print(scores)
            bestRMSE.append(rmseScore)
            bestMAPE.append(mapeScore)
            print("Mean MAPE: ", mapeScore)
            print("Median MAPE: ", np.percentile(isoDailyMape[ISO], 50))
            print("90th percentile MAPE: ", np.percentile(isoDailyMape[ISO], 90))
            print("95th percentile MAPE: ", np.percentile(isoDailyMape[ISO], 95))
            print("99th percentile MAPE: ", np.percentile(isoDailyMape[ISO], 99))
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

    # data = []
    # for i in range(len(actual)):
    #     row = []
    #     row.append(str(actual[i]))
    #     row.append(str(predicted[i]))
    #     data.append(row)
    # writeOutFile(OUT_FILE_NAME, data)

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
