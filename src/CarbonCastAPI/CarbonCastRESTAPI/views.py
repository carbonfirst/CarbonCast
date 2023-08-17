from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
# from .models import CarbonCast
# from .serializers import CarbonCastSerializer
from .helper import get_latest_csv_file, get_actual_value_file_by_date, get_forecasts_csv_file
import os
# import json

#Defining a list of US region codes
US_region_codes = ['AECI','AZPS', 'BPAT','CISO', 'DUK', 'EPE', 'ERCO', 'FPL', 
                'ISNE', 'LDWP', 'MISO', 'NEVP', 'NWMT', 'NYIS', 'PACE', 'PJM', 
                'SC', 'SCEG', 'SOCO', 'TIDC', 'TVA']

# 1: 
class CarbonIntensityApiView(APIView):
    # add permission to check if user is authenticated: permissions.IsAuthenticated
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        
        region_code = request.query_params.get('regionCode', '')

        csv_file1, csv_file2 = get_latest_csv_file(region_code)
        with open(csv_file1) as file:
            for line in file:
                pass
        values_csv1 = line.split(',')
        with open(csv_file2) as file:
            for line in file:
                pass
        values_csv2 = line.split(',')

        response_data= {
            "UTC time" : values_csv1[1],
            "region_code": region_code,
            "carbon_intensity_avg_lifecycle": float(values_csv1[2]),
            "carbon_intensity_avg_direct": float(values_csv2[2]),
            "carbon_intensity_unit": "gCO2eg/kWh"                
          }
        response = {
            "data": response_data
        }
        return Response(response, status=status.HTTP_200_OK)
        
#2    
class EnergySourcesApiView(APIView):
    # add permission to check if user is authenticated: permissions.IsAuthenticated
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        
        region_code = request.query_params.get('regionCode', '')

        csv_file1, csv_fil2 = get_latest_csv_file(region_code)
        with open(csv_file1) as file:
            header = file.readline().strip()
            columns = header.split(',')
            for row in file:
                line = row.strip().split(',')

        fields = [
                "UTC time", "region_code", "coal", "nat_gas", "nuclear",
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
        return Response(response, status=status.HTTP_200_OK)
        
#3    
class CarbonIntensityHistoryApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        
        region_code = request.query_params.get('regionCode', '')
        date = request.query_params.get('date', '')
        
        csv_file_a, csv_file_b = get_actual_value_file_by_date(region_code, date)
        print("In view: ", csv_file_a, csv_file_b)
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
        response = {
            "data": final_list
        }
        return Response(response, status=status.HTTP_200_OK)
        
#4    
class EnergySourcesHistoryApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        
        region_code = request.query_params.get('regionCode', '')
        date = request.query_params.get('date', '')
        
        csv_file_a, csv_file_b = get_actual_value_file_by_date(region_code, date)
        with open(csv_file_a) as file:
            lines_csv1 = file.readlines()

        with open(csv_file_b) as file:
            lines_csv2 = file.readlines()

        values_csv1 = [line.strip().split(',') for line in lines_csv1]
        values_csv2 = [line.strip().split(',') for line in lines_csv2]

        fields = [
            "UTC time", "region_code", "coal", "nat_gas", "nuclear",
            "oil", "hydro", "solar", "wind", "other"
        ]
        final_list = []

        for i in range(1, len(values_csv1)):
            temp_dict = {field: "0" for field in fields}
            temp_dict["UTC time"] = values_csv1[i][1]
            temp_dict["region_code"] = region_code

            for field in fields[2:]:  # Skip UTC time and region_code
                if field in values_csv1[0]:
                    index = values_csv1[0].index(field)
                    temp_dict[field] = values_csv1[i][index]

            final_list.append(temp_dict)

        response = {
            "data": final_list
        }
        return Response(response, status=status.HTTP_200_OK)

#6    
class CarbonIntensityForecastsHistoryApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        
        region_code = request.query_params.get('regionCode', '')
        date = request.query_params.get('date', '')
        csv_file_l, csv_file_d = get_forecasts_csv_file(region_code, date)
        with open(csv_file_l) as file:
            lines_csv1 = file.readlines()

        with open(csv_file_d) as file:
            lines_csv2 = file.readlines()

        filtered_data_by_date_csv1 = [line.split(',') for line in lines_csv1 if line.startswith(date)]
        filtered_data_by_date_csv2 = [line.split(',') for line in lines_csv2 if line.startswith(date)]

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

        response = {
            "data": final_list
        }
        return Response(response, status=status.HTTP_200_OK)

#8
class SupportedRegionsApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        items = os.listdir("../../real_time")
        supported_regions = [item for item in items if os.path.isdir(os.path.join("../../real_time", item)) and item != 'weather_data']
        response = {
            "data": supported_regions
        }
        return Response(response, status=status.HTTP_200_OK)