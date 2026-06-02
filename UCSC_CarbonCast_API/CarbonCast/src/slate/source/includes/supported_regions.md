# Supported Regions API

## Overview

The Supported Regions API provides provides a list of the Supported Regions.

## Endpoint

- URL: `/v1/SupportedRegions`
- Method: `GET`

## Parameters

None

## Responses

- `200`: HTTP 200 OK - Success response description
- `400`: HTTP 400 Bad Request - Description of possible error responses

## Example

To get the Supported Regions:

### Request

http
GET /v1/SupportedRegions

The above command returns JSON structured like this:

{
    "US_supported_regions": [
        "LDWP",
        "SCEG",
        "NYIS",
        "SC",
        "SOCO",
        "ISNE",
        "BPAT",
        "EPE",
        "TVA",
        "AECI",
        "PACE",
        "NWMT",
        "FPL",
        "DUK",
        "WACM",
        "PJM",
        "TIDC",
        "MISO",
        "ERCO",
        "CISO",
        "NEVP",
        "AZPS",
        "SRP"
    ],
    "carbon_cast_version": "v3.0"
}