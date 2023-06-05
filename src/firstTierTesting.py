'''
Script to generate first-tier outputs given a saved model & input files.
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
import os

from src.common import scaleDataset, inverseDataScaling, addDateTimeFeatures
import sys
import json5 as json

REGION = "CISO"
# update the direct_emissions file to have the columns in the following order:
# COAL, NAT_GAS, NUCLEAR, OIL, HYDRO, SOLAR, WIND, OTHER
# or, any order is fine, just keep "other" at the end
SOURCES = ["WIND", "HYDRO", "SOLAR", "OTHER", "OIL", "NUCLEAR", "NAT_GAS", "COAL"] # Modify this: Add all the columns in the order specified in CISO_direct_emissions.csv.
SOURCE_COL = [1, 2, 3, 4, 5 ,6, 7, 8] # Add the column numbers for the sources in the same order as above
NUM_FEATURES = 6 
RENEWABLE_SOURCES = ["SOLAR", "WIND", "HYDRO"]
filedir = os.path.dirname(__file__)
WEATHER_FORECAST_IN_FILE_NAME = os.path.normpath(os.path.join(filedir, "weather/extn/" + REGION + "/weather_data/CISO_weather_forecast.csv")) # change CISO_aggregated_weather_data.csv to this name & also change file location as required
LOCAL_TIMEZONE = "US/Pacific"
PARTIAL_FORECAST_AVAILABILITY_LIST = [0, 0, 0, 0, 0, 0, 0, 0],
IN_FILE_NAME = os.path.normpath(os.path.join(filedir, "../data/CISO/day/CISO_direct_emissions.csv")) # change the file location as required
SAVED_MODEL_LOCATION = os.path.normpath(os.path.join(filedir, "../saved_first_tier_models/"+REGION+"/"))
PARTIAL_FORECAST_HOURS = 24
MODEL_SLIDING_WINDOW_LEN = 24 
TRAINING_WINDOW_HOURS = 24
PREDICTION_WINDOW_HOURS =  96
MAX_PREDICTION_WINDOW_HOURS = 96


def runFirstTierTestingScript():
    sourceIdx = 0
    for source in SOURCES:
        print(source)
        OUT_FILE_NAME = os.path.normpath(os.path.join(filedir, "weather/extn/" + REGION + "/weather_data/" + REGION + "_DA_"+source+".csv")) # Change this file location as required
        sourceCol = SOURCE_COL[sourceIdx]
        isRenewableSource = False
        
        print("Initializing...")
        dataset, testDates, weatherDataset = initialize(
                    IN_FILE_NAME, WEATHER_FORECAST_IN_FILE_NAME, sourceCol)
        print("***** Initialization done *****")

        print(dataset.head())
        print(weatherDataset.head())
        numFeatures = NUM_FEATURES
        testData = np.array(dataset.values[:, sourceCol:sourceCol+1])
        wTestData = np.array(weatherDataset.values)


        print(testData.shape, wTestData.shape)
        if (source in RENEWABLE_SOURCES):
            isRenewableSource = True
            numFeatures += 5

        #####################################
        print("Scaling data...")
        # print(wTestData)
        testData, _, _, ftMin, ftMax = scaleDataset(testData, None, None)
        wTestData, _, _, wFtMin, wFtMax = scaleDataset(wTestData, None, None)
        # This part is not right. Ideally we should scale using min & max values from training data.
        # So, min & max values of each feature needs to be saved along with the model.
        # TODO: We will do that later.
        #####################################

        savedModelName = f"{SAVED_MODEL_LOCATION}/{source}.h5"
        model = load_model(savedModelName)
        model.summary()

        history = testData[-TRAINING_WINDOW_HOURS:, :]
        weatherData = wTestData[-PREDICTION_WINDOW_HOURS:, :]
        history = history.tolist()
        predictedData = getSourceProductionForecasts(model, history, testData, numFeatures, wTestData, 
                       weatherData, None, isRenewableSource)
        
        predictedData = predictedData.astype(np.float64)
        print("PredictedData shape: ", predictedData.shape)
        predicted = np.reshape(predictedData, predictedData.shape[0]*predictedData.shape[1])
        print("predicted.shape: ", predicted.shape)
        unscaledPredictedData = inverseDataScaling(predicted, 
                    ftMax[0], ftMin[0])
        
        writeSourceProductionForecastsToFile(testDates, unscaledPredictedData,
                                             source, OUT_FILE_NAME)
        
        sourceIdx += 1

    return

def initialize(inFileName, weatherForecastInFileName, startCol):
    # load the new file
    dataset = pd.read_csv(inFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])

    # print(dataset.head())
    # print(dataset.columns)
    dateTime = dataset.index.values

    print()
    weatherDataset = pd.read_csv(weatherForecastInFileName, header=0, infer_datetime_format=True, 
                            parse_dates=['datetime'], index_col=['datetime'])
    weatherDateTime = weatherDataset.index.values
    # print(weatherDataset.head())
    
    print("\nAdding features related to date & time...")
    # modifiedDataset = common.addDateTimeFeatures(dataset, dateTime, startCol)
    # dataset = modifiedDataset

    # Adding in weather dataset, as we need for 96 hours
    modifiedWeatherDataset = addDateTimeFeatures(weatherDataset, weatherDateTime, -1)
    weatherDataset = modifiedWeatherDataset
    print("Features related to date & time added")
    
    for i in range(startCol, len(dataset.columns.values)):
        col = dataset.columns.values[i]
        dataset[col] = dataset[col].astype(np.float64)
        # print(col, dataset[col].dtype)

    return dataset, weatherDateTime, weatherDataset

def getSourceProductionForecasts(model, history, testData, 
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
                yhat_sequence = getForecasts(model, tempHistory, 
                            numFeatures, weatherData[j:j+24])
            else:
                yhat_sequence = getForecasts(model, tempHistory, 
                            numFeatures, weatherData[j:j+24, :5])
            # print(yhat_sequence)
            # add current prediction to history for predicting the next day
            if (j==0 and partialSourceProductionForecast is not None):
                for k in range(24):
                    yhat_sequence[k] = partialSourceProductionForecast[currentDayHours+k]
            dayAheadPredictions.extend(yhat_sequence)
            # latestHistory = np.zeros((24, 6)) # 24 because last 24 values, 6 because CI + date/time features
            # latestHistory[:, 1:] = wTestData[currentDayHours+j:currentDayHours+j+24, :5]
            # latestHistory = latestHistory.tolist()
            for k in range(24):
                tempHistory[k] = yhat_sequence[k]
            # tempHistory = latestHistory

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
    data = np.reshape(data, (data.shape[0], 1))
    # retrieve last observations for input data
    input_x = data[-TRAINING_WINDOW_HOURS:]
    if (weatherData is not None):
        # print(input_x.shape, weatherData.shape)
        input_x = np.append(input_x, weatherData, axis=1)
        # print("inputX shape, numFeatures: ", input_x.shape, numFeatures)
    # reshape into [1, n_input, num_features]
    input_x = input_x.reshape((1, len(input_x), numFeatures))
    # print("ip_x shape: ", input_x.shape)
    # print(input_x)
    yhat = model.predict(input_x, verbose=0)
    # we only want the vector forecast
    yhat = yhat[0]
    return yhat

def writeSourceProductionForecastsToFile(formattedTestDates, unscaledPredictedData,
                                        source, outFileName):
    data = []
    
    for i in range(len(unscaledPredictedData)):
        row = []
        row.append(str(formattedTestDates[i]))
        row.append(str(unscaledPredictedData[i]))
        data.append(row)
    writeMode = "w"
    print("Writing to ", outFileName, "...")
    fields = ["UTC time", "avg_"+source.lower()+"_production_forecast"]
    
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
    runFirstTierTestingScript()