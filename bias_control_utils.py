import requests
bias_parameters = {'ip' : '10.123.1.84',
                   'port_base':5010,
                   'port_stride':10,
                   'expected_camera_num':2}
camera_list = list()


# =============================================================================
# bias_port_base = 5010
# bias_port_stride = 10
# camera_list = list()
# command = '?connect'
# r = requests.get('http://{ip}:{port}/{command}'.format(ip=bias_ip,port = bias_port,command = command))
# response = r.json()[0]
# 
# =============================================================================

#%% check camera number
for camera_idx in range(0,bias_parameters['expected_camera_num'],1):
    port = bias_parameters['port_base']+camera_idx*bias_parameters['port_stride']
    ip = bias_parameters['ip']
    command = '?get-status'
    try:
        r = requests.get('http://{ip}:{port}/{command}'.format(ip=ip,port = port,command = command))
        camera_dict = {'ip':ip,
                       'port':port,
                       'status':r.json()[0]['value']}
        camera_list.append(camera_dict)
    except:
        print('ERROR: less than expected cameras found')
        break
