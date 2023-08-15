# todo/todo_api/serializers.py
from rest_framework import serializers
from .models import CarbonCast

# # Dummy code for testing
class CarbonCastSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonCast
        fields = ["task", "completed", "timestamp", "updated", "user"]

# #API 1 --not used as no models would be needed, thus, no corresponding serializer
# class CarbonCastSerializer1(serializers.ModelSerializer):
#     # json_data = serializers.JSONField()
#     # class Meta:
#         model = CarbonCast1
#         fields = [
#                   "UTC_time", 
#                   "region_code", 
#                   "carbon_intensity_avg_lifecycle", 
#                   "carbon_intensity_avg_direct", 
#                   "carbon_intensity_unit"
#                 ]
 