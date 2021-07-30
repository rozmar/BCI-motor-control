from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine
from pybpodapi.bpod.hardware.events import EventName
from pybpodapi.bpod.hardware.output_channels import OutputChannel
from pybpodapi.com.messaging.trial import Trial
#%%
from datetime import datetime
from itertools import permutations
#import zaber.serial as zaber_serial
import time
import json
import numpy as np
import requests
import os, sys 
import socket
import threading
def splitthepath(path):
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path: # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts
#%


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

def bias_start_movie(camera_list,video_dir,subject_name,session_name,triali):
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
        trial_name = 'trial_{:03d}'.format(triali)
        command = '?set-video-file={}.avi'.format(os.path.join(video_dir,subject_name,camera_dict['camera_name'],session_name,trial_name,trial_name))
        r = bias_send_command(camera_dict,command)
        command = '?enable-logging'
        r = bias_send_command(camera_dict,command)
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


global messagelist
messagelist = list()
def rec_UDP(ip,port):
    global messagelist
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((ip, port))
        data, addr = sock.recvfrom(1024)
        messagelist.append(data.decode())
        print(data.decode())
        if data.decode() == 'stoptheudpserver':
            break
        #return data

def calculate_step_time(s,v,a):
    #s : step size in mm
    #v : max speed in mm/s
    #a : accelerateio in mm/s**2
    t1 = v/a
    s1 = t1*v
    if s1>=s:
        t = 2*np.sqrt((s/a)/2)
    else:
        t = 2*v/a+(s-(t1*v))/v
    return t



#%%


# ======================================================================================
# Main function starts here
# ====================================================================================== 

# ========= Setting up environment (path, metadata, etc.) ==========
my_bpod = Bpod()
history = my_bpod.session.history
experiment_name = 'not defined' 
setup_name = 'not defined' 
subject_name = 'not defined' 
experimenter_name = 'not defined'
for histnow in history:
    if hasattr(histnow, 'infoname'):
        if histnow.infoname ==  'SUBJECT-NAME':
            subject_name = histnow.infovalue
            subject_name = subject_name[2:subject_name[2:].find("'")+2]
        elif histnow.infoname ==  'CREATOR-NAME':
            experimenter_name = histnow.infovalue
            experimenter_name = experimenter_name[2:experimenter_name[2:].find('"')+2]
        elif histnow.infoname == 'SETUP-NAME':
            setup_name = histnow.infovalue
        elif histnow.infoname ==  'EXPERIMENT-NAME':
            experiment_name = histnow.infovalue

print('setup_name: ',setup_name)
print('experiment_name: ',experiment_name)
print('subject_name: ',subject_name)
path = my_bpod.session._path
pathlist = splitthepath(path)
session_name = pathlist[-2]
pathnow = ''
for dirnow in pathlist:
    if dirnow == 'Projects':
        rootdir = pathnow
    if dirnow == 'experiments':
        projectdir = pathnow
        subjectdir = os.path.join(projectdir,'subjects',subject_name)
    if dirnow == 'setups':
        experimentpath = pathnow
    if dirnow == 'sessions':
        setuppath = pathnow
    pathnow = os.path.join(pathnow,dirnow)
    



# ================ Define subejct-specific variables ===============
# ----- Load previous used parameters from json file -----
subjectfile = os.path.join(subjectdir,'variables.json')
if os.path.exists(subjectfile):
    with open(subjectfile) as json_file:
        variables = json.load(json_file)
    print('subject variables loaded from Json file')
else:
    variables = { # Delayed
            'ValveOpenTime_L' : .04,
            'ValveOpenTime_R' : .04,
            'AutoWater': True,
            'ITI' : 3., #s
            'LowActivityTime': 1., #s - trial doesn't start until the activity is below threshold for this long
            'AutoWaterTimeMultiplier':.5,
            'NeuronResponseTime':30,# time for the mouse to modulate its neuronal activity
            'LickResponseTime':2,# time for the mouse to lick     
            'RewardConsumeTime':2,
            'BaselineZaberForwardStepFrequency':0.0,
            'RecordMovies':False,
            'CameraFrameRate' : 400,
            'LowActivityCheckAtTheBeginning':True,
            'EnforceStopLicking':True,
            'SoundOnRewardZoneEntry':True,
            }
variables_subject = variables.copy()

# =================== Define rig-specific variables (ports, etc.) =========================
variables = dict()
setupfile = os.path.join(setuppath,'variables.json')
if os.path.exists(setupfile):
    with open(setupfile) as json_file:
        variables = json.load(json_file)
    print('setup variables loaded from Json file')
else:
    if setup_name =='KayvonScope':
        # for setup: Tower - 1
        variables['GoCue_ch'] = OutputChannel.PWM5
        variables['WaterPort_L_ch_out'] = 1
        variables['WaterPort_L_ch_in'] = EventName.Port1In
        variables['WaterPort_L_PWM'] = OutputChannel.PWM1
        variables['WaterPort_R_ch_out'] = 2
        variables['WaterPort_R_ch_in'] = EventName.Port2In
        variables['WaterPort_R_PWM'] = OutputChannel.PWM2
        variables['ScanimageROIisActive_ch_in'] = EventName.Wire2Low
        variables['ResponseEligibilityChannel'] =  OutputChannel.Wire3 # wire
        variables['ResetTrial_ch_out'] =  OutputChannel.PWM8
        variables['MotorInRewardZone'] =  EventName.Port8Out
        variables['CameraTriggerOut'] = OutputChannel.Wire1
        variables['StepZaberForwardManually_ch_out'] =  OutputChannel.PWM6
        variables['BitCode_ch_out'] =  OutputChannel.BNC1
        variables['Scanimage_trial_start_ch_out'] =  OutputChannel.BNC2
        variables['WhiteNoise_ch'] = OutputChannel.PWM4
        variables['RewardZoneCue_ch'] = OutputChannel.PWM7
        variables['UDP_IP_bpod'] = '10.123.1.55'
        variables['UDP_PORT_bpod'] = 1001
        variables['Bias_ip'] = '10.123.1.84'
        variables['Bias_port_base'] = 5010
        variables['Bias_port_stride'] = 10
        variables['Bias_expected_camera_num'] = 2
        #TODO parameters are missing heer
    elif setup_name =='DOM3':
    # for setup: DOM3
        variables['GoCue_ch'] = OutputChannel.PWM4
        variables['WaterPort_L_ch_out'] = 1
        variables['WaterPort_L_ch_in'] = EventName.Port1In
        variables['WaterPort_L_PWM'] = OutputChannel.PWM1
        variables['WaterPort_R_ch_out'] = 2
        variables['WaterPort_R_ch_in'] = EventName.Port2In
        variables['WaterPort_R_PWM'] = OutputChannel.PWM2
        variables['ScanimageROIisActive_ch_in'] = EventName.Wire2Low
        variables['ResponseEligibilityChannel'] =  OutputChannel.Wire3 # wire
        variables['ResetTrial_ch_out'] =  OutputChannel.PWM8
        variables['MotorInRewardZone'] =  EventName.Port8Out
        variables['CameraTriggerOut'] = OutputChannel.Wire1
        variables['StepZaberForwardManually_ch_out'] =  OutputChannel.Wire2
        variables['BitCode_ch_out'] =  OutputChannel.BNC1
        variables['Scanimage_trial_start_ch_out'] =  OutputChannel.BNC2
        variables['WhiteNoise_ch'] = OutputChannel.PWM3
        variables['RewardZoneCue_ch'] = OutputChannel.PWM6
        variables['UDP_IP_bpod'] = '10.123.1.32'
        variables['UDP_PORT_bpod'] = 1001
        variables['Bias_ip'] = '10.123.1.87'
        variables['Bias_port_base'] = 5010
        variables['Bias_port_stride'] = 10
        variables['Bias_expected_camera_num'] = 2
        variables['Bias_config_dir'] = r'F:\Marton\BIAS_config'
        variables['Bias_movie_dir'] = r'F:\Marton\Videos'
        variables['Bias_camera_names'] = ['side','bottom']
        variables['BCI_zaber_subjects_dir'] = r'C:\Users\bpod\Documents\BCI_Zaber_data\subjects'
variables_setup = variables.copy()

BCI_zaber_subject_dir = os.path.join(variables['BCI_zaber_subjects_dir'],subject_name)

with open(setupfile, 'w') as outfile:
    json.dump(variables_setup, outfile, indent=4)
with open(subjectfile, 'w') as outfile:
    json.dump(variables_subject, outfile, indent=4)
print('json files (re)generated')


variables = variables_subject.copy()
variables.update(variables_setup)
print('Variables:', variables)

bias_parameters = {'ip' :  variables['Bias_ip'],
                   'port_base':variables['Bias_port_base'],
                   'port_stride':variables['Bias_port_stride'],
                   'expected_camera_num':variables['Bias_expected_camera_num']}
if variables['RecordMovies']:
    camera_list_temp = bias_get_camera_list(bias_parameters)
    camera_list = list()
    for camera_dict, camera_name in zip(camera_list_temp,variables['Bias_camera_names']):
        camera_dict['camera_name'] = camera_name
        camera_list.append(camera_dict)
    print('Cameras found: {}'.format(camera_list))
    bias_stop_movie(camera_list)
    try:
        for camera_dict in camera_list:
            filename = '{}_{}.json'.format(subject_name,camera_dict['camera_name'])
            command = '?load-configuration={}'.format(os.path.join(variables['Bias_config_dir'],filename))
            bias_send_command(camera_dict,command)
##
    except:
        print('camera configuration could not be loaded')
        

# stop UDP server if already running
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
sock.sendto(b'stoptheudpserver', (variables['UDP_IP_bpod'], variables['UDP_PORT_bpod']))
sock.close()
# start listening to UDP port for scanimage
listen_UDP = threading.Thread(target=rec_UDP,args = [ variables['UDP_IP_bpod'],variables['UDP_PORT_bpod']])
listen_UDP.start()

# ===============  Session start ====================
# For each block
   
# ------ For each trial ------
triali = 0
while triali<2000: # unlimiter number of trials
    
    # Update variables if variables changed in json file DURING RUNNING (from behavior_online_analysis GUI)
    with open(subjectfile) as json_file:
        variables_subject_new = json.load(json_file)
    with open(setupfile) as json_file:
        variables_setup_new = json.load(json_file)
    if variables_setup_new != variables_setup or variables_subject_new != variables_subject:
        # Update effective `variables` ( = subject + setup)
        variables = variables_subject_new.copy()
        variables.update(variables_setup_new)
        # Cache the old values for future variable updates
        variables_setup = variables_setup_new.copy() 
        variables_subject = variables_subject_new.copy()
        print('Variables updated:',variables)  # Print to csv after each parameter update
    #%
    try: # calculate return time of the zaber motor
        zaber_cfg_file = np.sort(os.listdir(BCI_zaber_subject_dir))[-1]
        with open(os.path.join(BCI_zaber_subject_dir,zaber_cfg_file)) as json_file:
            variables_BCI_zaber = json.load(json_file)
        s = variables_BCI_zaber['zaber']['limit_far'] - variables_BCI_zaber['zaber']['limit_close']
        v = variables_BCI_zaber['zaber']['speed']
        a = variables_BCI_zaber['zaber']['acceleration']
        zaber_home_travel_time = calculate_step_time(s,v,a)
       # print('zaber home travel time:{}'.format(zaber_home_travel_time))
    except:
        zaber_home_travel_time = 0.4
    #%
    
    #%   
    triali += 1  # First trial number = 1; 
    print('Trialnumber:', triali)
    #%%
    # ------- Start of a trial ---------
    sma = StateMachine(my_bpod)
    sma.set_global_timer(timer_id=3, 
                         timer_duration=90,  # taken from Kayvon's script
                         on_set_delay=0, 
                         channel=variables['Scanimage_trial_start_ch_out'],
                         on_message=255,
                         off_message=0,
                         loop_mode=0,
                         send_events=1)
    sma.set_global_timer(timer_id=1, 
                         timer_duration=1/(2*variables['CameraFrameRate']), 
                         on_set_delay=0, 
                         channel=variables['CameraTriggerOut'],
                         on_message=255,
                         off_message=0,
                         loop_mode=1,
                         send_events=0, # otherwise pybpod crashes
                         loop_intervals=1/(2*variables['CameraFrameRate']))
    if variables['BaselineZaberForwardStepFrequency'] >0:
        sma.set_global_timer(timer_id=2, 
                        timer_duration=1/(2*variables['BaselineZaberForwardStepFrequency']), 
                        on_set_delay=0, 
                        channel=variables['StepZaberForwardManually_ch_out'],
                        on_message=255,
                        off_message=0,
                        loop_mode=1,
                        send_events=1, # otherwise pybpod crashes
                        loop_intervals=1/(2*variables['BaselineZaberForwardStepFrequency']))
    else:
        sma.set_global_timer(timer_id=2, 
                        timer_duration=0, 
                        on_set_delay=0, 
                        on_message=0,
                        off_message=0,
                        loop_mode=0,
                        send_events=0)
        
    # trigger scanimage and wavesurfer
    sma.add_state(
        state_name='Trigger-Scanimage',
        state_timer=0.05,
        state_change_conditions={EventName.Tup: 'Start'},
        output_actions = [('GlobalTimerTrig', 3)])
    

    # ---- 1. Delay period ----
    if variables['LowActivityTime']>0 and variables['LowActivityCheckAtTheBeginning']:
        # Lick before timeup of the delay timer ('baselinetime_now') --> Reset the delay timer
        sma.add_state(
            state_name='Start',
            state_timer=variables['LowActivityTime'],
            state_change_conditions={variables['ScanimageROIisActive_ch_in']: 'BackToBaseline',EventName.Tup: 'GoCueRetractLickport'},
            output_actions = [('GlobalTimerTrig', 1)])
        sma.add_state(
            state_name='StartWithPunishment',
            state_timer=variables['LowActivityTime'],
            state_change_conditions={variables['ScanimageROIisActive_ch_in']: 'BackToBaseline',EventName.Tup: 'GoCueRetractLickport'},
            output_actions = [])#(variables['WhiteNoise_ch'],255)
        
        # Add 2 second timeout (during which more early licks will be ignored), then restart the trial
        sma.add_state(
        	state_name='BackToBaseline',
        	state_timer=0,
        	state_change_conditions={EventName.Tup: 'StartWithPunishment'},
        	output_actions = [])

    else:
        sma.add_state(
            state_name='Start',
            state_timer=0.01,
            state_change_conditions={EventName.Tup: 'GoCueRetractLickport'},
            output_actions = [('GlobalTimerTrig', 1)])
        
    sma.add_state(
        	state_name='GoCueRetractLickport',
        	state_timer=zaber_home_travel_time,
        	state_change_conditions={EventName.Tup: 'GoCue'},
        	output_actions = [(variables['ResetTrial_ch_out'],255)])
    
    # autowater comes here!! (for encouragement)
    if variables['AutoWater']:
        sma.add_state(
        	state_name='GoCue',
        	state_timer=0,
        	state_change_conditions={EventName.Tup: 'Auto_Water_R'},
        	output_actions = [])
        sma.add_state(
                	state_name='Auto_Water_R',
                	state_timer=variables['ValveOpenTime_R']*variables['AutoWaterTimeMultiplier'],
                	state_change_conditions={EventName.Tup: 'GoCue_real'},
                	output_actions = [('Valve',variables['WaterPort_R_ch_out'])])    
        
        # In the autowater mode, it is the 'GoCue_real' that tells the mouse to lick
        sma.add_state(
        	state_name='GoCue_real',
        	state_timer=.05,
        	state_change_conditions={EventName.Tup:'Response'},
        	output_actions = [(variables['GoCue_ch'],255),('GlobalTimerTrig', 2)])  
        
        # End of autowater's gocue
        
    else:
        # ------ 2. GoCue (normal) --------
        sma.add_state(
        	state_name='GoCue',
            state_timer=.05,#
        	state_change_conditions={EventName.Tup:'Response'},
        	output_actions = [(variables['GoCue_ch'],255),('GlobalTimerTrig', 2)])
    if variables['SoundOnRewardZoneEntry']:
        sma.add_state(
        	state_name='Response',
        	state_timer=variables['NeuronResponseTime'],
        	state_change_conditions={EventName.Tup: 'End_no_reward',variables['MotorInRewardZone']:'RewardZoneCue'},
        	output_actions = [(variables['ResponseEligibilityChannel'],255)])
        sma.add_state(
            state_name='RewardZoneCue',
        	state_timer=.05,
        	state_change_conditions={EventName.Tup: 'ResponseInRewardZone'},
        	output_actions = [(variables['ResponseEligibilityChannel'],255),(variables['RewardZoneCue_ch'],255)])
    else:
        sma.add_state(
        	state_name='Response',
        	state_timer=variables['NeuronResponseTime'],
        	state_change_conditions={EventName.Tup: 'End_no_reward',variables['MotorInRewardZone']:'ResponseInRewardZone'},
        	output_actions = [(variables['ResponseEligibilityChannel'],255)])
    
    sma.add_state(
            state_name = 'ResponseInRewardZone',
            state_timer = variables['LickResponseTime'],
            state_change_conditions={EventName.Tup: 'End_no_reward', variables['WaterPort_L_ch_in']: 'Reward_L',variables['WaterPort_R_ch_in']: 'Reward_R'},
            output_actions=[(variables['ResponseEligibilityChannel'],255)]) 
   
    sma.add_state(
    	state_name='Reward_L',
    	state_timer=variables['ValveOpenTime_L'],
    	state_change_conditions={EventName.Tup: 'Consume_reward'},
    	output_actions = [('Valve',variables['WaterPort_L_ch_out']),('GlobalTimerCancel', 2),(variables['WaterPort_L_PWM'],255)])
    sma.add_state(
    	state_name='Reward_R',
    	state_timer=variables['ValveOpenTime_R'],
    	state_change_conditions={EventName.Tup: 'Consume_reward'},
    	output_actions = [('Valve',variables['WaterPort_R_ch_out']),('GlobalTimerCancel', 2),(variables['WaterPort_R_PWM'],255)])
    # --- 3. Enjoy the water! ---    
    # The mice are free to lick, until no lick in 'Reward_consume_time', which is hard-coded to 1s.
    
    if variables['EnforceStopLicking']:
        sma.add_state(
        	state_name='Consume_reward',
        	state_timer=variables['RewardConsumeTime'],  # time needed without lick to go to the next trial
        	state_change_conditions={variables['WaterPort_L_ch_in']: 'Consume_reward_return',variables['WaterPort_R_ch_in']: 'Consume_reward_return',EventName.Tup: 'End'},
        	output_actions = [])
        sma.add_state(
        	state_name='Consume_reward_return',
        	state_timer=.1,
        	state_change_conditions={EventName.Tup: 'Consume_reward'},
        	output_actions = [])
    else:
        sma.add_state(
        	state_name='Consume_reward',
        	state_timer=variables['RewardConsumeTime'],  # time needed without lick to go to the next trial
        	state_change_conditions={EventName.Tup: 'End'},
        	output_actions = [])
    
    if variables['LowActivityTime']>0 and not variables['LowActivityCheckAtTheBeginning']:
        sma.add_state(
            state_name = 'End',
            state_timer = variables['LowActivityTime'],
            state_change_conditions={variables['ScanimageROIisActive_ch_in']: 'BackToBaseline_end',EventName.Tup: 'End_real'},
            output_actions=[])
            # Add 2 second timeout (during which more early licks will be ignored), then restart the trial
        sma.add_state(
        	state_name='BackToBaseline_end',
        	state_timer=0,
        	state_change_conditions={EventName.Tup: 'End'},
        	output_actions = [])
        sma.add_state(
            state_name = 'End_real',
            state_timer = .001,
            state_change_conditions={EventName.Tup: 'BitCharStart0'},
            output_actions=[('GlobalTimerCancel', 1)])
    else:
        sma.add_state(
                state_name = 'End',
                state_timer = .001,
                state_change_conditions={EventName.Tup: 'BitCharStart0'},
                output_actions=[('GlobalTimerCancel', 1)])
        
    sma.add_state(
            state_name = 'End_no_reward',
            state_timer = .001,
            state_change_conditions={EventName.Tup: 'BitCharStart0'},
            output_actions=[('GlobalTimerCancel', 1)])
    
    
    #% generate bit code - a la Kayvon
    binary_length = 11
    trial_bin_str = str(bin(triali))[2:]
    trial_bin_str = trial_bin_str.zfill(binary_length)
    for i,bit_char in enumerate(trial_bin_str):
        bit_val = int(bit_char)
        if i < binary_length-1:
            next_state = 'BitCharStart{}'.format(i+1)
        else:
            next_state = 'exit'
        
        sma.add_state(
        	state_name='BitCharStart{}'.format(i),
        	state_timer=0.002,
        	state_change_conditions={EventName.Tup: 'BitCharNulla{}'.format(i)},
        	output_actions = [(variables['BitCode_ch_out'],1)])
        sma.add_state(
        	state_name='BitCharNulla{}'.format(i),
        	state_timer=0.02,
        	state_change_conditions={EventName.Tup: 'BitChar{}'.format(i)},
        	output_actions = [(variables['BitCode_ch_out'],0)])
        sma.add_state(
        	state_name='BitChar{}'.format(i),
        	state_timer=0.02,
        	state_change_conditions={EventName.Tup: 'BitCharNullb{}'.format(i)},
        	output_actions = [(variables['BitCode_ch_out'],bit_val)])
        sma.add_state(
        	state_name='BitCharNullb{}'.format(i),
        	state_timer=0.02,
        	state_change_conditions={EventName.Tup: 'BitCharEnd{}'.format(i)},
        	output_actions = [(variables['BitCode_ch_out'],0)])
        sma.add_state(
        	state_name='BitCharEnd{}'.format(i),
        	state_timer=0.002,
        	state_change_conditions={EventName.Tup: 'BitCharSpacer{}'.format(i)},
        	output_actions = [(variables['BitCode_ch_out'],1)])
        sma.add_state(
        	state_name='BitCharSpacer{}'.format(i),
        	state_timer=0.002,
        	state_change_conditions={EventName.Tup: next_state},
        	output_actions = [(variables['BitCode_ch_out'],0)])
    
    
    
    
    my_bpod.send_state_machine(sma)  # Send state machine description to Bpod device
    
    
    if variables['RecordMovies']:
        bias_start_movie(camera_list,variables['Bias_movie_dir'],subject_name,session_name,triali)
        
        
    ispybpodrunning = my_bpod.run_state_machine(sma)  # Run state machine
    
    if variables['RecordMovies']:        
        movie_names = bias_get_movie_names(camera_list)
        print('Movie names for trial: {}'.format(movie_names))
    if len(messagelist)>0:
        print('scanimage file: {}'.format(messagelist.pop()))
        for message in messagelist:
            print('additional older scanimage messages: {}'.format(message))
        messagelist = []
    else:
        print('no message from scanimage')
    print('ITI start')
    
    if variables['RecordMovies']:
        bias_stop_movie(camera_list)
        
    
    if not ispybpodrunning:
        print('pybpod protocol stopped')
        break
    time.sleep(variables['ITI'])
    print('ITI end')
    # ----------- End of state machine ------------
    
    # -------- Handle reward baiting, print log messages, etc. ---------
    # Check if the mouse got a reward in this trial
# =============================================================================
#     trialdata = my_bpod.session.current_trial.export()
#     reward_L_consumed = not np.isnan(trialdata['States timestamps']['Reward_L'][0][0])
#     reward_R_consumed = not np.isnan(trialdata['States timestamps']['Reward_R'][0][0])
#     reward_M_consumed = not np.isnan(trialdata['States timestamps']['Reward_M'][0][0])
#     L_chosen = not np.isnan(trialdata['States timestamps']['Choice_L'][0][0])
#     R_chosen = not np.isnan(trialdata['States timestamps']['Choice_R'][0][0])
#     M_chosen = not np.isnan(trialdata['States timestamps']['Choice_M'][0][0])
# =============================================================================
if variables['RecordMovies']:
    bias_stop_movie(camera_list)
    for camera_dict in camera_list:
        filename = os.path.join(variables['Bias_movie_dir'],subject_name,camera_dict['camera_name'],session_name,'camera_config.json')
        #filename = r'C:\Users\labadmin\Documents\temp.json'
        command = r'?save-configuration={}'.format(filename)
        response = bias_send_command(camera_dict,command)  
        
# =============================================================================
#         command = r'?get-configuration'
#         response = bias_send_command(camera_dict,command) 
#         config = response['value']
#         #config['']
#         #config['camera']['triggerType'] = 'Internal'
#         command = '?set-configuration={}'.format(config)
#         print(command)
#         response = bias_send_command(camera_dict,command) 
#         print(response)
# =============================================================================
# =============================================================================
#         command = '?disable-logging'
#         r = bias_send_command(camera_dict,command)
#         command = '?start-capture'
#         r = bias_send_command(camera_dict,command)
# =============================================================================
   # stop udp server 
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
sock.sendto(b'stoptheudpserver', (variables['UDP_IP_bpod'], variables['UDP_PORT_bpod']))
sock.close()
  
my_bpod.close()