import csv
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

import common


############################# MACRO START #######################################
print("Start")
# ISO_LIST = ["CISO", "ERCO", "ISNE", "PJM"]
ISO_LIST = ["CISO"]
LOCAL_TIMEZONES = {"CISO": "US/Pacific", "ERCO": "US/Central", "ISNE": "US/Eastern", 
                    "PJM": "US/Eastern", "SE": "CET", "GB": "UTC"}
IN_FILE_NAME = None
OUT_FILE_NAME = None
LOCAL_TIMEZONE = None
PLOT_TITLE = None

COAL = 3
NAT_GAS = 4
NUCLEAR = 5
OIL = 6
HYDRO = 7
SOLAR = 8
WIND = 9
OTHER = 10
NUCLEAR_SE = 3
UNKNOWN_SE = 4
HYDRO_SE = 6
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
START_COL = NAT_GAS


FORECASTS_ONE_DAY_AT_A_TIME = True
NUM_VAL_DAYS = 30
TRAINING_WINDOW_HOURS = 96
if (FORECASTS_ONE_DAY_AT_A_TIME is True):
    TRAINING_WINDOW_HOURS = 24
PREDICTION_WINDOW_HOURS = 96
MODEL_SLIDING_WINDOW_LEN = 24
BUFFER_HOURS = PREDICTION_WINDOW_HOURS - 24
DAY_INTERVAL = 1
MONTH_INTERVAL = 1
CARBON_INTENSITY_COL = 0

NUM_SPLITS = 4


NUMBER_OF_EXPERIMENTS = 1

# NUM_FEATURES = 6
NUM_FEATURES_DICT = {"coal":6, "nat_gas":6, "nuclear":6, "oil":6, "hydro":11, "solar": 11,
                    "wind":11, "other":6, "unknown": 6, "biomass": 6, "geothermal":6}
FUEL = {3:"coal", 4:"nat_gas", 5:"nuclear", 6:"oil", 7:"hydro", 8:"solar",
                    9:"wind", 10:"other"}
# FUEL = {3:"nuclear", 4:"unknown", 5:"wind", 6:"hydro"} # SE
# FUEL = {2:"biomass", 3:"hydro", 4:"coal", 5:"nat_gas", 6:"nuclear", 7:"unknown",
#                     8:"wind", 9:"solar"} # GB
# FUEL = {2:"biomass", 3:"coal", 4:"nat_gas", 5:"geothermal", 6:"hydro", 7:"nuclear",
#                     8:"oil", 9:"solar", 10:"wind", 11:"unknown"} # DE
NUM_FEATURES = NUM_FEATURES_DICT[FUEL[START_COL]]

# carbon intensity -> 1 + 
# hour_of_day (sin, cos) -> 2 + 
# month of year (sin, cos) -> 2 +  (actually, it's day of year)
# weekend -> 1 + 
# energy production by source +
# source production forecasts (solar, wind etc) +
# weather forecasts 
############################# MACRO END #########################################

def initialize(inFileName, localTimezone):
    global START_COL
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])

    print(dataset.head())
    print(dataset.columns)
    dateTime = dataset.index.values
    
    print("\nAdding features related to date & time...")
    modifiedDataset = common.addDateTimeFeatures(dataset, dateTime, START_COL)
    dataset = modifiedDataset
    print("Features related to date & time added")

    bufferPeriod = dataset[DATASET_LIMITER:DATASET_LIMITER+BUFFER_HOURS]
    dataset = dataset[:DATASET_LIMITER]
    bufferDates = dateTime[DATASET_LIMITER:DATASET_LIMITER+BUFFER_HOURS]
    dateTime = dateTime[:DATASET_LIMITER]
    
    # for i in range(START_COL, len(dataset.columns.values)):
    #     col = dataset.columns.values[i]
    #     dataset[col] = dataset[col].astype(np.float64)
    #     print(col, dataset[col].dtype)

    # print("Getting contribution of each energy source...")
    # contribution = getAvgContributionBySource(dataset)
    # print(contribution)

    return dataset, dateTime, bufferPeriod, bufferDates

# convert training data into inputs and outputs (labels)
def manipulateTrainingDataShape(data, trainWindowHours, labelWindowHours): 
    print("Data shape: ", data.shape)
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
        # print(data[trainWindow:labelWindow, 0])
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
    model.add(Dense(20, input_shape=(n_timesteps, n_features), activation='relu')) # 20 for coal, nat_gas, nuclear
    model.add(Dense(50, activation='relu')) # 50 for coal, nat_gas, nuclear
    model.add(Dense(n_outputs))
    opt = tf.keras.optimizers.Adam(learning_rate = 0.01)
    model.compile(loss=lossFunc, optimizer=optimizer[0],
                    metrics=['mean_absolute_error'])
    es = EarlyStopping(monitor='val_loss', mode='min', verbose=1, patience=10)
    mc = ModelCheckpoint('best_model_ann.h5', monitor='val_loss', mode='min', verbose=1, save_best_only=True)
    # fit network
    # hist = model.fit(trainX, trainY, epochs=epochs, batch_size=bSize, verbose=verbose)
    hist = model.fit(trainX, trainY, epochs=epochs, batch_size=batchSize[0], verbose=2,
                        validation_data=(valX, valY), callbacks=[es, mc])
    model = load_model("best_model_ann.h5")
    common.showModelSummary(hist, model)
    return model, n_features

    

# walk-forward validation
def getOneShotForecasts(trainX, trainY, model, history, testData, trainWindowHours, numFeatures):
    global MODEL_SLIDING_WINDOW_LEN
    global BUFFER_HOURS
    # walk-forward validation over each day
    print("Testing...")
    predictions = list()
    for i in range(0, ((len(testData)//24)-(BUFFER_HOURS//24))):
        # predict n days in one shot
        yhat_sequence, newTrainingData = getForecasts(model, history, trainWindowHours, numFeatures)
        predictions.append(yhat_sequence)
        # get real observation and add to history for predicting the next day
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
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
        predictions.append(dayAheadPredictions)

    # evaluate predictions days for each day
    predictedData = np.array(predictions, dtype=np.float64)
    return predictedData


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
# for PREDICTION_WINDOW_HOURS in osw:
for ISO in ISO_LIST:

    PLOT_TITLE = ISO
    # IN_FILE_NAME = "../final_weather_data/"+ISO+"/fuel_forecast/"+ISO+"_"+FUEL[START_COL]+"_2019_clean.csv"
    # OUT_FILE_NAME_PREFIX = "../final_weather_data/"+ISO+"/fuel_forecast/"+ISO+"_NR_Forecast"
    IN_FILE_NAME = "../extn/"+ISO+"/fuel_forecast/"+ISO+"_"+FUEL[START_COL]+"_2019_clean.csv"
    OUT_FILE_NAME_PREFIX = "../extn/"+ISO+"/fuel_forecast/"+ISO+"_"+str(PREDICTION_WINDOW_HOURS)+"_hr_src_prod_forecast"
    if(FORECASTS_ONE_DAY_AT_A_TIME is True):
        OUT_FILE_NAME_PREFIX = OUT_FILE_NAME_PREFIX + "_DA"
    
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
        

        print("Initializing...")
        dataset, dateTime, bufferPeriod, bufferDates = initialize(IN_FILE_NAME, LOCAL_TIMEZONE)
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
        bufferPeriod = bufferPeriod[:, START_COL: START_COL+NUM_FEATURES]
        if(len(bufferDates)>0):
            testDates = np.append(testDates, bufferDates)
            testData = np.vstack((testData, bufferPeriod))

        print("TrainData shape: ", trainData.shape) # (days x hour) x features
        print("ValData shape: ", valData.shape) # (days x hour) x features
        print("TestData shape: ", testData.shape) # (days x hour) x features
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

        featureList = dataset.columns.values[START_COL:START_COL+NUM_FEATURES]
        OUT_FILE_NAME = OUT_FILE_NAME_PREFIX + "_" + featureList[0] + OUT_FILE_SUFFIX + ".csv"
        print("Features: ", featureList)

        print("Scaling data...")
        # unscaledTestData = np.zeros(testData.shape[0])
        # for i in range(testData.shape[0]):
        #     unscaledTestData[i] = testData[i, CARBON_INTENSITY_COL]
        trainData, valData, testData, ftMin, ftMax = common.scaleDataset(trainData, valData, testData)
        print("***** Data scaling done *****")
        print(trainData.shape, valData.shape, testData.shape)


        print("\nManipulating training data...")
        if (FORECASTS_ONE_DAY_AT_A_TIME is True):
            X, y = manipulateTrainingDataShape(trainData, TRAINING_WINDOW_HOURS, TRAINING_WINDOW_HOURS)
            # Next line actually labels validation data
            valX, valY = manipulateTrainingDataShape(valData, TRAINING_WINDOW_HOURS, TRAINING_WINDOW_HOURS)
        else:
            X, y = manipulateTrainingDataShape(trainData, TRAINING_WINDOW_HOURS, PREDICTION_WINDOW_HOURS)
            # Next line actually labels validation data
            valX, valY = manipulateTrainingDataShape(valData, TRAINING_WINDOW_HOURS, PREDICTION_WINDOW_HOURS)
                                        
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
            history = valData[-TRAINING_WINDOW_HOURS:, :].tolist()
            if (FORECASTS_ONE_DAY_AT_A_TIME is True):
                predictedData = getDayAheadForecasts(X, y, bestModel, history, testData, 
                                    TRAINING_WINDOW_HOURS, numFeatures, CARBON_INTENSITY_COL)
            else:
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
        common.writeOutFile(OUT_FILE_NAME, data, featureList[0])

    plotTitle = PLOT_TITLE + "_" + str(featureList[0])
    plotBaseline = False

    # actual = np.reshape(actualData, actualData.shape[0]*actualData.shape[1])
    # predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
    # unScaledPredictedData = inverseDataNormalization(predicted, ftMax[CARBON_INTENSITY_COL], 
    #                         ftMin[CARBON_INTENSITY_COL])

    print("RMSE: ", periodRMSE)
    print("MAPE: ", periodMAPE)
    print("####################", ISO, " done ####################\n\n")

print("End")
