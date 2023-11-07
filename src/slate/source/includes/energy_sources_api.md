# Energy Sources API

## Overview

The Energy Sources API provides information about energy sources in various regions.

## Endpoint

- URL: `/api/energy-sources/`
- Method: `GET`

## Parameters

- `regionCode` (optional): Region code parameter (e.g., 'AECI').

## Responses

- `200`: HTTP 200 OK - Success response description
- `400`: HTTP 400 Bad Request - Description of possible error responses

## Example
To get the energy sources for a region, say AECI:

### Request

```http
GET /api/energy-sources/?region_code=AECI

>The above command returns JSON structured like this:

{
    "data": [
        {
            "UTC time": "2023-10-17 12:00:00",
            "creation_time (UTC)": "2023-10-17 11:45:00",
            "version": "1.0",
            "region_code": "AECI",
            "coal": "2500",
            "nat_gas": "1800",
            "nuclear": "1200",
            "oil": "300",
            "hydro": "800",
            "solar": "400",
            "wind": "700",
            "other": "100"
        }
    ],
    "carbon_cast_version": "1.0"
}
