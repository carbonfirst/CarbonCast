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
IN_SLIDING_WINDOW_LEN = configurationData["IN_SLIDING_WINDOW_LEN"]
OUT_SLIDING_WINDOW_LEN = configurationData["OUT_SLIDING_WINDOW_LEN"]
TOP_N_FEATURES = configurationData["TOP_N_FEATURES"]
DAY_INTERVAL = 1
MONTH_INTERVAL = 1
CARBON_INTENSITY_COL = 0
NUM_SPLITS = 4
NUMBER_OF_EXPERIMENTS = configurationData["NUMBER_OF_EXPERIMENTS_PER_ISO"]

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

def scaleDataset(trainData, valData, testData):
    # Scaling columns to range (0, 1)
    row, col = trainData.shape[0], trainData.shape[1]
    ftMin, ftMax = [], []
    for i in range(col):
        fmax= trainData[0, i]
        fmin = trainData[0, i]
        for j in range(len(trainData[:, i])):
            if(fmax < trainData[j, i]):
                fmax = trainData[j, i]
            if (fmin > trainData[j, i]):
                fmin = trainData[j, i]
        ftMin.append(fmin)
        ftMax.append(fmax)

    for i in range(col):
        if((ftMax[i] - ftMin[i]) == 0):
            continue
        trainData[:, i] = (trainData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])
        valData[:, i] = (valData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])
        testData[:, i] = (testData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])

    return trainData, valData, testData, ftMin, ftMax

def inverseDataScaling(data, cmax, cmin):
    cdiff = cmax-cmin
    unscaledData = np.zeros_like(data)
    for i in range(data.shape[0]):
        unscaledData[i] = data[i]*cdiff + cmin
    return unscaledData


def analyzeTimeSeries(dataset, trainData, unscaledCarbonIntensity, dateTime):
    global NUM_FEATURES
    global LOCAL_TIMEZONE
    global START_COL
    # checkStationarity(dataset)
    # showTrends(dataset, dateTime, LOCAL_TIMEZONE)
    print("Plotting each feature distribution...")
    features = dataset.columns.values[START_COL:START_COL+NUM_FEATURES]
    trainDataFrame = pd.DataFrame(unscaledCarbonIntensity, columns=features)
    createFeatureViolinGraph(features, trainDataFrame, dateTime)
    print("***** Feature distribution plotting done *****")
    return

def checkStationarity(dataset):
    print(dataset.columns)
    carbon = dataset["carbon_intensity"].values
    print(len(carbon))
    result = adfuller(carbon, autolag='AIC')
    print(f'ADF Statistic: {result[0]}')
    print(f'n_lags: {result[1]}')
    print(f'p-value: {result[1]}')
    for key, value in result[4].items():
        print('Critial Values:')
        print(f'   {key}, {value}')
    return

def showTrends(dataset, dateTime, localTimeZone):
    carbon = np.array(dataset["carbon_intensity"].values)
    carbon = np.resize(carbon, (carbon.shape[0]//24, 24))
    dailyAvgCarbon = np.mean(carbon, axis = 1)
    dates = getDatesInLocalTimeZone(dateTime)    
    
    fig, ax = plt.subplots()
    ax.plot(dates, dailyAvgCarbon)
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d, %H:%M"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=MONTH_INTERVAL, tz=localTimeZone))
    
    plt.xlabel("Local time")
    plt.ylabel("Carbon Intensity (g/kWh)")
    # plt.title("Carbon Intensity Trend")
    plt.grid(axis="x")
    plt.xticks(rotation=90)

    plt.legend()
    # plt.show()
    return

def createFeatureViolinGraph(features, dataset, dateTime):
    # print(features)
    # print(dataset)
    dataset = dataset.astype(np.float64)
    plt.figure() #figsize=(12, 6)
    datasetMod = dataset.melt(var_name='Column', value_name='Normalized values')
    ax = sns.violinplot(x='Column', y='Normalized values', data=datasetMod, scale="count")
    # ax = plt.boxplot(dataset, vert=True)
    # for ft in features:
    #     print(ft, np.amax(dataset[ft].values), np.amin(dataset[ft].values))
    _ = ax.set_xticklabels(features, rotation=80)
    plt.show()
    return

def getDatesInLocalTimeZone(dateTime):
    global LOCAL_TIMEZONE
    dates = []
    fromZone = pytz.timezone("UTC")
    for i in range(0, len(dateTime), 24):
        day = pd.to_datetime(dateTime[i]).replace(tzinfo=fromZone)
        day = day.astimezone(LOCAL_TIMEZONE)
        dates.append(day)    
    return dates

def getAvgContributionBySource(dataset):
    contribution = {}
    for col in dataset.columns:
        if "frac" in col:
            avgContribution = np.mean(dataset[col].values)
            print(col, ": ", avgContribution)
            contribution[col[5:]] = avgContribution
    contribution = dict(sorted(contribution.items(), key=lambda item: item[1]))
    return contribution

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

def splitDataset(dataset, testDataSize, valDataSize): # testDataSize, valDataSize are in days
    print("No. of rows in dataset:", len(dataset))
    valData = None
    numTestEntries = testDataSize * 24
    numValEntries = valDataSize * 24
    trainData, testData = dataset[:-numTestEntries], dataset[-numTestEntries:]
    trainData, valData = trainData[:-numValEntries], trainData[-numValEntries:]
    print("No. of rows in training set:", len(trainData))
    print("No. of rows in validation set:", len(valData))
    print("No. of rows in test set:", len(testData))
    return trainData, valData, testData

# convert history into inputs and outputs
def manipulateTrainingData(trainData, inSlidingWindowLen, outSlidingWindowLen): 
    # flatten data
    data = trainData.reshape((trainData.shape[0]*trainData.shape[1], 
                                    trainData.shape[2]))
    print("New data shape: ", data.shape)
    X, y = list(), list()
    # step over the entire history one time step at a time
    for i in range(len(data)-(inSlidingWindowLen+outSlidingWindowLen)+1):
        # define the end of the input sequence
        trainWindow = i + inSlidingWindowLen
        labelWindow = trainWindow + outSlidingWindowLen
        xInput = data[i:trainWindow, :]
        # xInput = xInput.reshape((len(xInput), 1))
        X.append(xInput)
        y.append(data[trainWindow:labelWindow, CARBON_INTENSITY_COL])
    return np.array(X), np.array(y)

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

    # train1X, val1X = trainX[:-NUM_VAL_DAYS*OUT_SLIDING_WINDOW_LEN], trainX[-NUM_VAL_DAYS*OUT_SLIDING_WINDOW_LEN:]
    # train1Y, val1Y = trainY[:-NUM_VAL_DAYS*OUT_SLIDING_WINDOW_LEN], trainY[-NUM_VAL_DAYS*OUT_SLIDING_WINDOW_LEN:]
    # print(train1X.shape, train1Y.shape, val1X.shape, val1Y.shape)
    # print("Training set 1...")
    # hist = model.fit(train1X, train1Y, epochs=epochs, batch_size=bs, verbose=verbose,
    #                     validation_data=(val1X, val1Y), callbacks=[es, mc])
    # model = load_model("best_model.h5")
    # print("Training set 2 (walk forward validation)...")
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
def validate(trainX, trainY, model, history, testData, inSlidingWindowLen, numFeatures):
    # walk-forward validation over each day
    print("Testing...")
    predictions = list()
    for i in range(len(testData)):
        # predict the day
        yhat_sequence, newTrainingData = predict(model, history, inSlidingWindowLen, numFeatures)
        # store the predictions
        predictions.append(yhat_sequence)
        newLabel = testData[i,:,0].reshape(1, testData.shape[1])
        np.append(trainX, newTrainingData)
        np.append(trainY, newLabel)
        # get real observation and add to history for predicting the next day
        # print(testData.shape, testData[i].shape)
        # model = updateModel(model, trainX, trainY)
        history.extend(testData[i, :, :].tolist())
    # evaluate predictions days for each day
    predictedData = np.array(predictions)
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

def predict(model, history, inSlidingWindowLen, numFeatures):
    # flatten data
    data = np.array(history)
    # retrieve last observations for input data
    input_x = data[-inSlidingWindowLen:]
    # reshape into [1, n_input, num_features]
    input_x = input_x.reshape((1, len(input_x), numFeatures))
    # input_x = np.reshape(input_x, (1, input_x.shape[0], input_x.shape[1], 1)) #CNN2D
    # forecast the next day
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

def calcCarbonIntensity(sourceVal, energySource):
    # both variables should have sources in the same order
    carbonRate = {"coal":908, "nat_gas":440, "nuclear":15, "oil":890, "hydro":13.5, 
                        "solar":50, "wind":22.5, "other":0}
    carbonIntensity = 0
    sum = 0
    for val in sourceVal:
        sum += val
    idx=0
    for idx in range(len(energySource)):
        source = energySource[idx]
        sourceContribFrac = sourceVal[idx]/sum
        carbonIntensity += (sourceContribFrac * carbonRate[source])
    return carbonIntensity

def calcCarbonIntensityFromForecasts(dataset):
    carbonIntensity = [None]* len(dataset)
    sourceForecasts = []
    energySource = []
    for col in dataset.columns:
        if("forecast" in col):
            sourceForecasts.append(dataset[col].values)
            energySource.append(col[9:]) # removing "forecast_"
            # sources are stored in the same order
    sourceForecasts = np.array(sourceForecasts, dtype=np.float)
    sourceForecasts = sourceForecasts.T
    for i in range(24):
        carbonIntensity[i] = dataset.iloc[i][0]
    for i in range(24, len(dataset)):
        carbonIntensity[i] = round(calcCarbonIntensity(sourceForecasts[i-24, :], energySource), 6)
    return carbonIntensity

def readDataFile():
    pass

def writeOutFile(outFileName, data):
    print("Writing to ", outFileName, "...")
    fields = ['Actual', 'Predicted']
    
    # writing to csv file 
    with open(outFileName, 'w') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile)   
        # writing the fields 
        csvwriter.writerow(fields) 
        # writing the data rows 
        csvwriter.writerows(data)

def plotGraphs(actualVal, predictedVal, testDates, plotTitle, localTimeZone, 
            plotBaseline=False, predictedLSTMVal = None):
    # print(actualVal)
    # print(predictedVal)
    
    baseline = actualVal[:-1]
    baseline = np.insert(baseline, 0, actualVal[0])
    localTestDates = []
    fromZone = pytz.timezone("UTC")
    for i in range(0, len(testDates)):
        localTestDay = pd.to_datetime(testDates[i]).replace(tzinfo=fromZone)
        localTestDay = localTestDay.astimezone(localTimeZone)
        localTestDates.append(localTestDay)

    # localTestDates = []
    # for i in range(72):
    #     localTestDates.append(i)

    
    fig, ax = plt.subplots()
    ax.plot(localTestDates, actualVal, label="Actual carbon intensity", color="k")
    if(plotBaseline is True):
        ax.plot(localTestDates, baseline, label="baseline")
    ax.plot(localTestDates, predictedVal, label="Predicted carbon intensity", color="r", 
            linestyle="dashed", linewidth=2)
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d, %H:%M"))
    # ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    # ax.xaxis.set_major_locator(mdates.HourLocator(interval=12, tz=localTimeZone))
    # ax.set_ylim(ymin=0)
    # ax.set_ylim(ymax=450)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=DAY_INTERVAL, tz=localTimeZone))
    
    # plt.xlabel("Local time")
    plt.xlabel("Local Time", fontsize=18)
    plt.ylabel("Carbon Intensity (g/KWh)", fontsize=18)
    # plt.title(plotTitle)
    plt.grid(axis="x")
    plt.xticks(rotation=45, fontsize=16)
    plt.yticks(fontsize=16)
    # plt.xticks(np.arange(0, 73, 12.0))

    plt.legend()
    # plt.show()

def plotBoxplots(isoDailyMape):
    fig = plt.figure()
    
    # get dictionary returned from boxplot
    fig, ax = plt.subplots()
    bp_dict = ax.boxplot(isoDailyMape.values(), vert=True)
    # print(bp_dict)
    ax.set_xticklabels(isoDailyMape.keys())
    for line in bp_dict['medians']:
        # get position data for median line
        # print(line.get_xydata())
        x, y = line.get_xydata()[1] # top of median line
        # print(x)
        # print(y)
        # overlay median value
        plt.text(x, y, '%.1f' % y,
            horizontalalignment='center') # draw above, centered

    # for line in bp_dict['boxes']:
    #     x, y = line.get_xydata()[0] # bottom of left line
    #     plt.text(x,y, '%.1f' % y,
    #         horizontalalignment='center', # centered
    #         verticalalignment='top')      # below
    #     x, y = line.get_xydata()[3] # bottom of right line
    #     plt.text(x,y, '%.1f' % y,
    #         horizontalalignment='center', # centered
    #             verticalalignment='top')      # below
    plt.xlabel("Zones/ISOs")
    plt.ylabel("MAPE (%)")
    plt.title("MAPE boxplots")
    # plt.grid(axis="x")

    return

def showPlots():
    plt.show()

def plotFeatures(X, trainDates, features, localTimeZone, selectedFeatures=False):
    localTrainDates = []
    fromZone = pytz.timezone("UTC")
    for i in range(0, len(trainDates)):
        localTrainDay = pd.to_datetime(trainDates[i]).replace(tzinfo=fromZone)
        localTrainDay = localTrainDay.astimezone(localTimeZone)
        localTrainDates.append(localTrainDay)
    plotData = X #np.reshape(X, (X.shape[0]*X.shape[1], X.shape[2]))
    # plotData = plotData[:31*24, :] # plot features for only 1 month --> January in this case
    # localTrainDates = localTrainDates[:31*24]

    idx = 1
    ax = None
    if selectedFeatures is False:
        rows = len(features)
        for i in range(len(features)):
            print("[", i, features[i], "]")
            if("sin" in features[i] or "cos" in features[i] or "weekend" in features[i]):
                rows -=1
        print("Num features without datetime: ", rows)
        for i in range(len(features)):
            if("sin" in features[i] or "cos" in features[i] or "weekend" in features[i]):
                continue
            ax = plt.subplot(rows, 1, idx)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=DAY_INTERVAL, tz=localTimeZone))
            idx+=1
            plt.plot(localTrainDates, plotData[:, i])
            plt.xticks(rotation=30)
            plt.title(features[i], y=0.3, loc='right')
    else:
        rows = 0
        fig, ax = plt.subplots()
        for i in range(len(features)):
            if (selectedFeatures in features[i]):
                rows +=1
        for i in range(len(features)):
            if (selectedFeatures not in features[i]):
                continue
            if (selectedFeatures in features[i] and "forecast" not in features[i]):
                continue
            print("[", i, features[i], "]")
            # ax = plt.subplot(rows, 1, idx)
            # idx+=1
            ax.plot(localTrainDates, plotData[:, i], label=features[i])
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=DAY_INTERVAL, tz=localTimeZone))
        plt.xlabel("Local time")
        plt.ylabel("Value")
        plt.title("Features")
        # plt.grid(axis="x")
        plt.xticks(rotation=30)
        plt.legend()

    plt.show()
    return

def getScores(scaledActual, scaledPredicted, unscaledActual, unscaledPredicted, dates):
    print("Actual data shape, Predicted data shape: ", scaledActual.shape, scaledPredicted.shape)
    # scores = list()
    # # calculate an RMSE score for each hour
    # for i in range(actualData.shape[1]):
    #     # calculate mse
    #     mse = mean_squared_error(actualData[:, i], predictedData[:, i])
    #     # calculate rmse
    #     rmse = math.sqrt(mse)
    #     # store
    #     scores.append(round(rmse, 6))
    # # calculate overall RMSE
    # s = 0
    # for row in range(actualData.shape[0]):
    #     # print(actualData[row])
    #     # print(predictedData[row])
    #     for col in range(actualData.shape[1]):
    #         s += (actualData[row, col] - predictedData[row, col])**2
    # score = math.sqrt(s / (actualData.shape[0] * actualData.shape[1]))

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

def plotPieChart(iso, data, features):
    fig = plt.figure()
    avgdata = np.mean(data, axis=0)
    sum = np.sum(avgdata)
    avgdata/=sum
    print(avgdata, np.sum(avgdata))
    plt.pie(avgdata, labels = features, autopct='%1.1f%%',)
    plt.title(iso+" - contribution by source")
    return

def shapFeatureExplanation():

    return

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
    trainData, valData, testData = splitDataset(dataset.values, NUM_TEST_DAYS, 
                                            NUM_VAL_DAYS)
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
    unscaledTestData = np.zeros(testData.shape[0])
    unscaledTrainCarbonIntensity = np.zeros(trainData.shape[0])
    for i in range(testData.shape[0]):
        unscaledTestData[i] = testData[i, CARBON_INTENSITY_COL]
    for i in range(trainData.shape[0]):
        unscaledTrainCarbonIntensity[i] = trainData[i, CARBON_INTENSITY_COL]
    trainData, valData, testData, ftMin, ftMax = scaleDataset(trainData, valData, testData)
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

    # restructure into windows of hourly data
    trainData = np.array(np.split(trainData, len(trainData)/IN_SLIDING_WINDOW_LEN), dtype=np.float64)
    valData = np.array(np.split(valData, len(valData)/OUT_SLIDING_WINDOW_LEN), dtype=np.float64)
    testData = np.array(np.split(testData, len(testData)/OUT_SLIDING_WINDOW_LEN), dtype=np.float64)

    print("\nManipulating training data...")
    X, y = manipulateTrainingData(trainData, IN_SLIDING_WINDOW_LEN, OUT_SLIDING_WINDOW_LEN)
    # X = np.reshape(X, (X.shape[0], X.shape[1], X.shape[2], 1)) #CNN2D
    assert not np.any(np.isnan(X)), "X has nan"
    # Next line actually labels validation data
    valX, valY = manipulateTrainingData(valData, IN_SLIDING_WINDOW_LEN, OUT_SLIDING_WINDOW_LEN)                                    
    # valX = np.reshape(valX, (valX.shape[0], valX.shape[1], valX.shape[2], 1)) #CNN2D
    print("***** Training data manipulation done *****")
    print("X.shape, y.shape: ", X.shape, y.shape)

    ######################## START #####################

    featureLeftOut = []
    featureEffect = {}
    datasetBkp = dataset
    trainDataBkp = trainData
    testDataBkp = testData
    idx = 0
    NUM_FEATURES_BKP = NUM_FEATURES
    X_bkp = X
    baselineRMSE, baselineMAPE = [], []
    bestRMSE, bestMAPE = [], []
    
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
            history = valData[-1,:, 0:numFeatures].tolist()
            predictedData = validate(X, y, bestModel, history, testData, IN_SLIDING_WINDOW_LEN, 
                                                                    numFeatures)
            actualData = testData[:, :, 0]
            actual = np.reshape(actualData, actualData.shape[0]*actualData.shape[1])
            predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
            unScaledPredictedData = inverseDataScaling(predicted, ftMax[CARBON_INTENSITY_COL], 
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
            plotTitle = PLOT_TITLE + "_" + str(OUT_SLIDING_WINDOW_LEN) + "hr_" + str(NUM_FEATURES) + "ft"
            # plotGraphs(unscaledTestData[-24*7:], unScaledPredictedData[-24*7:], testDates[-24*7:], 
            #                     plotTitle, LOCAL_TIMEZONE, False)
            # for i in range(24*7-1, -1, -1):
            #     print(unScaledPredictedData[-i])
            # for mape in isoDailyMape[ISO]:
            #     print(mape)


        # sortMape = bestMAPE
        # sortMape.sort()
        # print(bestMAPE, sortMape)
        # # print(sortMape)
        # curMean = (sortMape[0]+sortMape[1]+sortMape[2])/3
        # # configMapeDict[config] = curMean
        # if bestMean>curMean:
        #     bestMean = curMean
        #     bestConfig = config
        # print("Best config: ", bestConfig, "best mean: ", bestMean)
    
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

    plotTitle = PLOT_TITLE + "_" + str(OUT_SLIDING_WINDOW_LEN) + "hr_" + str(NUM_FEATURES) + "ft"
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
showPlots()

print("End")
