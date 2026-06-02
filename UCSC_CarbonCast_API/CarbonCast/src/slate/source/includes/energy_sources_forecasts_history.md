# Energy Sources Forecasts History API

## Overview

The Energy Sources Forecasts History API provides provides a history of energy sources forecasts for a particular region, on a particular date for a specified period of time.

## Endpoint

- URL: `/v1/CarbonIntensityForecastsHistory`
- Method: `GET`

## Parameters

- `regionCode` (mandatory): Region code parameter (e.g., 'AECI').
- `date` (mandatory): Date parameter (e.g., '2023-08-19').
- `forecastPeriod` (optional): Forecast Period parameter. The default is set to 24h. Te (e.g., '48h').

## Responses

- `200`: HTTP 200 OK - Success response description
- `400`: HTTP 400 Bad Request - Description of possible error responses

## Example

To get the Carbon Intensity Forecasts History for the region AECI for the date 2023-08-19:

### Request

http
GET /v1/EnergySourcesForecastsHistory?regionCode=AECI&date=2023-08-19&forecastPeriod=48h

The above command returns JSON structured like this:

{
    "data": [
        {
            "UTC time": "2023-08-19 00:00:00",
            "creation_time (UTC)": "2023-08-20 14:50:47",
            "version": "3.0",
            "region_code": "AECI",
            "avg_coal_production_forecast": "911.63421",
            "avg_nat_gas_production_forecast": "1508.62855",
            "avg_nuclear_production_forecast": "0",
            "avg_oil_production_forecast": "0",
            "avg_hydro_production_forecast": "0",
            "avg_solar_production_forecast": "0",
            "avg_wind_production_forecast": "1837.78003\n",
            "avg_other_production_forecast": "0"
        },
        {
            "UTC time": "2023-08-19 01:00:00",
            "creation_time (UTC)": "2023-08-20 14:50:47",
            "version": "3.0",
            "region_code": "AECI",
            "avg_coal_production_forecast": "935.42209",
            "avg_nat_gas_production_forecast": "1450.8531",
            "avg_nuclear_production_forecast": "0",
            "avg_oil_production_forecast": "0",
            "avg_hydro_production_forecast": "0",
            "avg_solar_production_forecast": "0",
            "avg_wind_production_forecast": "1823.9399\n",
            "avg_other_production_forecast": "0"
        }, ...
    ],
    "carbon_cast_version": "v3.0"
}
