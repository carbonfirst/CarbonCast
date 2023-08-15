from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from .models import CarbonCast
from .serializers import CarbonCastSerializer
from .helper import get_latest_csv_file
import os
import json

#Defining a list of US region codes
US_region_codes = ['AECI','AZPS', 'BPAT','CISO', 'DUK', 'EPE', 'ERCO', 'FPL', 
                'ISNE', 'LDWP', 'MISO', 'NEVP', 'NWMT', 'NYIS', 'PACE', 'PJM', 
                'SC', 'SCEG', 'SOCO', 'TIDC', 'TVA']

class CarbonCastListApiView(APIView):
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
        # print(line)
        # os.chdir("../../")
        # os.chdir(os.path.join('src', 'API', 'server'))
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
        





    # # 1. List all -- dummy code for testing
    # def get(self, request, *args, **kwargs):
    #     '''
    #     List all the CarbonCast items for given requested user
    #     '''
    #     CarbonCasts = CarbonCast.objects.filter(user = request.user.id)
    #     serializer = CarbonCastSerializer(CarbonCasts, many=True)
    #     return Response(serializer.data, status=status.HTTP_200_OK)

    # # 2. Create -- dummy code for testing
    # def post(self, request, *args, **kwargs):
    #     '''
    #     Create the CarbonCast with given CarbonCast data
    #     '''
    #     data = {
    #         'task': request.data.get('task'), 
    #         'completed': request.data.get('completed'), 
    #         'user': request.user.id
    #     }
    #     serializer = CarbonCastSerializer(data=data)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data, status=status.HTTP_201_CREATED)

    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)