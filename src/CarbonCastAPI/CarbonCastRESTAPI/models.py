from django.db import models
from django.contrib.auth.models import User

# Create your models here.

# Dummy code for testing
class CarbonCast(models.Model):
    task = models.CharField(max_length = 180)
    timestamp = models.DateTimeField(auto_now_add = True, auto_now = False, blank = True)
    completed = models.BooleanField(default = False, blank = True)
    updated = models.DateTimeField(auto_now = True, blank = True)
    user = models.ForeignKey(User, on_delete = models.CASCADE, blank = True, null = True)

    def __str__(self):
        return self.task
    

# #1 if Models are used
# class CarbonCast1(models.Model):
#     UTC_time = models.DateTimeField(auto_now = False, blank = True)
#     region_code = models.CharField(max_length = 180)
#     carbon_intensity_avg_lifecycle = models.FloatField(blank=True)
#     carbon_intensity_avg_direct = models.FloatField(blank=True)
#     carbon_intensity_unit = models.CharField(default="gCO2eg/kWh", max_length=180)

#     def __str__(self):
#         return self.task
    
