# Carbon Intensity History API

## Overview

The Carbon Intensity History API provides information about carbon intensity history for various regions and dates.

## Endpoint

- URL: `/v1/CarbonIntensityHistory/`
- Method: `GET`

## Parameters

- `regionCode` (mandatory): Region code parameter (e.g., 'AECI').
- `date` (mandatory): Date parameter (e.g., '2023-08-19').

## Responses

- `200`: HTTP 200 OK - Success response description
- `400`: HTTP 400 Bad Request - Description of possible error responses

## Example

To get the Carbon Intensity History for the region AECI for the date 2023-08-19:

### Request

http
GET /v1/CarbonIntensityHistory?region_code=AECI&date=2023-08-19

The above command returns JSON structured like this:

{
    "data": [ 
        { 
            "UTC time": "2023-08-19 00:00:00",
            "creation_time (UTC)": "2023-08-20 22:01:18",
            "version": "3.0",
            "region_code": "AECI",
            "carbon_intensity_avg_lifecycle": 522.42,
            "carbon_intensity_avg_direct": 430.15,
            "carbon_intensity_unit": "gCO2eg/kWh"
        },
        {
            "UTC time": "2023-08-19 01:00:00",
            "creation_time (UTC)": "2023-08-20 22:01:18",
            "version": "3.0",
            "region_code": "AECI",
            "carbon_intensity_avg_lifecycle": 485.02,
            "carbon_intensity_avg_direct": 396.01,
            "carbon_intensity_unit": "gCO2eg/kWh"
        }
    ],
    "carbon_cast_version": "v3.0"
}
