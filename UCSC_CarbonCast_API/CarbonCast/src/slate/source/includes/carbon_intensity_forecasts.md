# Carbon Intensity Forecasts API

## Overview

The Carbon Intensity Forecasts API provides a forecast of the carbon intensity for a particular region for the given forecast period. The user may choose from '24h', '48h' or '96h' for the forecast period.

## Endpoint

- URL: `/v1/CarbonIntensityForecasts`
- Method: `GET`

## Parameters

- `regionCode` (mandatory): Region code parameter (e.g., 'AECI').
- `forecastPeriod` (optional): Forecast Period parameter. The default is set to 24h. Te (e.g., '48h').

## Responses

- `200`: HTTP 200 OK - Success response description
- `400`: HTTP 400 Bad Request - Description of possible error responses

## Example

To get the Carbon Intensity Forecasts for the region AECI for a period of 48h:

### Request

http
GET http://127.0.0.1:8000/v1/CarbonIntensityForecasts?regionCode=AECI&forecastPeriod=48h

The above command returns JSON structured like this:

{
    "data": [
        {
            "UTC time": "2023-09-10T00:00:00.000000000",
            "creation_time (UTC)": "2023-09-11 16:15:59",
            "version": "3.0",
            "region_code": "AECI",
            "carbon_intensity_avg_lifecycle": 644.10674,
            "carbon_intensity_avg_direct": 568.8284,
            "carbon_intensity_unit": "gCO2eg/kWh"
        },
        {
            "UTC time": "2023-09-10T01:00:00.000000000",
            "creation_time (UTC)": "2023-09-11 16:15:59",
            "version": "3.0",
            "region_code": "AECI",
            "carbon_intensity_avg_lifecycle": 651.75944,
            "carbon_intensity_avg_direct": 569.28782,
            "carbon_intensity_unit": "gCO2eg/kWh"
        }, ...
    ],
    "carbon_cast_version": "v3.0"
}
