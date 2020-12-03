import requests
import time
pass
bias_parameters = {'ip' : '10.123.1.84',
                   'port_base':5010,
                   'port_stride':10,
                   'expected_camera_num':2}

#% check camera number
def bias_send_command(camera_dict,command):
    port = camera_dict['port']
    ip = camera_dict['ip']
    r = requests.get('http://{ip}:{port}/{command}'.format(ip=ip,port = port,command = command))
    return r.json()[0]
def bias_get_camera_list(bias_parameters):
    camera_list = list()
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
    return camera_list

def bias_start_movie(camera_list):
    #%
    for camera_dict in camera_list:
        command = '?get-status'
        try:
            r = bias_send_command(camera_dict,command)
            if not r['value']['connected']:
                print('camera not connected - {}'.format(camera_dict))
        except:
            print('ERROR with camera access - {}'.format(camera_dict))
            
    for camera_dict in camera_list:
        command = '?start-capture'
        r = bias_send_command(camera_dict,command)
    
    checkInterval = 0.1
    maxNumberOfChecks = 50 
    iternow = 0
    allcamscapturing = False
    command = '?get-status'
    while not allcamscapturing and iternow < maxNumberOfChecks:
        allcamscapturing = True
        iternow += 1
        for camera_dict in camera_list:
            r = bias_send_command(camera_dict,command)
            if not r['value']['capturing']:
                allcamscapturing = False
                break
        time.sleep(checkInterval)
    if not allcamscapturing:
        print('Not sure if all the cameras are capturing..')

def bias_stop_movie(camera_list):
    time.sleep(.1) # this is needed for some reason
    for camera_dict in camera_list:
        command = '?stop-capture'
        r = bias_send_command(camera_dict,command)
        
    checkInterval = 0.1
    maxNumberOfChecks = 50 
    iternow = 0
    allcamsstopped = False
    command = '?get-status'
    while not allcamsstopped and iternow < maxNumberOfChecks:
        allcamsstopped = True
        iternow += 1
        for camera_dict in camera_list:
            r = bias_send_command(camera_dict,command)
            if r['value']['capturing']:
                allcamsstopped = False
                break
        time.sleep(checkInterval)
    if not allcamsstopped:
        print('Not sure if all the cameras stopped..')
def bias_get_movie_names(camera_list):
    command = '?get-video-file'
    file_list = list()
    for camera_dict in camera_list:
        r = bias_send_command(camera_dict,command)
        file_list.append(r['value'])
    return file_list
camera_list = bias_get_camera_list(bias_parameters)
