import rdams_client as rc

dsid = 'ds084.1'


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

def submitDataRequest(template_dict):
    response = rc.submit_json(template_dict)
    print(response)
    assert response['code'] == 200
    print("Success!")
    return response

# param_map = getSeriesParams(dsid)
# print(param_map)
# getSeriesMetadata(dsid)
template_dict = getTemplateFile(dsid)
for k,v in template_dict.items():
    print(k, ": ", v)
response = submitDataRequest(template_dict)