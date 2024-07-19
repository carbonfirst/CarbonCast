import os


def get_latest_csv_file(region_code):
    path = os.path.abspath(os.path.join(os.getcwd(),'real_time',region_code))
    file_list1= [file for file in os.listdir(path) if file.endswith("_lifecycle_emissions.csv")]
    file_list2= [file for file in os.listdir(path) if file.endswith("_direct_emissions.csv")]
    dates_list1 , dates_list2 = [] , []
    for filename in file_list1:
        d = filename.split('_')[1]
        dates_list1.append(d)
    for filename in file_list2:
        c = filename.split('_')[1]
        dates_list2.append(c)
    latest_date1, latest_date2 = max(dates_list1), max(dates_list2)
    csv_file1 = os.path.join(path, f'{region_code}_{latest_date1}_lifecycle_emissions.csv')
    csv_file2 = os.path.join(path, f'{region_code}_{latest_date2}_direct_emissions.csv')
    
    return csv_file1, csv_file2


def get_CI_forecasts_csv_file(region_code, date):
    path = os.path.abspath(os.path.join(os.getcwd(),'real_time',region_code))
    i = 0 
    numFiles = len(os.listdir(path))
    csv_file_l= None
    csv_file_d = None
    for file in os.listdir(path):
        print("this is printing file:",file)
        if(i ==numFiles-1):
            print(i, file, date)
        i+=1 
        if file.endswith(f"lifecycle_CI_forecasts_{date}.csv"):
            csv_file_l = os.path.join(path, file)
        elif file.endswith(f"direct_CI_forecasts_{date}.csv"):
            csv_file_d = os.path.join(path, file)
    if (csv_file_l is None): # file not found
        #csv_file_l = os.path.join(path, f"{region_code}_lifecycle_CI_forecasts_2023-08-07.csv")
        latestdate = list()
        for filename in os.listdir(path):
            if "lifecycle_CI_forecast" in filename:
                latestdate.append(filename)
                print("this is the latestdate1:", latestdate[-1])

        csv_file_l = os.path.join(path,latestdate[-1])
    if (csv_file_d is None): # file not found
       #csv_file_d = os.path.join(path, f"{region_code}_direct_CI_forecasts_2023-08-07.csv")
       latestdate2 = list()
       for filename in os.listdir(path):
            if "direct_CI_forecasts" in filename:
                latestdate2.append(filename)
                print("this is the latestdate2:", latestdate2[-1])
                csv_file_d = os.path.join(path, latestdate2[-1])
    
    return csv_file_l, csv_file_d



def get_actual_value_file_by_date(region_code, date):
    path = os.path.abspath(os.path.join(os.getcwd(),'real_time',region_code))
    i = 0
    numFiles = len(os.listdir(path))
    csv_file_a = None
    csv_file_b = None
    for file in os.listdir(path):
        if(i, file, date):
            print(i, file, date)
        i += 1
        if file.endswith(f"_{date}_lifecycle_emissions.csv"):
            csv_file_a = os.path.join(path, file)
            print(csv_file_a)
        elif file.endswith(f"_{date}_direct_emissions.csv"):
            csv_file_b = os.path.join(path, file)
            print(csv_file_b)
    if (csv_file_a is None): # file not found
        latestdate3 = list()
        for filename in os.listdir(path):
            if "lifecycle_emissions" in filename:
                latestdate3.append(filename)
                print("this is the latestdate3:", latestdate3[-1])
        csv_file_a = os.path.join(path,latestdate3[-1] )

    if (csv_file_b is None): # file not found
        latestdate4 = list()
        for filename in os.listdir(path):
            if "direct_emissions" in filename:
                latestdate4.append(filename)
                print("this is the latestdate4:", latestdate4[-1])
        csv_file_b = os.path.join(path,latestdate4[-1])

    print(csv_file_a, csv_file_b)
    return csv_file_a, csv_file_b

def get_energy_forecasts_csv_file(region_code, date):
    path = os.path.abspath(os.path.join(os.getcwd(),'real_time',region_code))
    for file in os.listdir(path):
        if file.endswith(f"_96hr_forecasts_{date}.csv"):
            e_forecast_csv_file = os.path.join(path, file)
    return e_forecast_csv_file


