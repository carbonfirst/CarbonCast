"""
CarbonCast REST API views.

This package was split out of a single large ``views.py`` for readability.
Behaviour is unchanged: every view class is re-exported here so existing
imports such as ``from .views import CarbonIntensityApiView`` continue to work.
"""
from .carbon_intensity import (
    CarbonIntensityApiView,
    CarbonIntensityHistoryApiView,
)
from .energy_sources import (
    EnergySourcesApiView,
    EnergySourcesHistoryApiView,
)
from .forecasts import (
    CarbonIntensityForecastsApiView,
    CarbonIntensityForecastsHistoryApiView,
    EnergySourcesForecastsHistoryApiView,
)
from .regions import (
    SupportedRegionsApiView,
    DataFreshnessApiView,
)
from .retraining import RetrainingStatusApiView
from .pipeline_status import PipelineStatusApiView, PipelineHealthApiView
from .auth import (
    UserAuthenticationEnforcedView,
    LogoutAPIView,
    SignUpApiView,
    SignInApiView,
    VerifyOTP,
)
from ._base import check_throttle_limit

__all__ = [
    "CarbonIntensityApiView",
    "CarbonIntensityHistoryApiView",
    "EnergySourcesApiView",
    "EnergySourcesHistoryApiView",
    "CarbonIntensityForecastsApiView",
    "CarbonIntensityForecastsHistoryApiView",
    "EnergySourcesForecastsHistoryApiView",
    "SupportedRegionsApiView",
    "DataFreshnessApiView",
    "RetrainingStatusApiView",
    "PipelineStatusApiView",
    "PipelineHealthApiView",
    "UserAuthenticationEnforcedView",
    "LogoutAPIView",
    "SignUpApiView",
    "SignInApiView",
    "VerifyOTP",
    "check_throttle_limit",
]
