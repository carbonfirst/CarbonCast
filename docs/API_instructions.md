Instructions to run CarbonCastAPI: 

1. Clone the Django API Branch

2. Choose the dockerized version or without docker:
    - With Docker:

      Inside the main CarbonCast Folder, run 
			```docker-compose up```

		  (The API routes will be accessible on 0.0.0.0 instead of 127.0.0.1 or localhost)

    - Without Docker:
      
      - Inside the main CarbonCast Folder, run migrations:

        ```python src/CarbonCastAPI/manage.py makemigrations ``` 

        ``` python src/CarbonCastAPI/manage.py migrate ```
      - Run the Server:

        ```python src/CarbonCastAPI/manage.py runserver```

3. We can check if a user needs to be authenticated to use the APIs based on the response received using the API: http://127.0.0.1:8000/v1/UserAuthenticationEnforced 

4. Based on the above response, if users need to log in to get access to the API endpoints, follow these steps:
    - To Sign Up, send a POST request to http://127.0.0.1:8000/v1/SignUp  with the parameters “username”, “name”, “password” and “email”. 
    Example:
    ```json 
    {
    "username": "Test1",
    "name": "Test1",
    "password": "1234567g",
    "email": "test1@abc.com"
    }
    ```

    - To Sign In, send a POST request to http://127.0.0.1:8000/v1/SignIn with the parameters “username”, “name”, “password” and “email”. Example:
    ```json 
    {
    "username": "Test1",
    "name": "Test1",
    "password": "1234567g",
    "email": "test1@abc.com"
    }
    ```
    - Both Sign Up and Sign In return a response with the user details. The “otp_base32” field can be entered in any authenticator to get the OTP for 2-step verification. The url in “otp_auth_url” can be used to generate a QR code image for scanning using any authenticator, or optionally, the “otp_qrcode_image” sends the encoded image, which can be decoded to get the QR code. (A QR code also gets generated and stored in the code temporarily for easy access)
    - Once we have the OTP,  send a POST request with the username to the Verification endpoint http://127.0.0.1:8000/v1/VerifyOTP for 2-step verification and to get access to the system.
    ```json
    {
    "username": "Test1",
    "token": "918641"
    }
    ```

5. Access the API endpoint: 

    - http://127.0.0.1:8000/v1/CarbonIntensity?region_code=all  ( can vary the region_code parameter to specific regions or all regions;  if region_code invalid or not entered, message will pop up )
    - http://127.0.0.1:8000/v1/EnergySources?region_code=all  (can vary the region_code parameter to specific regions or all regions; if region_code invalid or not entered, message will pop up)
    - http://127.0.0.1:8000/v1/CarbonIntensityHistory?regionCode=AECI&date=2023-08-19  (can specify any regionCode and date till 2023-09-10) 
    - http://127.0.0.1:8000/v1/EnergySourcesHistory?regionCode=AECI&date=2023-08-19 (can specify any regionCode and date till 2023-09-10)
    - http://127.0.0.1:8000/v1/CarbonIntensityForecasts?regionCode=AECI&forecastPeriod=48h (can specify any regionCode and if forecastPeriod not specified, default will be 24h; otherwise specify forecastPeriod as 24h, 48h or 96h)
    - http://127.0.0.1:8000/v1/CarbonIntensityForecastsHistory?regionCode=AECI&date=2023-08-19 (can specify any regionCode and date till 2023-09-10)
    - http://127.0.0.1:8000/v1/EnergySourcesForecastsHistory?regionCode=AECI&date=2023-08-19&forecastPeriod=48h (can specify any regionCode and date till 2023-09-10; if forecastPeriod not specified, default will be 24h; otherwise specify forecastPeriod as 24h, 48h or 96h)
    - http://127.0.0.1:8000/v1/SupportedRegions 


6. Logout: To log out, it is necessary to be logged in and have an active session. Then access the API endpoint: http://127.0.0.1:8000/v1/Logout

7. A cron job was created to refresh the individual user and overall global limits at 12:00 am everyday. To set up the cron job run: 
```crontab -e ```
and enter the following command to run cron job everyday at 12:00 am: 

    ```0 0 * * * /usr/bin/python3 /path/to/your/manage.py refresh_limits ```
