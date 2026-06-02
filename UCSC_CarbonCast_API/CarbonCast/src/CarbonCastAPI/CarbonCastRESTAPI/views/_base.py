from django.shortcuts import render
import pyotp
import qrcode
import base64

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers, permissions, authentication
from django.contrib.auth import authenticate,login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.conf import settings
from django.core.cache import cache
from ..models import UserModel, UserThrottleLimit, EmissionActual, Forecast96, Weather, WeatherForecast, ModelRun
from ..serializers import UserSerializer
from ..helper import (
    get_latest_csv_file,
    get_actual_value_file_by_date,
    get_CI_forecasts_csv_file,
    get_energy_forecasts_csv_file,
    get_actual_value_file_by_date_with_metadata,
    get_CI_forecasts_csv_file_with_metadata,
    get_energy_forecasts_csv_file_with_metadata
)
import os
from ..consts import carbon_cast_version, authentication_classes, permission_classes, US_region_codes
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime
import time
def check_throttle_limit(user):
    # Rate limiting disabled - always allow requests
    return True
