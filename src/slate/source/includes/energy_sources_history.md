# Energy Sources History API

## Overview

The Energy Sources History API provides information about energy sources history for various regions and dates.

## Endpoint

- URL: `/v1/EnergySourcesHistory`
- Method: `GET`

## Parameters

- `regionCode` (mandatory): Region code parameter (e.g., 'AECI').
- `date` (mandatory): Date parameter (e.g., '2023-08-19').

## Responses

- `200`: HTTP 200 OK - Success response description
- `400`: HTTP 400 Bad Request - Description of possible error responses

## Example

To get the Energy Sources History for the region AECI for the date 2023-08-19:

### Request

http
GET /v1/EnergySourcesHistory?regionCode=AECI&date=2023-08-19

The above command returns JSON structured like this:

{
    "data": [
        {
            "UTC time": "2023-08-19 00:00:00",
            "creation_time (UTC)": "2023-08-20 22:01:18",
            "version": "3.0",
            "region_code": "AECI",
            "coal": "616.0",
            "nat_gas": "1490.0",
            "nuclear": "0",
            "oil": "0",
            "hydro": "0",
            "solar": "0",
            "wind": "264.0",
            "other": "0"
        },
        {
            "UTC time": "2023-08-19 01:00:00",
            "creation_time (UTC)": "2023-08-20 22:01:18",
            "version": "3.0",
            "region_code": "AECI",
            "coal": "500.0",
            "nat_gas": "1394.0",
            "nuclear": "0",
            "oil": "0",
            "hydro": "0",
            "solar": "0",
            "wind": "368.0",
            "other": "0"
        }, ...
    ],
    "carbon_cast_version": "v3.0"
}
