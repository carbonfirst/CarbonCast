'''
Script to generate second-tier outputs given a saved model & input files.
'''

import csv
from datetime import datetime as dt
from datetime import timezone as tz

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz as pytz
from keras.layers import Dense, Flatten
from keras.layers import LSTM
from keras.models import Sequential
from scipy.sparse import data
import tensorflow as tf
from tensorflow import keras
from keras.callbacks import EarlyStopping
from keras.callbacks import ModelCheckpoint
from keras.models import load_model
from keras.layers import RepeatVector

from src.common import scaleDataset, inverseDataScaling, addDateTimeFeatures
import sys
import json5 as json
import os

filedir = os.path.dirname(__file__)
REGION = "CISO"
IN_FILE_NAME = os.path.normpath(os.path.join(filedir, "../data/CISO/day/CISO_direct_emissions.csv")) # change the file location as required
FORECAST_IN_FILE_NAME = os.path.normpath(os.path.join(filedir,  "weather/extn/" + REGION +  "/weather_data/" + REGION + "_96hr_forecasts_DA.csv"))
OUT_FILE_NAME = os.path.normpath(os.path.join(filedir, "weather/extn/"+ REGION + "_direct_96_hour_CI_forecasts.csv")) # Change this file location as required
START_COL=1
NUM_FEATURES = 6 
NUM_FORECAST_FEATURES = 12
LOCAL_TIMEZONE = "US/Pacific"
SAVED_MODEL_LOCATION = os.path.normpath(os.path.join(filedir, "../saved_second_tier_models/direct/")) # change this location as required
MODEL_SLIDING_WINDOW_LEN = 24 
TRAINING_WINDOW_HOURS = 24
PREDICTION_WINDOW_HOURS =  96
MAX_PREDICTION_WINDOW_HOURS = 96


def runSecondTierScript():
    print("Initializing...")
    dataset, testDates, forecastDataset = initialize(IN_FILE_NAME, FORECAST_IN_FILE_NAME, START_COL)
    print("***** Initialization done *****")

    print(dataset.head())
    print(forecastDataset.head())
       
    numHistoricalAndDateTimeFeatures = NUM_FEATURES
    numForecastFeatures = NUM_FORECAST_FEATURES
    testData = np.array(dataset.values[:, 0:1])
    wTestData = np.array(forecastDataset.values[:, 0:numHistoricalAndDateTimeFeatures+numForecastFeatures-1])
    print("total features = ", numHistoricalAndDateTimeFeatures+numForecastFeatures)
    print(testData.shape, wTestData.shape)

    #####################################
    print("Scaling data...")
    # print(wTestData)
    testData, _, _, ftMin, ftMax = scaleDataset(testData, None, None)
    wTestData, _, _, wFtMin, wFtMax = scaleDataset(wTestData, None, None)
    # This part is not right. Ideally we should scale using min & max values from training data.
    # So, min & max values of each feature needs to be saved along with the model.
    # TODO: We will do that later.
    #####################################

    savedModelName = f"{SAVED_MODEL_LOCATION}/{REGION}.h5"
    model = load_model(savedModelName)
    model.summary()

    history = testData[-TRAINING_WINDOW_HOURS:, :]
    weatherData = wTestData[-PREDICTION_WINDOW_HOURS:, :]
    history = history.tolist()
    predictedData = getCIForecasts(model, history, testData, 
                                numHistoricalAndDateTimeFeatures+numForecastFeatures, 
                                wTestData, weatherData)
    print("***** Forecast done *****")

    predictedData = predictedData.astype(np.float64)
    predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
    unscaledPredictedData = inverseDataScaling(predicted, ftMax[0], ftMin[0])

    print(unscaledPredictedData)

    writeCIForecastsToFile(testDates, unscaledPredictedData, OUT_FILE_NAME)   

    return

def initialize(inFileName, forecastInFileName, startCol):
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])

    # print(dataset.head())
    # print(dataset.columns)
    dateTime = dataset.index.values

    forecastDataset = pd.read_csv(forecastInFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['datetime'], index_col=['datetime'])
    forecastDateTime = forecastDataset.index.values
    
    print("\nAdding features related to date & time...")
    # modifiedDataset = common.addDateTimeFeatures(dataset, dateTime, startCol)
    # dataset = modifiedDataset

    # Adding in weather dataset, as we need for 96 hours
    modifiedForecastDataset = addDateTimeFeatures(forecastDataset, forecastDateTime, -1)
    forecastDataset = modifiedForecastDataset
    print(forecastDataset.head())
    print("Features related to date & time added")
    
    for i in range(startCol, len(dataset.columns.values)):
        col = dataset.columns.values[i]
        dataset[col] = dataset[col].astype(np.float64)
        # print(col, dataset[col].dtype)

    return dataset, forecastDateTime, forecastDataset

def getCIForecasts(model, history, testData, numFeatures, 
                   wTestData = None, weatherData = None):
    # walk-forward validation over each day
    print("Testing...")
    # print(ciMin, ciMax)
    predictions = list()
    weatherIdx = 0
    for i in range(0, ((len(testData)//24))):
        dayAheadPredictions = list()
        tempHistory = history.copy()
        currentDayHours = i* MODEL_SLIDING_WINDOW_LEN
        for j in range(0, MAX_PREDICTION_WINDOW_HOURS, 24):
            if (j >= PREDICTION_WINDOW_HOURS):
                continue
            yhat_sequence = getForecasts(model, tempHistory, 
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

def getForecasts(model, history, numFeatures, weatherData):
    # flatten data
    data = np.array(history, dtype=np.float64)
    data = np.reshape(data, (data.shape[0], 1))
    # retrieve last observations for input data
    input_x = data[-TRAINING_WINDOW_HOURS:]
    input_x = np.append(input_x, weatherData, axis=1)
    # reshape into [1, n_input, num_features]
    input_x = input_x.reshape((1, len(input_x), numFeatures))
    # print("ip_x shape: ", input_x.shape)
    yhat = model.predict(input_x, verbose=0)
    # we only want the vector forecast
    yhat = yhat[0]
    return yhat

def writeCIForecastsToFile(formattedTestDates, unscaledPredictedData, outFileName):

    data = []
    
    for i in range(len(unscaledPredictedData)):
        row = []
        row.append(str(formattedTestDates[i]))
        row.append(str(unscaledPredictedData[i]))
        data.append(row)
    writeMode = "w"
    print("Writing to ", outFileName, "...")
    fields = ["UTC time", "forecasted_avg_carbon_intensity"]
    
    # writing to csv file 
    with open(outFileName, writeMode) as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile)   
        # writing the fields
        if (writeMode == "w"): 
            csvwriter.writerow(fields) 
        # writing the data rows 
        csvwriter.writerows(data)
    return

if __name__ == "__main__":
    runSecondTierScript()