from drf_yasg import openapi

API_INFO = openapi.Info(
    title="CarbonCast API",
    default_version='v1',
    description="REST APIs",
    terms_of_service="https://www.google.com/policies/terms/",
    license=openapi.License(name="BSD License"),
)