import os


def get_latest_csv_file(region_code):
    os.chdir("../../")
    path = os.chdir(os.path.join('real_time',region_code))
    file_list1= [file for file in os.listdir() if file.endswith("_lifecycle_emissions.csv")]
    file_list2= [file for file in os.listdir() if file.endswith("_direct_emissions.csv")]
    dates_list1 , dates_list2 = [] , []
    for filename in file_list1:
        d = filename.split('_')[1]
        dates_list1.append(d)
    for filename in file_list2:
        c = filename.split('_')[1]
        dates_list2.append(c)
    latest_date1, latest_date2 = max(dates_list1), max(dates_list2)
    csv_file1 = f'{region_code}_{latest_date1}_lifecycle_emissions.csv'
    csv_file2 = f'{region_code}_{latest_date2}_direct_emissions.csv'
    
    return csv_file1, csv_file2


def get_CI_forecasts_csv_file(region_code, date):
    os.chdir("../../")
    path = os.chdir(os.path.join('real_time',region_code))
    for file in os.listdir():
        print(file)
        if file.endswith(f"lifecycle_CI_forecasts_{date}.csv"):
            csv_file_l = file
        elif file.endswith(f"direct_CI_forecasts_{date}.csv"):
            csv_file_d = file
    return csv_file_l, csv_file_d


def get_actual_value_file_by_date(region_code, date):
    os.chdir("../../")
    path = os.chdir(os.path.join('real_time',region_code))
    i = 0
    for file in os.listdir():
        print(i, file, date)
        i += 1
        if file.endswith(f"_{date}_lifecycle_emissions.csv"):
            csv_file_a = file
            print(csv_file_a)
        elif file.endswith(f"_{date}_direct_emissions.csv"):
            csv_file_b = file
            print(csv_file_b)
    print(csv_file_a, csv_file_b)
    return csv_file_a, csv_file_b

def get_energy_forecasts_csv_file(region_code, date):
    os.chdir("../../")
    path = os.chdir(os.path.join('real_time',region_code))
    for file in os.listdir():
        if file.endswith(f"_96hr_forecasts_{date}.csv"):
            e_forecast_csv_file = file
    return e_forecast_csv_file