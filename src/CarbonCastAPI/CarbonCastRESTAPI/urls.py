from django.contrib import admin
from django.urls import path, include
from .views import (
    CarbonCastListApiView
)

urlpatterns = [
    path('api', CarbonCastListApiView.as_view()),
]
