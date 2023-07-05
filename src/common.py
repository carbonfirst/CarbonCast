import numpy as np
import pandas as pd
import pytz as pytz
import tensorflow as tf
import matplotlib.pyplot as plt
import csv
import math
import seaborn as sns
from statsmodels.tsa.stattools import adfuller
import matplotlib.dates as mdates



def inverseDataScaling(data, cmax, cmin):
    cdiff = cmax-cmin
    unscaledData = np.zeros_like(data)
    for i in range(data.shape[0]):
        unscaledData[i] = round(max(data[i]*cdiff + cmin, 0), 5)
    return unscaledData

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

def getScores(scaledActual, scaledPredicted, unscaledActual, unscaledPredicted):
    print("Actual data shape, Predicted data shape: ", scaledActual.shape, scaledPredicted.shape)
    mse = tf.keras.losses.MeanSquaredError()
    rmseScore = round(math.sqrt(mse(scaledActual, scaledPredicted)), 6)

    mape = tf.keras.losses.MeanAbsolutePercentageError()
    mapeTensor =  mape(unscaledActual, unscaledPredicted)
    mapeScore = mapeTensor.numpy()

    return rmseScore, mapeScore

def writeOutFile(outFileName, data, fuel, writeMode):
    print("Writing to ", outFileName, "...")
    fields = ["datetime", fuel+"_actual", "avg_"+fuel+"_production_forecast"]
    if (fuel == "carbon_intensity"):
        fields = ["datetime", fuel+"_actual", "avg_"+fuel+"_forecast"]
    
    # writing to csv file 
    with open(outFileName, writeMode) as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile)   
        # writing the fields
        if (writeMode == "w"): 
            csvwriter.writerow(fields) 
        # writing the data rows 
        csvwriter.writerows(data)

def dumpRandomDataToFile(fileName, data, writeMode):
    with open(fileName, writeMode) as dumpFile:
        dumpFile.writelines(data)

def showPlots():
    plt.show()

def scaleDataset(trainData, valData, testData):
    # Scaling columns to range (0, 1)
    row, col = trainData.shape[0], trainData.shape[1]
    # print(row, col)
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
        if (valData is not None):
            valData[:, i] = (valData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])
        if (testData is not None):
            testData[:, i] = (testData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])
        # print(trainData[:, i])
        # print(ftMax[i], ftMin[i])

    return trainData, valData, testData, ftMin, ftMax

def scaleTestDataWithTrainingValues(data, ftMin, ftMax):
    # Scaling columns to range (0, 1)
    col = data.shape[1]
    for i in range(col):
        if((ftMax[i] - ftMin[i]) == 0):
            continue
        for j in range(len(data)):
            # print(data[j, i], ftMin[i], ftMax[i])
            data[j, i] = (data[j, i] - ftMin[i]) / (ftMax[i] - ftMin[i])
        
    return data

def scaleColumn(data, ftMin, ftMax):
    # Scaling columns to range (0, 1)
    col = len(data)
    for i in range(col):
        # print(data[i], ftMin, ftMax)
        data[i] = (data[i] - ftMin) / (ftMax - ftMin)
        # print(data[i])

    return data

def inverseScaleColumn(data, cmin, cmax):
    cdiff = cmax-cmin
    unscaledData = np.zeros_like(data)
    for i in range(data.shape[0]):
        unscaledData[i] = round(max(data[i]*cdiff + cmin, 0), 5)
    return unscaledData

def getMinMaxFeatureValues(minMaxFeatureFileName, areForecastsFeatures):
    print("Min max feature file: ", minMaxFeatureFileName)
    ftMin = []
    ftMax = []
    wftMin = []
    wftMax = []
    minValues = None
    maxValues = None
    wMinValues = None
    wMaxValues = None
    with open(minMaxFeatureFileName, "r") as f:
        minValues = f.readline()
        minValues = minValues[1:-2] # -2 because the line ends with ]\n
        minValues = minValues.split(",")
        maxValues = f.readline()
        maxValues = maxValues[1:-2] # -2 because the line ends with ]\n
        maxValues = maxValues.split(",")
        if (areForecastsFeatures is True):
            wMinValues = f.readline()
            wMinValues = wMinValues[1:-2] # -2 because the line ends with ]\n
            wMinValues = wMinValues.split(",")
            wMaxValues = f.readline()
            wMaxValues = wMaxValues[1:-2] # -2 because the line ends with ]\n
            wMaxValues = wMaxValues.split(",")

    ftMin.append(float(minValues[0].strip()))
    ftMax.append(float(maxValues[0].strip()))

    for i in range(1, len(minValues)):
        wftMin.append(float(minValues[i].strip()))
        wftMax.append(float(maxValues[i].strip()))

    if (wMinValues is not None):
        for i in range(len(wMinValues)):
            wftMin.append(float(wMinValues[i].strip()))
            wftMax.append(float(wMaxValues[i].strip()))

    # print(ftMin, ftMax, wftMin, wftMax)
    return ftMin, ftMax, wftMin, wftMax

# Date time feature engineering
def addDateTimeFeatures(dataset, dateTime, startCol):
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
    # print(zero, one)
    # hour of day feature
    dataset.insert(loc=loc, column="hour_sin", value=hourSin)
    dataset.insert(loc=loc+1, column="hour_cos", value=hourCos)
    # month of year feature
    dataset.insert(loc=loc+2, column="month_sin", value=monthSin)
    dataset.insert(loc=loc+3, column="month_cos", value=monthCos)
    # is weekend feature
    dataset.insert(loc=loc+4, column="weekend", value=weekendList)

    # print(dataset.columns)
    # print(dataset.head())
    return dataset

def splitDataset(dataset, testDataSize, valDataSize, predictionWindowDiff=0): # testDataSize, valDataSize are in days
    print("No. test days:", testDataSize)
    print("No. val days:", valDataSize)
    print("No. of rows in dataset:", len(dataset))
    valData = None
    numTestEntries = testDataSize * 24
    numValEntries = valDataSize * 24
    trainData, testData = dataset[:-numTestEntries], dataset[-numTestEntries:]
    fullTrainData = np.copy(trainData)
    trainData, valData = trainData[:-numValEntries], trainData[-numValEntries:]
    # trainData = trainData[:-predictionWindowDiff]
    print("No. of rows in training set:", len(trainData))
    print("No. of rows in validation set:", len(valData))
    print("No. of rows in test set:", len(testData))
    return trainData, valData, testData, fullTrainData

def splitWeatherDataset(dataset, testDataSize, valDataSize, predictionWindowHours): # testDataSize, valDataSize are in days
    print("No. of rows in weather dataset:", len(dataset))
    valData = None
    numTestEntries = testDataSize * predictionWindowHours
    numValEntries = valDataSize * predictionWindowHours
    trainData, testData = dataset[:-numTestEntries], dataset[-numTestEntries:]
    fullTrainData = np.copy(trainData)
    trainData, valData = trainData[:-numValEntries], trainData[-numValEntries:]
    print("No. of rows in training set:", len(trainData))
    print("No. of rows in validation set:", len(valData))
    print("No. of rows in test set:", len(testData))
    return trainData, valData, testData, fullTrainData

def showModelSummary(history, model):
    print("Showing model summary...")
    model.summary()
    print("***** Model summary shown *****")
    # list all data in history
    print(history.history.keys()) # ['loss', 'mean_absolute_error', 'val_loss', 'val_mean_absolute_error']
    fig = plt.figure()
    subplt1 = fig.add_subplot(2, 1, 1)
    subplt1.plot(history.history['mean_absolute_error'])
    subplt1.plot(history.history['val_mean_absolute_error'])
    subplt1.legend(['train MAE', 'val_MAE'], loc="upper left")
    # summarize history for loss
    subplt2 = fig.add_subplot(2, 1, 2)
    subplt2.plot(history.history['loss'])
    subplt2.plot(history.history['val_loss'])
    subplt2.legend(['train RMSE', 'val RMSE'], loc="upper left")
    
    # plt.plot(history.history["loss"])
    # plt.xlabel('epoch')
    # plt.ylabel("RMSE")
    # plt.title('Training loss (RMSE)')
    return

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
    global MONTH_INTERVAL
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