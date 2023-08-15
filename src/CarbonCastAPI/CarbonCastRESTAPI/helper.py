import os

def get_latest_csv_file(region_code):
    os.chdir("../../")
    print("Current working directory: {0}".format(os.getcwd()))
    path = os.chdir(os.path.join('real_time',region_code))
    print("Current working directory: {0}".format(os.getcwd()))
    file_list1= [file for file in os.listdir() if file.endswith("_lifecycle_emissions.csv")]
    file_list2= [file for file in os.listdir() if file.endswith("_direct_emissions.csv")]
    # print(file_list)
    dates_list1 , dates_list2 = [] , []
    for filename in file_list1:
        d = filename.split('_')[1]
        dates_list1.append(d)
    # print(dates_list)
    for filename in file_list2:
        c = filename.split('_')[1]
        dates_list2.append(c)
    latest_date1, latest_date2 = max(dates_list1), max(dates_list2)
    # print(latest_date)
    csv_file1 = f'{region_code}_{latest_date1}_lifecycle_emissions.csv'
    csv_file2 = f'{region_code}_{latest_date2}_direct_emissions.csv'
    
    return csv_file1, csv_file2

def get_file_by_date(region_code, date):
    os.chdir("../../")
    path = os.chdir(os.path.join('real_time',region_code))
    for file in os.listdir():
        if file.endswith(f"_{date}_lifecycle_emissions.csv"):
            csv_file_a = file
        elif file.endswith(f"_{date}_direct_emissions.csv"):
            csv_file_b = file
    return csv_file_a, csv_file_b


