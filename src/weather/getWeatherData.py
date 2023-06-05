import rdams_client as rc
import time

dsid = 'ds084.1'

regions = ['CISO', 'PJM', 'ERCOT', 'ISNE', 'SE', 'GB', 'DE', 'CA-ON', 'DK-DK2',
            'PL', 'MISO', 'AUS-NSW', 'AUS_QLD', 'AUS_SA']

coordDict = {
    'CISO': {'nlat': 42, 'slat': 32, 'wlon': -124.75, 'elon': -113.5},
    'PJM': {'nlat': 43, 'slat': 34.25, 'wlon': -91, 'elon': -73.5},
    'ERCOT': {'nlat': 36.5, 'slat': 25.25, 'wlon': -104.5, 'elon': -93.25},
    'ISNE': {'nlat': 48, 'slat': 40, 'wlon': 74.25, 'elon': -66.5},
    'SE': {'nlat': 69, 'slat': 55.25, 'wlon': 11.25, 'elon': 21.25},
    'GB': {'nlat': 61, 'slat': 49.75, 'wlon': -8.25, 'elon': 2.25},
    'DE': {'nlat': 55.25, 'slat': 47.25, 'wlon': 5.75, 'elon': 15},
    'CA-ON': {'nlat': 57.25, 'slat': 41.25, 'wlon': -95.75, 'elon': -73.75},
    'DK-DK2': {'nlat': 57.75, 'slat': 54.75, 'wlon': 7.25, 'elon': 11.25},
    'PL': {'nlat': 54.75, 'slat': 49, 'wlon': 14, 'elon': 24},
    'MISO' : {'nlat': 107.862115248933, 'slat': 28.4286900252724, 'wlon': -81.9130970652477, 'elon': 49.884274119856},
    'AUS-NSW':{'nlat': -34.75, 'slat': -36.50, 'wlon': 148.25, 'elon': 150},
    'AUS_QLD': {'nlat': -8.75, 'slat': -29.75, 'wlon': 137.50, 'elon': 154},
    'AUS_SA': {'nlat': -25.50, 'slat': -38.50, 'wlon': 128.50, 'elon': 141.50}, 
}

productDict = {
    'Analysis': 'Analysis/3-hour Forecast/6-hour Forecast/9-hour Forecast/12-hour Forecast/15-hour Forecast/18-hour Forecast/21-hour Forecast/24-hour Forecast/27-hour Forecast/30-hour Forecast/33-hour Forecast/36-hour Forecast/39-hour Forecast/42-hour Forecast/45-hour Forecast/48-hour Forecast/51-hour Forecast/54-hour Forecast/57-hour Forecast/60-hour Forecast/63-hour Forecast/66-hour Forecast/69-hour Forecast/72-hour Forecast/75-hour Forecast/78-hour Forecast/81-hour Forecast/84-hour Forecast/87-hour Forecast/90-hour Forecast/93-hour Forecast/96-hour Forecast',
    'Average': '3-hour Average (initial+0 to initial+3)/6-hour Average (initial+0 to initial+6)/3-hour Average (initial+6 to initial+9)/6-hour Average (initial+6 to initial+12)/3-hour Average (initial+12 to initial+15)/6-hour Average (initial+12 to initial+18)/3-hour Average (initial+18 to initial+21)/6-hour Average (initial+18 to initial+24)/3-hour Average (initial+24 to initial+27)/6-hour Average (initial+24 to initial+30)/3-hour Average (initial+30 to initial+33)/6-hour Average (initial+30 to initial+36)/3-hour Average (initial+36 to initial+39)/6-hour Average (initial+36 to initial+42)/3-hour Average (initial+42 to initial+45)/6-hour Average (initial+42 to initial+48)/3-hour Average (initial+48 to initial+51)/6-hour Average (initial+48 to initial+54)/3-hour Average (initial+54 to initial+57)/6-hour Average (initial+54 to initial+60)/3-hour Average (initial+60 to initial+63)/6-hour Average (initial+60 to initial+66)/3-hour Average (initial+66 to initial+69)/6-hour Average (initial+66 to initial+72)/3-hour Average (initial+72 to initial+75)/6-hour Average (initial+72 to initial+78)/3-hour Average (initial+72 to initial+81)/6-hour Average (initial+78 to initial+84)/3-hour Average (initial+84 to initial+87)/6-hour Average (initial+84 to initial+90)/3-hour Average (initial+90 to initial+93)/6-hour Average (initial+90 to initial+96)',
    'Accumulation': '3-hour Accumulation (initial+0 to initial+3)/6-hour Accumulation (initial+0 to initial+6)/3-hour Accumulation (initial+6 to initial+9)/6-hour Accumulation (initial+6 to initial+12)/3-hour Accumulation (initial+12 to initial+15)/6-hour Accumulation (initial+12 to initial+18)/3-hour Accumulation (initial+18 to initial+21)/6-hour Accumulation (initial+18 to initial+24)/3-hour Accumulation (initial+24 to initial+27)/6-hour Accumulation (initial+24 to initial+30)/3-hour Accumulation (initial+30 to initial+33)/6-hour Accumulation (initial+30 to initial+36)/3-hour Accumulation (initial+36 to initial+39)/6-hour Accumulation (initial+36 to initial+42)/3-hour Accumulation (initial+42 to initial+45)/6-hour Accumulation (initial+42 to initial+48)/3-hour Accumulation (initial+48 to initial+51)/6-hour Accumulation (initial+48 to initial+54)/3-hour Accumulation (initial+54 to initial+57)/6-hour Accumulation (initial+54 to initial+60)/3-hour Accumulation (initial+60 to initial+63)/6-hour Accumulation (initial+60 to initial+66)/3-hour Accumulation (initial+66 to initial+69)/6-hour Accumulation (initial+66 to initial+72)/3-hour Accumulation (initial+72 to initial+75)/6-hour Accumulation (initial+72 to initial+78)/3-hour Accumulation (initial+72 to initial+81)/6-hour Accumulation (initial+78 to initial+84)/3-hour Accumulation (initial+84 to initial+87)/6-hour Accumulation (initial+84 to initial+90)/3-hour Accumulation (initial+90 to initial+93)/6-hour Accumulation (initial+90 to initial+96)'
}

def getSeriesParams(dsid):

    param_response = rc.query(['-get_param_summary', dsid, '-np'])
    # -get_param_summary returns an rda response object that has more info that we need, so we'll filter it out
    param_data = param_response['result']['data']
    params = list(map(lambda x: x['param_description'], param_data))
    # print('\n'.join(params))
    param_map = {}
    for _param in param_data:
        long_name = _param['param_description']
        short_name = _param['param']
        param_map[long_name] = short_name

    for k,v in param_map.items(): print('{:7} : {}'.format(v, k))
    return param_map

def getSeriesMetadata(dsid):
    metadata_response = rc.query(['-get_metadata', dsid])
    # List of dicts representing a variable
    _vars = metadata_response['result']['data']

    # Just get temperature variables
    # TMP_variables = list(filter(lambda v: v['param'] == 'TMP',_vars)) 
    TMP_variables = list(filter(lambda v: v['param'] == 'A PCP',_vars)) 

    # Let's say we're only interested in 2020
    TMP_2020_variables = list(filter(
            lambda v: v['start_date'] < 202001010000 and v['end_date'] > 202101010000 ,TMP_variables
            )) 

    # We only should have 1 variable
    # assert len(TMP_2020_variables) == 1
    # print(TMP_2020_variables)
    print(len(TMP_2020_variables))
    my_var = TMP_2020_variables[0]

    for i in range(len(TMP_2020_variables)):
        # for prod in TMP_2020_variables[i]['product']:
            # print(len(prod))
        # print(TMP_2020_variables[i], type(TMP_2020_variables[i]))
        for k, v in TMP_2020_variables[i].items():
            if (k == "product"):
                print(k,": ",  v)
            if (k == "param_description"):
                print(k,": ",  v)
            # if (k == "levels"):
            #     print(k,": ",)
            #     for items in v:
            #           print(items["level"], ":", items["level_value"], " ",)

    # # Now let's look at the levels available:
    # for lev in my_var['levels']:
    #     print('{:6} {:10} {}'.format(lev['level'], lev['level_value'],lev['level_description']))

    # # But let's say I only want Isobaric surfaces between 100 and 500Hpa. 
    # ISBL_levels = set()
    # for lev in my_var['levels']:
    #     if lev['level_description'] == 'Isobaric surface' \
    #             and float(lev['level_value']) >= 100 \
    #             and float(lev['level_value']) <= 500:
    #         ISBL_levels.add(lev['level_value'])
    return None

def getTemplateFile(dsid):
    # response = rc.get_control_file_template(dsid)
    # template = response['result']['template'] # Template string
    # print(template)

    # Parse the string
    # template_dict = rc.read_control_file(template)
    template_dict = rc.read_control_file(control_file="ds084.1_control.ctl")

    # Insert our TMP param
    # template_dict['param'] = 'A PCP'
    # template_dict['level'] = 'ISBL:' + '/'.join(ISBL_levels)
    return template_dict

def buildControlDict(param, level, region, product):
    
   controlDict = { 
         'dataset' : 'ds084.1',
         'date':'202304070000/to/202304072359',
         'datetype':'init',
         'param': param,
         'level': level,
         'nlat': coordDict[region]['nlat'],
         'slat': coordDict[region]['slat'],
         'elon': coordDict[region]['elon'],
         'wlon': coordDict[region]['wlon'],
         'product': productDict[product],
         }
   
   return controlDict

def check_ready(rqst_id, wait_interval=60):
    """Checks if a request is ready."""
    for i in range(100): # 100 is arbitrary. Would wait 200 minutes for request
        res = rc.get_status(rqst_id)
        request_status = res['result']['status']
        if request_status == 'Completed':
            return True
        print(request_status)
        print('Not yet available. Waiting ' + str(wait_interval) + ' seconds.' )
        time.sleep(wait_interval)
    return False

def submitDataRequest(template_dict):
    response = rc.submit_json(template_dict)
    print(response)
    assert response['code'] == 200
    rqst_id = response['result']['request_id']
    check_ready(rqst_id)
    rc.download(rqst_id)
    rc.purge_request(rqst_id)
    print("Success!")


controlDict = buildControlDict('U GRD/V GRD', 'HTGL:10', 'CISO', 'Analysis')
submitDataRequest(controlDict)
