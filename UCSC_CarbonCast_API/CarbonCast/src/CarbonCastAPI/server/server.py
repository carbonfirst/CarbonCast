import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import http.client
import urllib.parse
import os

server_host = 'localhost'

def get_latest_csv_file(region_code):
    os.chdir("../../../")
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

def get_forecasts_csv_file(region_code, date):
    os.chdir("../../../")
    path = os.chdir(os.path.join('real_time',region_code))
    for file in os.listdir():
        if file.endswith(f"lifecycle_CI_forecasts_{date}.csv"):
            csv_file_l = file
        elif file.endswith(f"direct_CI_forecasts_{date}.csv"):
            csv_file_d = file
    return csv_file_l, csv_file_d

def get_actual_value_file_by_date(region_code, date):
    os.chdir("../../../")
    path = os.chdir(os.path.join('real_time',region_code))
    for file in os.listdir():
        if file.endswith(f"_{date}_lifecycle_emissions.csv"):
            csv_file_a = file
        elif file.endswith(f"_{date}_direct_emissions.csv"):
            csv_file_b = file
    return csv_file_a, csv_file_b


class RequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        #1
        if parsed_path.path == '/CarbonIntensity':
            region_code = query_params.get('regionCode', [''])[0]   

            csv_file1, csv_file2 = get_latest_csv_file(region_code)
            with open(csv_file1) as file:
                for line in file:
                    pass
            values_csv1 = line.split(',')
            with open(csv_file2) as file:
                for line in file:
                    pass
            values_csv2 = line.split(',')
            os.chdir("../../")
            os.chdir(os.path.join('src', 'API', 'server'))
            response_data= {
                "UTC time" : values_csv1[1],
                "creation_time (UTC)": values_csv1[2],
                "version": values_csv1[3],
                "region_code": region_code,
                "carbon_intensity_avg_lifecycle": float(values_csv1[4]),
                "carbon_intensity_avg_direct": float(values_csv2[4]),
                "carbon_intensity_unit": "gCO2eg/kWh"                
              }
            response = {
                "data": response_data
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()                                
            self.wfile.write(json.dumps(response).encode())


        #2
        if parsed_path.path == '/EnergySources':
            region_code = query_params.get('regionCode', [''])[0]   

            csv_file1, csv_fil2 = get_latest_csv_file(region_code)
            with open(csv_file1) as file:
                header = file.readline().strip()
                columns = header.split(',')

                for row in file:
                    line = row.strip().split(',')
            os.chdir("../../")
            os.chdir(os.path.join('src', 'API', 'server'))
            fields = [
                 "UTC time", "creation_time (UTC)", "version", "region_code", "coal", "nat_gas", "nuclear",
                 "oil", "hydro", "solar", "wind", "other"
                 ]
            response_data = {}

            for field in fields:
                if field in columns:
                    index = columns.index(field)
                    value = line[index].strip() if index < len(line) else "0"
                    response_data[field] = value
                elif field == "region_code":
                    response_data[field] = region_code
                else:
                    response_data[field] = "0"
                    
            response = {
                "data": response_data
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()                                
            self.wfile.write(json.dumps(response).encode())

        #3
        if parsed_path.path == '/CarbonIntensityHistory':
            region_code = query_params.get('regionCode', [''])[0]   
            date = query_params.get('date', [''])[0]

            csv_file_a, csv_file_b = get_actual_value_file_by_date(region_code, date)
            with open(csv_file_a) as file:
                lines_csv1 = file.readlines()

            with open(csv_file_b) as file:
                lines_csv2 = file.readlines()            

            values_csv1 = [line.strip().split(',') for line in lines_csv1]
            values_csv2 = [line.strip().split(',') for line in lines_csv2]

            final_list =[]
            for i in range(1,len(values_csv1)):
                temp_list= []
                temp_list.append(values_csv1[i][1])
                temp_list.append(values_csv1[i][2])
                temp_list.append(values_csv1[i][3])
                temp_list.append(region_code)
                temp_list.append(float(values_csv1[i][4]))
                temp_list.append(float(values_csv2[i][4]))
                temp_list.append("gCO2eg/kWh")
                final_list.append(temp_list)
            os.chdir("../../")
            os.chdir(os.path.join('src', 'API', 'server'))
            response_data = {
                "data": final_list
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()                                
            self.wfile.write(json.dumps(response_data).encode())

        #4
        if parsed_path.path == '/EnergySourcesHistory':
            region_code = query_params.get('regionCode', [''])[0]   
            date = query_params.get('date', [''])[0]

            csv_file_a, csv_file_b = get_actual_value_file_by_date(region_code, date)
            with open(csv_file_a) as file:
                lines_csv1 = file.readlines()

            with open(csv_file_b) as file:
                lines_csv2 = file.readlines()

            values_csv1 = [line.strip().split(',') for line in lines_csv1]
            values_csv2 = [line.strip().split(',') for line in lines_csv2]

            fields = [
                "UTC time", "creation_time (UTC)", "version","region_code", "coal", "nat_gas", "nuclear",
                "oil", "hydro", "solar", "wind", "other"
            ]
            final_list = []

            for i in range(1, len(values_csv1)):
                temp_dict = {field: "0" for field in fields}
                temp_dict["UTC time"] = values_csv1[i][1]
                temp_dict["creation_time (UTC)"] = values_csv1[i][2]
                temp_dict["version"] = values_csv1[i][3]
                temp_dict["region_code"] = region_code

                for field in fields[2:]:  
                    if field in values_csv1[0]:
                        index = values_csv1[0].index(field)
                        temp_dict[field] = values_csv1[i][index]

                final_list.append(temp_dict)

            os.chdir("../../")
            os.chdir(os.path.join('src', 'API', 'server'))
            response_data = {
                "data": final_list
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()                                
            self.wfile.write(json.dumps(response_data).encode())

        #6
        if parsed_path.path == '/CarbonIntensityForecastsHistory':
            region_code = query_params.get('regionCode', [''])[0]   
            date = query_params.get('date', [''])[0]

            csv_file_l, csv_file_d = get_forecasts_csv_file(region_code, date)
            with open(csv_file_l) as file:
                lines_csv1 = file.readlines()

            with open(csv_file_d) as file:
                lines_csv2 = file.readlines()

            filtered_data_by_date_csv1 = [line.split(',') for line in lines_csv1 if line.startswith(date)]
            filtered_data_by_date_csv2 = [line.split(',') for line in lines_csv2 if line.startswith(date)]

            os.chdir("../../")
            os.chdir(os.path.join('src', 'API', 'server'))

            final_list =[]
            for i in range(1,len(filtered_data_by_date_csv1)):
                temp_list= []
                temp_list.append(filtered_data_by_date_csv1[i][0])
                temp_list.append(filtered_data_by_date_csv1[i][1])
                temp_list.append(filtered_data_by_date_csv1[i][2])
                temp_list.append(region_code)
                temp_list.append(float(filtered_data_by_date_csv1[i][3]))
                temp_list.append(float(filtered_data_by_date_csv2[i][3]))
                temp_list.append("gCO2eg/kWh")
                final_list.append(temp_list)            

            response_data = {
                "data": final_list
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()                                
            self.wfile.write(json.dumps(response_data).encode())

        #7
        if parsed_path.path == '/EnergySourcesForecastsHistory':
            region_code = query_params.get('regionCode', [''])[0]   
            date = query_params.get('date', [''])[0]

            os.chdir("../../../")
            os.chdir(os.path.join('real_time',region_code))

            energy_forecast_csv_file = f"{region_code}_{date}.csv"
            with open(energy_forecast_csv_file) as file:
                lines_csv = file.readlines()

            filtered_energy_data_by_date_csv = [line.split(',') for line in lines_csv if line.startswith(date)]

            os.chdir("../../")
            os.chdir(os.path.join('src', 'API', 'server'))

            fields = [
                "UTC time", "creation_time (UTC)", "version","region_code", "coal", "nat_gas", "nuclear",
                "oil", "hydro", "solar", "wind", "other"
            ]
            final_list = []

            for i in range(1, len(filtered_energy_data_by_date_csv)):
                temp_dict = {field: "0" for field in fields}
                temp_dict["UTC time"] = filtered_energy_data_by_date_csv[i][1]
                temp_dict["creation_time (UTC)"] = filtered_energy_data_by_date_csv[i][2]
                temp_dict["version"] = filtered_energy_data_by_date_csv[i][3]
                temp_dict["region_code"] = region_code

                for field in fields[2:]:  
                    if field in filtered_energy_data_by_date_csv[0]:
                        index = filtered_energy_data_by_date_csv[0].index(field)
                        temp_dict[field] = filtered_energy_data_by_date_csv[i][index]

                final_list.append(temp_dict)
            response_data = {
                "data": final_list
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()                                
            self.wfile.write(json.dumps(response_data).encode())

        #8
        if parsed_path.path == '/SupportedRegions':
            os.chdir("../../../")
            items = os.listdir("real_time")
            supported_regions = [item for item in items if os.path.isdir(os.path.join("real_time", item)) and item != 'weather_data']
            response_data = {
                "data": supported_regions
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()                                
            self.wfile.write(json.dumps(response_data).encode())


def run():
    server_address = ('', 13000)

    httpd = HTTPServer(server_address, RequestHandler)
    print('Starting server...')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Server stopped")                              


if __name__ == '__main__':
    run()