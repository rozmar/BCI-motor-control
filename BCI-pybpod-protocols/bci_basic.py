from pybpodapi.bpod import Bpod
from pybpodapi.state_machine import StateMachine
from pybpodapi.bpod.hardware.events import EventName
from pybpodapi.bpod.hardware.output_channels import OutputChannel
from pybpodapi.com.messaging.trial import Trial
from datetime import datetime
from itertools import permutations
#import zaber.serial as zaber_serial
import time
import json
import numpy as np

import os, sys 

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

# soft codes : 1 - retract RC motor; 2 - protract RC motor

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
            'ResponseTime':30,# time for the mouse to modulate its neuronal activity
            'RewardConsumeTime':2
            }
print(variables)
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
        variables['WaterPort_R_ch_out'] = 2
        variables['WaterPort_R_ch_in'] = EventName.Port2In
        variables['ScanimageROIisActive_ch_in'] = EventName.Wire2Low
        variables['ResponseEligibilityChannel'] =  OutputChannel.Wire3 # wire
        variables['ResetTrial_ch_out'] =  OutputChannel.PWM8
        variables['MotorInRewardZone'] =  EventName.Port8Out

variables_setup = variables.copy()

with open(setupfile, 'w') as outfile:
    json.dump(variables_setup, outfile)
with open(subjectfile, 'w') as outfile:
    json.dump(variables_subject, outfile)
print('json files (re)generated')


variables = variables_subject.copy()
variables.update(variables_setup)
print('Variables:', variables)


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
    
    triali += 1  # First trial number = 1; 
    
    # ------- Start of a trial ---------
    sma = StateMachine(my_bpod)
    
    # ---- 1. Delay period ----
    if variables['LowActivityTime']>0:
        # Lick before timeup of the delay timer ('baselinetime_now') --> Reset the delay timer
        sma.add_state(
            state_name='Start',
            state_timer=variables['LowActivityTime'],
            state_change_conditions={variables['ScanimageROIisActive_ch_in']: 'BackToBaseline',EventName.Tup: 'GoCue'},
            output_actions = [(variables['ResetTrial_ch_out'],255)])
        
        # Add 2 second timeout (during which more early licks will be ignored), then restart the trial
        sma.add_state(
        	state_name='BackToBaseline',
        	state_timer=0,
        	state_change_conditions={EventName.Tup: 'Start'},
        	output_actions = [])

    else:
        sma.add_state(
            state_name='Start',
            state_timer=0.05,
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
        	output_actions = [(variables['GoCue_ch'],255)])  
        
        # End of autowater's gocue
        
    else:
        # ------ 2. GoCue (normal) --------
        sma.add_state(
        	state_name='GoCue',
            state_timer=.05,#
        	state_change_conditions={EventName.Tup:'Response'},
        	output_actions = [(variables['GoCue_ch'],255)])
    
    sma.add_state(
        	state_name='Response',
        	state_timer=variables['ResponseTime'],
        	state_change_conditions={EventName.Tup: 'End',variables['MotorInRewardZone']:'ResponseInRewardZone'},
        	output_actions = [(variables['ResponseEligibilityChannel'],255)])
    
    sma.add_state(
            state_name = 'ResponseInRewardZone',
            state_timer = variables['ResponseTime'],
            state_change_conditions={EventName.Tup: 'End', variables['WaterPort_L_ch_in']: 'Reward_L',variables['WaterPort_R_ch_in']: 'Reward_R'},
            output_actions=[(variables['ResponseEligibilityChannel'],255)]) 
   
    sma.add_state(
    	state_name='Reward_L',
    	state_timer=variables['ValveOpenTime_L'],
    	state_change_conditions={EventName.Tup: 'Consume_reward'},
    	output_actions = [('Valve',variables['WaterPort_L_ch_out'])])
    sma.add_state(
    	state_name='Reward_R',
    	state_timer=variables['ValveOpenTime_R'],
    	state_change_conditions={EventName.Tup: 'Consume_reward'},
    	output_actions = [('Valve',variables['WaterPort_R_ch_out'])])
    # --- 3. Enjoy the water! ---    
    # The mice are free to lick, until no lick in 'Reward_consume_time', which is hard-coded to 1s.
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
    
    
    sma.add_state(
            state_name = 'End',
            state_timer = 0,
            state_change_conditions={EventName.Tup: 'exit'},
            output_actions=[])

    my_bpod.send_state_machine(sma)  # Send state machine description to Bpod device

    my_bpod.run_state_machine(sma)  # Run state machine
    print('Trialnumber:', triali + 1)
    print('ITI start')
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
    

    
    
    
my_bpod.close()