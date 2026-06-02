import numpy as np
import pandas as pd
import pytz as pytz
from scipy.fftpack import ss_diff
import tensorflow as tf
import matplotlib.pyplot as plt
import csv
import math
import seaborn as sns
from statsmodels.tsa.stattools import adfuller
import matplotlib.dates as mdates
import sys



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

def writeOutFile(outFileName, data, fuel):
    print("Writing to ", outFileName, "...")
    fields = ["datetime", fuel+"_actual", "avg_"+fuel+"_production_forecast"]
    
    # writing to csv file 
    with open(outFileName, 'w') as csvfile: 
        # creating a csv writer object 
        csvwriter = csv.writer(csvfile)   
        # writing the fields 
        csvwriter.writerow(fields) 
        # writing the data rows 
        csvwriter.writerows(data)

def showPlots():
    plt.show()

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
        # print(fmax, fmin)

    for i in range(col):
        if((ftMax[i] - ftMin[i]) == 0):
            continue
        trainData[:, i] = (trainData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])
        valData[:, i] = (valData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])
        testData[:, i] = (testData[:, i] - ftMin[i]) / (ftMax[i] - ftMin[i])

    return trainData, valData, testData, ftMin, ftMax

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

def plotFeatures(X, trainDates, features, localTimeZone, dayInterval = 1, selectedFeatures=False):
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
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=dayInterval, tz=localTimeZone))
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
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=dayInterval, tz=localTimeZone))
        plt.xlabel("Local time")
        plt.ylabel("Value")
        plt.title("Features")
        # plt.grid(axis="x")
        plt.xticks(rotation=30)
        plt.legend()

    plt.show()
    return

def plotPieChart(iso, data, features):
    print(features)
    fig = plt.figure()
    avgdata = np.mean(data, axis=0)
    sum = np.sum(avgdata)
    avgdata/=sum
    print(avgdata, np.sum(avgdata))
    plt.pie(avgdata, labels = features, autopct='%1.1f%%',)
    plt.title(iso+" - contribution by source")
    return

def plotGraphs(actualVal, predictedVal, testDates, plotTitle, localTimeZone, dayInterval=1,
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
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=dayInterval, tz=localTimeZone))
    
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

def writeDailyMapeToFile(iteration, data, fileName):
    with open(fileName, "w") as f:
        writer = csv.writer(f)
        writer.writerows(data)
    return

def plotDailyMapeCDF(data1, data2, title): # data1: DACF, data2: CarbonCast
    # No of Data points
    N = len(data1)
    

    bins1 = int(np.amax(data1) + 1)
    bins2 = int(np.amax(data2) + 1)
    # print(data, bins)
    
    # getting data of the histogram
    count1, bins_count1 = np.histogram(data1, bins=bins1)
    count2, bins_count2 = np.histogram(data2, bins=bins2)
    
    # finding the PDF of the histogram using count values
    pdf1 = count1 / sum(count1)
    pdf2 = count2 / sum(count2)
    
    # using numpy np.cumsum to calculate the CDF
    # We can also find using the PDF values by looping and adding
    cdf1 = np.cumsum(pdf1)
    cdf2 = np.cumsum(pdf2)


    # plotting PDF and CDF
    # plt.plot(bins_count[1:], pdf, color="red", label="PDF")
    plt.plot(bins_count1[1:], cdf1, label="Non-hierarchical", linestyle = "dashed", linewidth = 6)
    plt.plot(bins_count2[1:], cdf2, label="CarbonCast", linewidth = 6)
    plt.grid(axis="both")
    # plt.title(title)
    plt.xlabel("MAPE (%)", fontsize=21)
    plt.ylabel("CDF", fontsize=21)
    plt.yticks(np.arange(0.0, 1.1, 0.1), fontsize=19)
    plt.xticks(fontsize=19)
    plt.legend(fontsize=19)
    plt.show()
    return

def plotCDF(iso, directory):
    carbonCastFile1 = "../extn/"+iso+"/buildsys/lifecycle_final/file5.csv"
    carbonCastFile2 = "../extn/"+iso+"/buildsys/lifecycle_final/file7.csv"
    carbonCastFile3 = "../extn/"+iso+"/buildsys/lifecycle_final/file9.csv"

    cdata1 = pd.read_csv(carbonCastFile1, header=None)
    # print(cdata1.head())
    cdata2 = pd.read_csv(carbonCastFile2, header=None)
    # print(cdata2.head())
    cdata3 = pd.read_csv(carbonCastFile3, header=None)
    # print(cdata3.head())
    # print(cdata1.shape, cdata2.shape)
    cdata = pd.DataFrame(index=range(cdata1.shape[0]),columns=range(cdata1.shape[1]))
    for i in range(cdata1.shape[0]):
        for j in range(cdata1.shape[1]):
            cdata.iloc[i, j] = cdata1.iloc[i, j] + cdata2.iloc[i, j] + cdata3.iloc[i, j] 
    cdata = cdata.to_numpy()
    cdata = cdata/3
    print(cdata.shape)
    print("Daywise statistics...")
    for i in range(0, 4):
        print("Prediction day ", i+1, "(", (i*24), " - ", (i+1)*24, " hrs)")
        print("Mean MAPE: ", round(np.mean(cdata[:, i]), 2))
        print("Median MAPE: ", round(np.percentile(cdata[:, i], 50), 2))
        print("90th percentile MAPE: ", round(np.percentile(cdata[:, i], 90), 2))
        print("95th percentile MAPE: ", round(np.percentile(cdata[:, i], 95), 2))
        print("99th percentile MAPE: ", round(np.percentile(cdata[:, i], 99), 2))
    # print(cdata)

    print("Mean : ", round(np.mean(cdata), 2))
    print("Median : ", round(np.percentile(cdata, 50), 2))
    print("90th : ", round(np.percentile(cdata, 90), 2))
    print("95th : ", round(np.percentile(cdata, 95), 2))

    dacfFile = "../extn/"+iso+"/buildsys/lifecycle_final/dacf.csv"
    ddata = pd.read_csv(dacfFile)

    for i in range(4):
        plotDailyMapeCDF(ddata.iloc[:, i], cdata[:, i], "Day "+str(i+1))
    
    return

# Add Gaussian noise to forecast features
def addNoiseToForecast(iso, source, dev=0.05):
    percentNoise = dev*100
    inFile = "../extn/"+iso+"/noise/"+iso+"_direct_emissions.csv"
    # outFile = "../extn/"+iso+"/noise/"+source+"_"+str(int(percentNoise))+"_percent.csv"
    outFile = "../extn/"+iso+"/noise/"+source+"_50.csv"
    dataset = pd.read_csv(inFile)
    modifiedDataset = pd.DataFrame()
    # energySources = ["forecast_coal", "forecast_nat_gas", "forecast_nuclear", 
    #                 "forecast_oil", "forecast_hydro", "forecast_solar", "forecast_wind"]
    sourceFcst = "avg_"+source+"_production_forecast"
    for col in dataset.columns:
        noisyForecast = []
        if col == source:
            val = dataset[col].values
            print(val)
            for j in range(0, len(val), 24):
                tmpVal = val[j:j+24]
                sourceMean = np.mean(tmpVal)
                stdDev = dev * sourceMean
                noise = np.random.normal(loc=0, scale=stdDev, size=len(tmpVal))
                noisyForecast.extend(noise)
                # print(len(noisyForecast))
            # sourceMean = np.mean(val)
            # stdDev = dev * sourceMean
            # noise = np.random.normal(loc=0, scale=stdDev, size=len(val))
            # noisyForecast = np.add(dataset[col], noise)
            noisyForecast = np.add(dataset[col], noisyForecast)
            noisyForecast = np.maximum(0, noisyForecast)

            # rng = np.random.default_rng(12345)
            # noisyForecast = rng.integers(low=0, high=np.amax(val), size=len(val))
            
            # modifiedDataset[col] = dataset[col]
            # modifiedDataset[sourceFcst] = noisyForecast
            modifiedDataset[col] = noisyForecast
        else:
            modifiedDataset[col] = dataset[col]
    modifiedDataset.to_csv(outFile)
    return modifiedDataset

def manipulateNoisyForecasts(iso):
    inFile = "../extn/"+iso+"/noise/nat_gas_50.csv"
    outFile = "../extn/"+iso+"/noise/nat_gas_50_96hr.csv"
    dataset = pd.read_csv(inFile)
    modifiedDataset = pd.DataFrame()
    for col in dataset.columns:
        if (col == "UTC time"):
            data = manipulateTestDataShape(dataset[col], 24, 96, True)
            data = np.reshape(data, data.shape[0]*data.shape[1])
            modifiedDataset[col] = data
        elif (col == "carbon_intensity"):
            continue
        else:
            sourceFcst = "avg_"+col+"_production_forecast"
            data = manipulateTestDataShape(dataset[col], 24, 96, False)
            data = np.reshape(data, data.shape[0]*data.shape[1])
            modifiedDataset[sourceFcst] = data
    modifiedDataset.to_csv(outFile)
    return

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

if __name__ == "__main__":
    if (sys.argv[2] == "l"):
        plotCDF(sys.argv[1], "lifecycle")
    else:
        plotCDF(sys.argv[1], "direct")
    # addNoiseToForecast("CISO", "nat_gas", dev=0.5)

    # manipulateNoisyForecasts("CISO")

