from statistics import mode
import pandas as pd
from matplotlib import pyplot as plt
from statsmodels.tsa.arima.model import ARIMA
import statsmodels.api as sm
from sklearn.metrics import mean_squared_error
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.linear_model import LinearRegression
from math import sqrt
import pmdarima as pm
import numpy as np

STEP_SIZE = 24
START_COL = 2

# Date time feature engineering
def addDateTimeFeatures(dataset, dateTime):
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

def scaleDataset(trainData, valData, testData):
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
    for i in range(len(data)):
        unscaledData[i] = data[i]*cdiff + cmin
    return unscaledData


# exit(0)
# walk-forward validation

def sarimaResidualCorrection(series, train, test):
    day = 1
    exogenousInput = train[-STEP_SIZE:, 1:]
    dailyMape = []
    model = sm.tsa.statespace.SARIMAX(endog=train[STEP_SIZE:, 0], order=(5, 1, 0), seasonal_order=(2, 0, 0, 24))
    model_fit = model.fit()
    for t in range(0, len(test), STEP_SIZE):
        output = model_fit.forecast(steps=STEP_SIZE)
        for yhat in output:
            # print('Hour %d: %f' % (day, yhat))
            # history.append(inverted)
            predictions.append(yhat)
            day += 1
        # yhat = output[0]
        
        obs = test[t:t+STEP_SIZE]
        history.extend(obs)
        for i in range(len(obs)):
            print('predicted=%f, expected=%f' % (output[i], obs[i, 0]))
        rmse = sqrt(mean_squared_error(test[t:t+STEP_SIZE, 0], predictions[t:t+STEP_SIZE]))
        mape = mean_absolute_percentage_error(test[t:t+STEP_SIZE, 0], predictions[t:t+STEP_SIZE])
        dailyMape.append(mape)
        print('Test daily RMSE: %.3f' % rmse)
        print('Test daily MAPE: %.3f' % (mape*100))
        print("Updating model each day via extend()")
        model_fit = model_fit.extend(obs[:, 0])
    # evaluate forecasts
    rmse = sqrt(mean_squared_error(test[:,0], predictions))
    mape = mean_absolute_percentage_error(test[:,0], predictions)
    print('Test RMSE: %.3f' % rmse)
    print('Test MAPE: %.3f' % (mape*100))
    for item in dailyMape:
        print((item*100))
    print("Mean MAPE: ", np.mean(dailyMape))
    print("Median MAPE: ", np.percentile(dailyMape, 50))
    print("90th percentile MAPE: ", np.percentile(dailyMape, 90))
    print("95th percentile MAPE: ", np.percentile(dailyMape, 95))
    print("99th percentile MAPE: ", np.percentile(dailyMape, 99))
    # plot forecasts against actual outcomes
    # plt.plot(test[:, 0])
    # plt.plot(predictions, color='red')
    # plt.show()
    return

def simpleLinearReg(series, train, val, test, ftMin, ftMax, history):
    day = 1
    exogenousInput = val[-STEP_SIZE:, :]
    dailyMape = []
    residual = []
    model = LinearRegression()
    model_fit = model.fit(train[:-STEP_SIZE, :], train[STEP_SIZE:, 0])  
    for t in range(0, len(test), STEP_SIZE):
        output = model_fit.predict(exogenousInput)
        for yhat in output:
            predictions.append(yhat)
        
        obs = test[t:t+STEP_SIZE]
        exogenousInput = obs[:, :]
        # unScaledTest = test[t:t+STEP_SIZE, 0]
        # unScaledPred = predictions[t:t+STEP_SIZE]
        unScaledTest = inverseDataScaling(test[t:t+STEP_SIZE, 0], ftMax, ftMin)
        unScaledPred = inverseDataScaling(predictions[t:t+STEP_SIZE], ftMax, ftMin)
        # for i in range(STEP_SIZE):
        #     print('predicted=%f, expected=%f' % (unScaledTest[i], unScaledPred[i]))
        rmse = sqrt(mean_squared_error(unScaledTest, unScaledPred))
        mape = mean_absolute_percentage_error(unScaledTest, unScaledPred)
        dailyMape.append((mape*100))
        # print('Test daily RMSE: %.3f' % rmse)
        # print('Test daily MAPE: %.3f' % (mape*100))
        # print("Updating model each day via extend()")
        # model_fit = model_fit.extend(obs[:, 0], exogenousInput)
        # model_fit = model.fit(newX, newY)
    # evaluate forecasts
    unScaledTest = inverseDataScaling(test[:, 0], ftMax, ftMin)
    unScaledPred = inverseDataScaling(predictions, ftMax, ftMin)
    rmse = sqrt(mean_squared_error(unScaledTest, unScaledPred))
    mape = mean_absolute_percentage_error(unScaledTest, unScaledPred)
    # print('Test RMSE: %.3f' % rmse)
    # print('Test MAPE: %.3f' % (mape*100))
    for item in dailyMape:
        print(item)
    # for i in range(24*7-1, -1, -1):
    #     print(unScaledPred[-i])
    print("Mean MAPE: ", np.mean(dailyMape))
    print("Median MAPE: ", np.percentile(dailyMape, 50))
    print("90th percentile MAPE: ", np.percentile(dailyMape, 90))
    print("95th percentile MAPE: ", np.percentile(dailyMape, 95))
    print("99th percentile MAPE: ", np.percentile(dailyMape, 99))
    # plot forecasts against actual outcomes
    # plt.plot(unScaledTest[-24*7:])
    # plt.plot(unScaledPred[-24*7:], color='red')
    # plt.show()
    return model_fit.coef_


def linearReg(series, train, test, ftMin, ftMax, history):
    day = 1
    exogenousInput = train[-STEP_SIZE:, 1:]
    dailyMape = []
    residual = []
    model = LinearRegression()

    for i in range(STEP_SIZE, len(train)-STEP_SIZE, STEP_SIZE):
        exogenousInput = train[-STEP_SIZE:, 1:]
        model_fit = model.fit(train[0:i, 1:], train[STEP_SIZE:i+STEP_SIZE:, 0])
        output = model_fit.predict(exogenousInput)
        for yhat in output:
            residual.append(yhat)

    residual = np.array(residual)
    print("Residual shape: ", residual.shape)
    print("train shape: ", train.shape)
    exit(0)
    
    exogenousInput = train[-STEP_SIZE:, 1:]
    for t in range(0, len(test), STEP_SIZE):
        output = model_fit.predict(exogenousInput)
        for yhat in output:
            predictions.append(yhat)
            day += 1
        
        obs = test[t:t+STEP_SIZE]
        # unScaledTest = test[t:t+STEP_SIZE, 0]
        # unScaledPred = predictions[t:t+STEP_SIZE]
        unScaledTest = inverseDataScaling(test[t:t+STEP_SIZE, 0], ftMax, ftMin)
        unScaledPred = inverseDataScaling(predictions[t:t+STEP_SIZE], ftMax, ftMin)
        for i in range(STEP_SIZE):
            print('predicted=%f, expected=%f' % (unScaledTest[i], unScaledPred[i]))
        rmse = sqrt(mean_squared_error(unScaledTest, unScaledPred))
        mape = mean_absolute_percentage_error(unScaledTest, unScaledPred)
        dailyMape.append((mape*100))
        print('Test daily RMSE: %.3f' % rmse)
        print('Test daily MAPE: %.3f' % (mape*100))
        # print("Updating model each day via extend()")
        # model_fit = model_fit.extend(obs[:, 0], exogenousInput)
        # model_fit = model.fit(newX, newY)
    # evaluate forecasts
    unScaledTest = test[t:t+STEP_SIZE, 0]#inverseDataScaling(test[t:t+STEP_SIZE, 0], ftMax, ftMin)
    unScaledPred = predictions[t:t+STEP_SIZE]#inverseDataScaling(predictions[t:t+STEP_SIZE], ftMax, ftMin)
    rmse = sqrt(mean_squared_error(unScaledTest, unScaledPred))
    mape = mean_absolute_percentage_error(unScaledTest, unScaledPred)
    print('Test RMSE: %.3f' % rmse)
    print('Test MAPE: %.3f' % (mape*100))
    for item in dailyMape:
        print(item)
    print("Mean MAPE: ", np.mean(dailyMape))
    print("Median MAPE: ", np.percentile(dailyMape, 50))
    print("90th percentile MAPE: ", np.percentile(dailyMape, 90))
    print("95th percentile MAPE: ", np.percentile(dailyMape, 95))
    print("99th percentile MAPE: ", np.percentile(dailyMape, 99))
    # plot forecasts against actual outcomes
    # plt.plot(test[:, 0])
    # plt.plot(predictions, color='red')
    # plt.show()
    return


ISO_LIST = ["CISO"]
# ISO_LIST = ["CISO", "PJM", "ERCO", "ISNE", "SE", "DE"]
for iso in ISO_LIST:
    print("************* ISO: ", iso, "*************")
    START_COL = 3
    if iso == "SE":
        START_COL = 2
    if iso == "DE" or iso == "PL":
        START_COL = 1
    IN_FILE_NAME = "../final_weather_data/"+iso+"/"+iso+"_forecast_carbon.csv"
    # IN_FILE_NAME = "../final_weather_data/"+iso+"/"+iso+"_hierarchical.csv"
    series = pd.read_csv(IN_FILE_NAME, header=0, infer_datetime_format=True, 
                            parse_dates=['UTC time'], index_col=['UTC time'])
    # series = series[:8784]

    print("\nAdding features related to date & time...")
    series = addDateTimeFeatures(series, series.index.values)
    print("Features related to date & time added")

    print(series)
    for i in range(START_COL, len(series.columns.values)):
            col = series.columns.values[i]
            series[col] = series[col].astype(np.float64)
            print(col, series[col].dtype)
    # split into train and test sets
    X = series.values
    # X = X[:8784]
    NUM_TEST_DAYS = 184
    NUM_VAL_DAYS = 181
    train, test = X[0:-NUM_TEST_DAYS*24, START_COL:], X[-NUM_TEST_DAYS*24:, START_COL:]
    # train, test = X[0:-NUM_TEST_DAYS*24, START_COL:START_COL+14], X[-NUM_TEST_DAYS*24:, START_COL:START_COL+14]
    train, val = train[0:-NUM_VAL_DAYS*24, :], train[-NUM_VAL_DAYS*24:, :]
    train = np.array(train, dtype=float)
    val = np.array(val, dtype=float)
    test = np.array(test, dtype=float)

    for i in range(train.shape[0]):
        for j in range(train.shape[1]):
            if(np.isnan(train[i, j])):
                train[i, j] = train[i-1, j]

    for i in range(val.shape[0]):
        for j in range(val.shape[1]):
            if(np.isnan(val[i, j])):
                val[i, j] = val[i-1, j]

    for i in range(test.shape[0]):
        for j in range(test.shape[1]):
            if(np.isnan(test[i, j])):
                test[i, j] = test[i-1, j]

    print(train.shape, val.shape, test.shape)

    ftMin = [None]*train.shape[1]
    ftMax = [None]*train.shape[1]

    print("Scaling dataset to [0,1]")
    train, val, test, ftMin, ftMax = scaleDataset(train, val, test)
    print("Dataset scaled")

    history = [x for x in train]
    predictions = list()
    
    coeff = simpleLinearReg(series, train, val, test, ftMin[0], ftMax[0], history)
    print(coeff, len(coeff))
    ftImpMap = {}
    col = series.columns.values
    for i in range(len(coeff)):
        ftImpMap[col[i+START_COL]] = coeff[i]
    ftImpMap = dict(sorted(ftImpMap.items(), key=lambda item: item[1]))
    tmp=[]
    for ft, grad in ftImpMap.items():
        tmp.append([ft, grad])
    left = 0
    right = len(tmp)-1
    idx = 0
    for i in range(len(tmp)):
        if (abs(tmp[left][1]) > abs(tmp[right][1])):
            print(tmp[left][0], tmp[left][1])
            left +=1
        else:
            print(tmp[right][0], tmp[right][1])
            right -=1
        idx +=1

    print("************* ISO: ", iso, " done *************")



