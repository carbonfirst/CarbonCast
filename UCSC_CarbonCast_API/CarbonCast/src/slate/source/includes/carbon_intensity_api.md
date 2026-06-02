# Carbon Intensity API

## Overview

The Carbon Intensity API provides information about carbon intensity in various regions.

## Endpoint

- URL: `/v1/CarbonIntensity/`
- Method: `GET`

## Parameters

- `regionCode` (optional): Region code parameter (e.g., 'AECI').

## Responses

- `200`: HTTP 200 OK - Success response description
- `400`: HTTP 400 Bad Request - Description of possible error responses

## Example
To get the Carbon Intensity for the region AECI:

### Request

http
GET /api/carbon-intensity/?region_code=AECI

The above command returns JSON structured like this:

{
  "data": [
    {
      "UTC time": "2023-10-17T00:00:00Z",
      "creation_time (UTC)": "2023-10-17T12:00:00Z",
      "version": "1.0",
      "region_code": "AECI",
      "carbon_intensity_avg_lifecycle": 100.0,
      "carbon_intensity_avg_direct": 90.0,
      "carbon_intensity_unit": "gCO2eg/kWh"
    }
  ]
}


