from django.contrib import admin
from django.urls import path, include
from .views import (
    CarbonIntensityApiView,
    EnergySourcesApiView,
    CarbonIntensityHistoryApiView,
    EnergySourcesHistoryApiView,
    CarbonIntensityForecastsApiView,
    CarbonIntensityForecastsHistoryApiView,
    EnergySourcesForecastsHistoryApiView,
    SupportedRegionsApiView,
    SignUpApiView,
    SignInApiView,
    LogoutAPIView,
    VerifyOTP
)

urlpatterns = [
    path('CarbonIntensity', CarbonIntensityApiView.as_view()),
    path('EnergySources', EnergySourcesApiView.as_view()),
    path('CarbonIntensityHistory', CarbonIntensityHistoryApiView.as_view()),
    path('EnergySourcesHistory', EnergySourcesHistoryApiView.as_view()),
    path('CarbonIntensityForecasts', CarbonIntensityForecastsApiView.as_view()),
    path('CarbonIntensityForecastsHistory', CarbonIntensityForecastsHistoryApiView.as_view()),
    path('EnergySourcesForecastsHistory', EnergySourcesForecastsHistoryApiView.as_view()),   
    path('SupportedRegions', SupportedRegionsApiView.as_view()),
    path('SignUp', SignUpApiView.as_view()),
    path('SignIn', SignInApiView.as_view()),
    path('Logout', LogoutAPIView.as_view()),
    path('VerifyOTP', VerifyOTP.as_view()),
]
