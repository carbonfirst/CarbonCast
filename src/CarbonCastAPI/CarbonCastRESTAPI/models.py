from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser

# Existing user models (unchanged except import ordering)
class UserThrottleLimit(models.Model):
    user = models.OneToOneField('UserModel', on_delete=models.CASCADE)
    throttle_limit = models.PositiveIntegerField()

class UserModel(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=50)
    throttle_limit = models.OneToOneField(UserThrottleLimit, on_delete=models.CASCADE, null=True)
    email = models.EmailField(max_length=100, unique=True)
    password = models.CharField(max_length=32)
    otp_enabled = models.BooleanField(default=False)
    otp_verified = models.BooleanField(default=False)
    otp_base32 = models.CharField(max_length=255, null=True)
    otp_auth_url = models.CharField(max_length=255, null=True)
    otp_qrcode_image = models.TextField(null=True)
    password_checked = models.BooleanField(default=False)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['password', 'name', 'email']

    def __str__(self):
        return self.username

# New models for SQLite integration

class EmissionActual(models.Model):
    """
    Stores actual emissions rows parsed from lifecycle and direct CSVs.
    - region: region code (e.g., 'AECI')
    - ts: timestamp (UTC) for the row
    - lifecycle: lifecycle emission value (float, nullable)
    - direct: direct emission value (float, nullable)
    - source_file: original CSV filename (helpful for debugging)
    - data: raw row mapping (JSON) to keep any extra columns (e.g., energy source breakdown)
    """
    region = models.CharField(max_length=32, db_index=True)
    ts = models.DateTimeField(db_index=True)
    lifecycle = models.FloatField(null=True, blank=True)
    direct = models.FloatField(null=True, blank=True)
    source_file = models.CharField(max_length=256, null=True, blank=True)
    data = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('region', 'ts')
        indexes = [
            models.Index(fields=['region', 'ts']),
        ]

    def __str__(self):
        return f"{self.region} @ {self.ts.isoformat()}"

class Forecast96(models.Model):
    """
    Generic 96-hour forecast rows (used for lifecycle/direct CI forecasts and simple energy forecasts).
    - region: region code
    - ts: timestamp for forecast row
    - value: numeric forecast value
    - forecast_type: 'lifecycle' | 'direct' | 'energy' (free text)
    - data: optional JSON blob with extra columns (creation_time/version/etc.)
    """
    region = models.CharField(max_length=32, db_index=True)
    ts = models.DateTimeField(db_index=True)
    value = models.FloatField()
    forecast_type = models.CharField(max_length=32, default='lifecycle')
    data = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('region', 'ts', 'forecast_type')
        indexes = [
            models.Index(fields=['region', 'ts', 'forecast_type']),
        ]

    def __str__(self):
        return f"{self.region} {self.forecast_type} @ {self.ts.isoformat()} -> {self.value}"

class Weather(models.Model):
    """
    Lightweight weather table for runtime weather rows.
    - region, ts, temp (optional), raw JSON for other columns.
    """
    region = models.CharField(max_length=32, db_index=True)
    ts = models.DateTimeField(db_index=True)
    temp = models.FloatField(null=True, blank=True)
    data = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('region', 'ts')
        indexes = [
            models.Index(fields=['region', 'ts']),
        ]

    def __str__(self):
        return f"{self.region} weather @ {self.ts.isoformat()}"
