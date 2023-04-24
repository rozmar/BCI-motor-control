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
#%%


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
subjectfile = os.path.join(subjectdir,'variables_pavlovian.json')
if os.path.exists(subjectfile):
    with open(subjectfile) as json_file:
        variables = json.load(json_file)
    print('subject variables loaded from Json file')
else:
    variables = { # Delayed
            'ValveOpenTime_L' : .02,
            'ValveOpenTime_R' : .0,
            'ITI' : 5., #s - exponential
            'ITI_min':1.5,
            'ITI_max':5.5,
            'RewardOmissionRatio':0., # proportion of trials without reward
            'CueOmissionRatio':.1, # proportion of trials without go cue
            'PreGoCueTime':1., #at the start of the trial before GO cue
            'TimeToReward':1.5,
            'GoCueLength':.2,#seconds
            'RewardConsumeTime':2.,
            'RecordMovies':False,
            'CameraFrameRate' : 400,
            'EnforceStopLicking':True,
            'WaitRewardCollection':True, # doesn't start ITI until reward is consumed
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
        variables['GoCue_ch'] = OutputChannel.PWM3
        variables['NoGoCue_ch'] = OutputChannel.PWM4
        variables['WaterPort_L_ch_out'] = 1
        variables['WaterPort_L_ch_in'] = EventName.Port1In
        variables['WaterPort_L_PWM'] = OutputChannel.PWM1
        variables['CameraTriggerOut'] = OutputChannel.Wire1
        variables['BitCode_ch_out'] =  OutputChannel.BNC1
        variables['Scanimage_trial_start_ch_out'] =  OutputChannel.BNC2
        variables['UDP_IP_bpod'] = '10.128.54.244'
        variables['UDP_PORT_bpod'] = 1001
        variables['Bias_ip'] = '10.128.54.109'
        variables['Bias_port_base'] = 5010
        variables['Bias_port_stride'] = 10
        variables['Bias_expected_camera_num'] = 2
        variables['Bias_config_dir'] = r'D:\BIAS_config'
        variables['Bias_movie_dir'] = r'D:\videos'
        variables['Bias_camera_names'] = ['side','bottom']
        variables['BCI_zaber_subjects_dir'] = r'C:\Users\bpod\Documents\BCI_Zaber_data\subjects'
        
        
variables_setup = variables.copy()

trigger_photostim = False
photostim_delay_bounds = [6,10]


BCI_zaber_subject_dir = os.path.join(variables['BCI_zaber_subjects_dir'],subject_name)

with open(setupfile, 'w') as outfile:
    json.dump(variables_setup, outfile, indent=4)
with open(subjectfile, 'w') as outfile:
    json.dump(variables_subject, outfile, indent=4)
print('json files (re)generated')


variables = variables_subject.copy()
variables.update(variables_setup)
print('Variables:', variables)

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
while triali<2000: # unlimited number of trials
    trial_rand_val = np.random.uniform()
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
    triali += 1  # First trial number = 1; 
    print('Trialnumber:', triali)
    ITI_now = np.random.exponential(variables['ITI'])
    
    
    if ITI_now<variables['ITI_min']:
        ITI_now = variables['ITI_min']
    elif ITI_now>variables['ITI_max']:
        ITI_now = variables['ITI_max']
    print('ITI start')
    print('{} seconds ITI'.format(np.round(ITI_now,3)))
    #time.sleep(ITI_now)
    print('ITI end')
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
        
    # trigger scanimage and wavesurfer
    sma.add_state(
        state_name='Trigger-Scanimage',
        state_timer=0.05,
        state_change_conditions={EventName.Tup: 'Start'},
        output_actions = [('GlobalTimerTrig', 3)])
    

    # ---- 1. Delay period ----
    if trial_rand_val< variables['CueOmissionRatio']:
        gocuestatename = 'GoCueOmission'
        print('Cue omission trial')
    else:
        gocuestatename = 'GoCue'
    if variables['EnforceStopLicking']:
        # Lick before timeup of the delay timer ('baselinetime_now') --> Reset the delay timer
        sma.add_state(
            state_name='Start',
            state_timer=variables['PreGoCueTime'],
            state_change_conditions={variables['WaterPort_L_ch_in']: 'BackToBaseline',EventName.Tup: gocuestatename},
            output_actions = [('GlobalTimerTrig', 1)])
        sma.add_state(
            state_name='StartWithPunishment',
            state_timer=variables['PreGoCueTime'],
            state_change_conditions={variables['WaterPort_L_ch_in']: 'BackToBaseline',EventName.Tup: gocuestatename},
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
            state_timer=variables['PreGoCueTime'],
            state_change_conditions={EventName.Tup: gocuestatename},
            output_actions = [('GlobalTimerTrig', 1)])
    sma.add_state(
           	state_name='GoCueOmission',
               state_timer=variables['GoCueLength'],
           	state_change_conditions={EventName.Tup:'Wait'},
           	output_actions = [])
    sma.add_state(
            	state_name='GoCue',
                state_timer=variables['GoCueLength'],
            	state_change_conditions={EventName.Tup:'Wait'},
            	output_actions = [(variables['GoCue_ch'],255)])
 
    
    
    if trial_rand_val>=variables['CueOmissionRatio'] and trial_rand_val<variables['RewardOmissionRatio']+variables['CueOmissionRatio']:
        sma.add_state(
        	state_name='Wait',
        	state_timer=variables['TimeToReward'],
        	state_change_conditions={EventName.Tup: 'NoReward'},
        	output_actions = [])
        print('Reward omission trial')
    else:
        sma.add_state(
        	state_name='Wait',
        	state_timer=variables['TimeToReward'],
        	state_change_conditions={EventName.Tup: 'Reward_L'},
        	output_actions = [])
 ############ NO REWARD comes here
    
        
    sma.add_state(
    	state_name='NoReward',
    	state_timer=variables['ValveOpenTime_L'],
    	state_change_conditions={EventName.Tup: 'Consume_reward'}, # should consume reward be skipped here??
    	output_actions = [])
    
    if variables['WaitRewardCollection']:
        postrewardstate = 'WaitForRewardCollection'
    else:
        postrewardstate = 'Consume_reward'
        
    sma.add_state(
    	state_name='Reward_L',
    	state_timer=variables['ValveOpenTime_L'],
    	state_change_conditions={EventName.Tup:postrewardstate},
       	output_actions = [('Valve',variables['WaterPort_L_ch_out'])])
    
    
    sma.add_state(
    	state_name='WaitForRewardCollection',
    	state_timer=10,
    	state_change_conditions={variables['WaterPort_L_ch_in']: 'Consume_reward'},
       	output_actions = [])
    

    sma.add_state(
    	state_name='Consume_reward',
    	state_timer=variables['RewardConsumeTime']+ITI_now,
    	state_change_conditions={EventName.Tup: 'End'},
    	output_actions = [])
    sma.add_state(
            state_name = 'End',
            state_timer = .001,
            state_change_conditions={EventName.Tup:  'exit'},
            output_actions=[('GlobalTimerCancel', 1)])
        

    
    my_bpod.send_state_machine(sma)  # Send state machine description to Bpod device
    
    ispybpodrunning = my_bpod.run_state_machine(sma)  # Run state machine
    
    if variables['RecordMovies'] and len(messagelist)>0:
        print('Movie names for trial: {}'.format(messagelist))
        messagelist = []
    else:
        print('no movies recorded')
    
    if not ispybpodrunning:
        print('pybpod protocol stopped')
        break
    time.sleep(0.5)#500ms delay between trials for 
  
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
sock.sendto(b'stoptheudpserver', (variables['UDP_IP_bpod'], variables['UDP_PORT_bpod']))
sock.close()
  
my_bpod.close()