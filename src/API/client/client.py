import http.client
import json
import urllib.parse
from random import randrange


server_host = 'localhost'

#Defining a list of US region codes
US_region_codes = ['AECI','AZPS', 'BPAT','CISO', 'DUK', 'EPE', 'ERCO', 'FPL', 
                'ISNE', 'LDWP', 'MISO', 'NEVP', 'NWMT', 'NYIS', 'PACE', 'PJM', 
                'SC', 'SCEG', 'SOCO', 'TIDC', 'TVA']
#1
try:
    conn = http.client.HTTPConnection(server_host, 13000)
    req_data = {'regionCode':US_region_codes[randrange(len(US_region_codes))]}      
        
    url = "/CarbonIntensity?"+urllib.parse.urlencode(req_data)
    # print(req_data)
       
    conn.request('GET', url)
    response = conn.getresponse()

    if response.status == 200:
            response_content = response.read().decode('utf-8')
            response_data = json.loads(response_content)
            print(response_data)

    else:
             print(f"Error: server returned status code {response.status_code}")   

except json.JSONDecodeError as e:
       print(f'Error decoding response content: {response_content}. Exception: {e}')

except Exception as e:
        print(f'Error retrieving data from server: {e}')
    
#2
try:
    conn = http.client.HTTPConnection(server_host, 13000)
    req_data = {'regionCode':US_region_codes[randrange(len(US_region_codes))]}      
        
    url = "/EnergySources?"+urllib.parse.urlencode(req_data)
    # print(req_data)
       
    conn.request('GET', url)
    response = conn.getresponse()

    if response.status == 200:
            response_content = response.read().decode('utf-8')
            response_data = json.loads(response_content)
            print(response_data)

    else:
             print(f"Error: server returned status code {response.status_code}")   

except json.JSONDecodeError as e:
       print(f'Error decoding response content: {response_content}. Exception: {e}')

except Exception as e:
        print(f'Error retrieving data from server: {e}')

#3
try:
    conn = http.client.HTTPConnection(server_host, 13000)

    date_input = input("Enter a date in yyyy-mm-dd format:")

    req_data = {
                'regionCode':US_region_codes[randrange(len(US_region_codes))], 
                'date': date_input
                }      
        
    url = "/CarbonIntensityHistory?"+urllib.parse.urlencode(req_data)
    # print(req_data)
       
    conn.request('GET', url)
    response = conn.getresponse()

    if response.status == 200:
            response_content = response.read().decode('utf-8')
            response_data = json.loads(response_content)
            final_carbon_list = response_data["data"]
            for items in final_carbon_list:
                   print(items)
        #     print(response_data)

    else:
             print(f"Error: server returned status code {response.status_code}")   

except json.JSONDecodeError as e:
       print(f'Error decoding response content: {response_content}. Exception: {e}')

except Exception as e:
        print(f'Error retrieving data from server: {e}')

#4
try:
    conn = http.client.HTTPConnection(server_host, 13000)

    date_input = input("Enter a date in yyyy-mm-dd format:")

    req_data = {
                'regionCode':US_region_codes[randrange(len(US_region_codes))], 
                'date': date_input
                }      
        
    url = "/EnergySourcesHistory?"+urllib.parse.urlencode(req_data)
    # print(req_data)
       
    conn.request('GET', url)
    response = conn.getresponse()

    if response.status == 200:
            response_content = response.read().decode('utf-8')
            response_data = json.loads(response_content)
            final_carbon_list = response_data["data"]
            for items in final_carbon_list:
                   print(items)
        #     print(response_data)

    else:
             print(f"Error: server returned status code {response.status_code}")   

except json.JSONDecodeError as e:
       print(f'Error decoding response content: {response_content}. Exception: {e}')

except Exception as e:
        print(f'Error retrieving data from server: {e}')


#6
try:
    conn = http.client.HTTPConnection(server_host, 13000)

    date_input = input("To get the real forecasted Carbon Intensity values, enter a date in yyyy-mm-dd format:")

    req_data = {
                'regionCode':US_region_codes[randrange(len(US_region_codes))], 
                'date': date_input
                }      
        
    url = "/CarbonIntensityForecastsHistory?"+urllib.parse.urlencode(req_data)
    # print(req_data)
       
    conn.request('GET', url)
    response = conn.getresponse()

    if response.status == 200:
            response_content = response.read().decode('utf-8')
            response_data = json.loads(response_content)
            final_carbon_list = response_data["data"]
            for items in final_carbon_list:
                   print(items)
        #     print(response_data)

    else:
             print(f"Error: server returned status code {response.status_code}")   

except json.JSONDecodeError as e:
       print(f'Error decoding response content: {response_content}. Exception: {e}')

except Exception as e:
        print(f'Error retrieving data from server: {e}')





