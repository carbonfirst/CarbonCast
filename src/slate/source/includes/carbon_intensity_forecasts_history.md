# Carbon Intensity Forecasts History API

## Overview

The Carbon Intensity Forecasts History API provides provides a history of carbon intensity forecasts for a particular region and a particular date.

## Endpoint

- URL: `/v1/CarbonIntensityForecastsHistory`
- Method: `GET`

## Parameters

- `regionCode` (mandatory): Region code parameter (e.g., 'AECI').
- `date` (mandatory): Date parameter (e.g., '2023-08-19').

## Responses

- `200`: HTTP 200 OK - Success response description
- `400`: HTTP 400 Bad Request - Description of possible error responses

## Example

To get the Carbon Intensity Forecasts History for the region AECI for the date 2023-08-19:

### Request

http
GET /v1/CarbonIntensityForecastsHistory?regionCode=AECI&date=2023-08-19

The above command returns JSON structured like this:

{
    "data": [
        {
            "UTC time": "2023-08-19T00:00:00.000000000",
            "creation_time (UTC)": "2023-08-20 14:50:47",
            "version": "3.0",
            "region_code": "AECI",
            "forecasted_avg_carbon_intensity_lifecycle": 605.70294,
            "forecasted_avg_carbon_intensity_direct": 485.28822,
            "carbon_intensity_unit": "gCO2eg/kWh"
        },
        {
            "UTC time": "2023-08-19T01:00:00.000000000",
            "creation_time (UTC)": "2023-08-20 14:50:47",
            "version": "3.0",
            "region_code": "AECI",
            "forecasted_avg_carbon_intensity_lifecycle": 609.4448,
            "forecasted_avg_carbon_intensity_direct": 484.65894,
            "carbon_intensity_unit": "gCO2eg/kWh"
        }, ...
    ],
    "carbon_cast_version": "v3.0"
}
