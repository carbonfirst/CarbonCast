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
    password = models.CharField(max_length=128)
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

# Metric types supported by the platform. Carbon is the only metric backed by
# real ingestion today; demand/price are reserved so the schema and API can
# grow to cover them without a redesign (per the real-time service roadmap).
METRIC_CARBON = 'carbon'
METRIC_DEMAND = 'demand'
METRIC_PRICE = 'price'
METRIC_TYPE_CHOICES = (
    (METRIC_CARBON, 'Carbon intensity'),
    (METRIC_DEMAND, 'Energy demand'),
    (METRIC_PRICE, 'Electricity price'),
)


class EmissionActual(models.Model):
    """
    Stores actual observed rows (currently carbon/energy) per region+hour.
    - region: region code (e.g., 'AECI')
    - ts: timestamp (UTC) for the row
    - metric_type: which metric this row describes (carbon/demand/price). Existing
      rows default to 'carbon' so demand/price can be added later without a redesign.
    - lifecycle: lifecycle emission value (float, nullable)
    - direct: direct emission value (float, nullable)
    - source_file: original CSV filename (helpful for debugging)
    - data: raw row mapping (JSON) to keep any extra columns (e.g., energy source breakdown)
    """
    region = models.CharField(max_length=32, db_index=True)
    ts = models.DateTimeField(db_index=True)
    metric_type = models.CharField(
        max_length=16, choices=METRIC_TYPE_CHOICES, default=METRIC_CARBON, db_index=True
    )
    lifecycle = models.FloatField(null=True, blank=True)
    direct = models.FloatField(null=True, blank=True)
    source_file = models.CharField(max_length=256, null=True, blank=True)
    data = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('region', 'ts', 'metric_type')
        indexes = [
            models.Index(fields=['region', 'ts']),
            models.Index(fields=['region', 'metric_type', 'ts']),
        ]

    def __str__(self):
        return f"{self.region} [{self.metric_type}] @ {self.ts.isoformat()}"

class Forecast96(models.Model):
    """
    Forecast rows (supports up to 168h). Existing data keeps forecast_horizon=96.
    - metric_type: carbon (default) / demand / price, so the same table can hold
      forecasts for new metrics as the platform expands.
    """
    region = models.CharField(max_length=32, db_index=True)
    ts = models.DateTimeField(db_index=True)
    value = models.FloatField()
    metric_type = models.CharField(
        max_length=16, choices=METRIC_TYPE_CHOICES, default=METRIC_CARBON, db_index=True
    )
    forecast_type = models.CharField(max_length=32, default='lifecycle')
    forecast_horizon = models.IntegerField(default=96)
    batch_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    data = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('region', 'ts', 'forecast_type')
        indexes = [
            models.Index(fields=['region', 'ts', 'forecast_type']),
            models.Index(fields=['region', 'metric_type', 'ts']),
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


class WeatherForecast(models.Model):
    """
    Processed weather forecast data per region, ingested from the RDA automation
    tool's downloaded files or fallback sources (NOMADS, 12-month historical).
    """
    region = models.CharField(max_length=32, db_index=True)
    forecast_created = models.DateTimeField(db_index=True)
    forecast_target = models.DateTimeField(db_index=True)
    variable = models.CharField(max_length=32, db_index=True)
    value = models.FloatField(null=True)
    source = models.CharField(max_length=32, default='rda')
    data = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('region', 'forecast_created', 'forecast_target', 'variable')
        indexes = [
            models.Index(fields=['region', 'forecast_created']),
        ]

    def __str__(self):
        return f"{self.region} {self.variable} {self.source} @ {self.forecast_target.isoformat()}"


class ModelRun(models.Model):
    """Tracks each weekly model retraining execution."""
    region = models.CharField(max_length=32, db_index=True)
    model_name = models.CharField(max_length=64)
    run_started = models.DateTimeField(auto_now_add=True)
    run_completed = models.DateTimeField(null=True)
    status = models.CharField(max_length=16, default='running')
    weather_source = models.CharField(max_length=32, default='rda')
    config = models.JSONField(null=True, blank=True)
    metrics = models.JSONField(null=True, blank=True)
    model_artifact_path = models.CharField(max_length=512, null=True)

    def __str__(self):
        return f"{self.region} {self.model_name} {self.status} @ {self.run_started.isoformat()}"
