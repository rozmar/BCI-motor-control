import sys
import os
import subprocess
import serial.tools.list_ports
from zaber.serial import AsciiSerial,AsciiCommand
import logging 
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton,  QLineEdit, QCheckBox, QHBoxLayout, QGroupBox, QDialog, QVBoxLayout, QGridLayout, QComboBox, QSizePolicy, qApp, QLabel,QPlainTextEdit
from PyQt5.QtGui import QIcon

from PyQt5.QtCore import pyqtSlot, QTimer, Qt

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import pathlib
import numpy as np
import datetime
import json
from pathlib import Path
#from scipy import stats
import utils_pybpod
import threading
try:
    import zaber.serial as zaber_serial
except:
    pass
#%%
extra_time_for_each_step = .001 #s
defpath = r'C:\Users\bpod\Documents\Pybpod'
def find_ports(manufacturer):
    #
    usb_devices = serial.tools.list_ports.comports()
    usb_device_names = list()
    for usb_device in usb_devices:
        try:
            if manufacturer.lower() in usb_device.manufacturer.lower():
                usb_device_names.append(usb_device.device)
                #print('usb_device.product.lower()')
                try:
                    if 'arduino' in manufacturer.lower() and 'prog' not in usb_device.product.lower():#usb_device.product.lower():
                        ddel = usb_device_names.pop() # linux version
                except:
                    if 'arduino' in manufacturer.lower() and 'prog' not in usb_device.description.lower():#usb_device.product.lower():
                        ddel = usb_device_names.pop() # windows version
        except:
            pass
        #
    return usb_device_names
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
def calculate_step_size_for_max_speed(v,a,max_speed):
    #a : accelerateio in mm/s**2
    #v : max travelling speed in mm/s
    #max_speed : desired max average speed in mm/s
    s = 0
    speed = 0
    while speed<max_speed:
        s+=.001
        t=calculate_step_time(s,v,a)+extra_time_for_each_step# adding plus 1 ms to make sure the step is complete
        speed = s/t
    return s
#%%
# =============================================================================
# def loaddirstucture(projectdir = Path(defpath),projectnames_needed = None, experimentnames_needed = None,  setupnames_needed=None):
#     dirstructure = dict()
#     projectnames = list()
#     experimentnames = list()
#     setupnames = list()
#     sessionnames = list()
#     subjectnames = list()
#     if type(projectdir) != type(Path()):
#         projectdir = Path(projectdir)
#     for projectname in projectdir.iterdir():
#         if projectname.is_dir() and (not projectnames_needed or projectname.name in projectnames_needed):
#             dirstructure[projectname.name] = dict()
#             projectnames.append(projectname.name)
#             
#             for subjectname in (projectname / 'subjects').iterdir():
#                 if subjectname.is_dir() : 
#                     subjectnames.append(subjectname.name)            
#             
#             for experimentname in (projectname / 'experiments').iterdir():
#                 if experimentname.is_dir() and (not experimentnames_needed or experimentname.name in experimentnames_needed ): 
#                     dirstructure[projectname.name][experimentname.name] = dict()
#                     experimentnames.append(experimentname.name)
#                     
#                     for setupname in (experimentname / 'setups').iterdir():
#                         if setupname.is_dir() and (not setupnames_needed or setupname.name in setupnames_needed ): 
#                             setupnames.append(setupname.name)
#                             dirstructure[projectname.name][experimentname.name][setupname.name] = list()
#                             
#                             for sessionname in (setupname / 'sessions').iterdir():
#                                 if sessionname.is_dir(): 
#                                     sessionnames.append(sessionname.name)
#                                     dirstructure[projectname.name][experimentname.name][setupname.name].append(sessionname.name)
#     return dirstructure, projectnames, experimentnames, setupnames, sessionnames, subjectnames  
# =============================================================================
class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)
        
class App(QDialog):
    def __init__(self):
        super().__init__()
        print('started')
        self.dirs = dict()
        self.handles = dict()
        self.title = 'BCI control - Zaber and Arduino'
        self.left = 20 # 10
        self.top = 30 # 10
        self.width = 1400 # 1024
        self.height = 900  # 768
        #self.microstep_size = 0.09525 # microns per step
        
        zaber_properties = {'trigger_step_size':100,
                            'max_speed':3,
                            'reward_zone':10}
        arduino_properties = {'analog_pin':0,
                              'trialStartedPin':12,
                              'activityToBpodPin':8,
                              'digital_out_forward_pin':9,
                              'digital_out_pulse_width':1, #ms
                              'function_forward':'interval = 10000/val',
                              'exec_file_location': r'C:\Program Files (x86)\Arduino\arduino.exe',
                              'min_value_to_move':10}
        self.properties = {'zaber':zaber_properties,
                           'arduino':arduino_properties,
                           'bpod':None}
        self.zaber_port = None
        self.zaber_max_limit = 310000
        self.zaber_min_limit = 0
        self.base_dir = r'C:\Users\bpod\Documents\BCI_Zaber_data'
        self.pybpod_dir = r'C:\Users\bpod\Documents\Pybpod'
        self.bpod_loaddirectorystructure()
        self.initUI()
        
        self.timer  = QTimer(self)
        self.timer.setInterval(1000)          # Throw event timeout with an interval of 1000 milliseconds
        self.timer.timeout.connect(self.updatelocation) # each time timer counts a second, call self.blink
        
        self.timer_bpod  = QTimer(self)
        self.timer_bpod.setInterval(5000)          # Throw event timeout with an interval of 1000 milliseconds
        self.timer_bpod.timeout.connect(self.updatebpodplot) # each time timer counts a second, call self.blink
        
        self.pickle_write_thread = None
        
        self.updateZaberUI()
        self.updateArduinoUI()
        self.bpod_updateUI('filter_project')
        self.pybpod_variables_to_display = ['ValveOpenTime_L',
                                            'ValveOpenTime_R',
                                            'AutoWater',
                                            'ITI' ,
                                            'LowActivityTime',
                                            'AutoWaterTimeMultiplier',
                                            'NeuronResponseTime',
                                            'LickResponseTime',
                                            'RewardConsumeTime',
                                            'BaselineZaberForwardStepFrequency',
                                            'RecordMovies',
                                            'CameraFrameRate',
                                            'LowActivityCheckAtTheBeginning']
        self.update_subject()

        ############################################################# BPOD START ##################################################################################
    @pyqtSlot()
    def autoupdatebpodplot(self):
        self.updatebpodplot()
        
    def updatebpodplot(self):
        
        qApp.processEvents()
        project_now = [self.handles['bpod_filter_project'].currentText()]
        experiment_now = [self.handles['bpod_filter_experiment'].currentText()]
        setup_now =[self.handles['bpod_filter_setup'].currentText()]
        subject_now = self.handles['subject_select'].currentText()
        
        
        if self.pickle_write_thread == None or not self.pickle_write_thread.isAlive():
            self.pickle_write_thread = threading.Thread(target=utils_pybpod.generate_pickles_from_csv, 
                                                        args=(self.pybpod_dir, 
                                                              project_now, 
                                                              experiment_now, 
                                                              setup_now, 
                                                              True))   # Only cache recent 5 days
            
            self.pickle_write_thread.daemon = True                            # Daemonize thread
            self.pickle_write_thread.start() 
            
            try:
                self.data = utils_pybpod.load_pickles_for_online_analysis(projectdir = self.pybpod_dir,
                                                        projectnames_needed = project_now,
                                                        experimentnames_needed = experiment_now,
                                                        setupnames_needed = setup_now,
                                                        subjectnames_needed = subject_now,
                                                        # load_only_last_day = False)   # Load all data
                                                        load_only_last_day = True)  # Only load recent 5 days
            except:
                pass
            try:
                self.handles['ax_bpod_results'].update_bpod_plot(self.data) 
            except:
                pass

            
                
        
        
        
        
        
        
    def bpod_updateUI(self, lastselected):
        project_now = [self.handles['bpod_filter_project'].currentText()]
        experiment_now = [self.handles['bpod_filter_experiment'].currentText()]
        setup_now =[self.handles['bpod_filter_setup'].currentText()]
        #session_now = self.handles['filter_session'].currentText()
        if project_now[0] == '?':
            project_now = None
        if experiment_now[0] == '?':
            experiment_now = None
        if setup_now[0] == '?':
            setup_now = None
        self.bpod_loaddirectorystructure(project_now, experiment_now,  setup_now)
        if lastselected == 'filter_project':
            self.handles['bpod_filter_experiment'].currentIndexChanged.disconnect()
            self.handles['bpod_filter_experiment'].clear()
            #self.handles['bpod_filter_experiment'].addItem('all experiments')
            self.handles['bpod_filter_experiment'].addItems(self.bpod_alldirs['experimentnames'])
            self.handles['bpod_filter_experiment'].currentIndexChanged.connect(lambda: self.bpod_updateUI('filter_experiment'))
            
            self.handles['subject_select'].currentIndexChanged.disconnect()
            self.handles['subject_select'].clear()
            #self.handles['subject_select'].addItem('all subjects')
            self.handles['subject_select'].addItems(self.bpod_alldirs['subjectnames'])
            self.handles['subject_select'].currentIndexChanged.connect(lambda: self.update_subject())#currentIndexChanged.connect(lambda: self.bpod_updateUI('filter_subject'))
              
        if lastselected == 'filter_project' or lastselected == 'filter_experiment':
            self.handles['bpod_filter_setup'].currentIndexChanged.disconnect()
            self.handles['bpod_filter_setup'].clear()
            #self.handles['bpod_filter_setup'].addItem('all setups')
            self.handles['bpod_filter_setup'].addItems(self.bpod_alldirs['setupnames'])
            self.handles['bpod_filter_setup'].currentIndexChanged.connect(lambda: self.bpod_updateUI('filter_setup'))        
        
        
    def bpod_load_parameters(self):
        maxcol = 4 # number of columns
        project_now = self.handles['bpod_filter_project'].currentText()
        experiment_now = self.handles['bpod_filter_experiment'].currentText()
        setup_now = self.handles['bpod_filter_setup'].currentText()
        subject_now = self.handles['subject_select'].currentText()
        if project_now != '?' and experiment_now != '?' and setup_now != '?' and subject_now != '?':
            subject_var_file = os.path.join(self.pybpod_dir,project_now,'subjects',subject_now,'variables.json')
            setup_var_file = os.path.join(self.pybpod_dir,project_now,'experiments',experiment_now,'setups',setup_now,'variables.json')
            with open(subject_var_file) as json_file:
                variables_subject = json.load(json_file)
            with open(setup_var_file) as json_file:
                variables_setup = json.load(json_file)
                
            if self.properties['bpod'] is None:
                
                layout = QGridLayout()
                self.horizontalGroupBox_bpod_variables_setup = QGroupBox("Setup: "+setup_now)
                self.horizontalGroupBox_bpod_variables_subject = QGroupBox("Subject: "+subject_now)
                layout.addWidget(self.horizontalGroupBox_bpod_variables_setup ,0,0)
                layout.addWidget(self.horizontalGroupBox_bpod_variables_subject ,1,0)
                self.horizontalGroupBox_bpod_variables.setLayout(layout)
                
                self.handles['bpod_variables_subject']=dict()
                self.handles['bpod_variables_subject']=dict()
                
                layout_setup = QGridLayout()
                row = 0
                col = -1
                self.handles['bpod_variables_setup']=dict()
                self.handles['bpod_variables_subject']=dict()
                for idx,key in enumerate(variables_setup.keys()):
                    if key in self.pybpod_variables_to_display:
                        col +=1
                        if col > maxcol*2:
                            col = 0
                            row += 1
                        layout_setup.addWidget(QLabel(key+':') ,row,col)
                        col +=1
                        self.handles['bpod_variables_setup'][key] =  QLineEdit(str(variables_setup[key]))
                        self.handles['bpod_variables_setup'][key].returnPressed.connect(self.bpod_save_parameters)
                        self.handles['bpod_variables_setup'][key].textChanged.connect(self.bpod_check_parameters)
                        layout_setup.addWidget(self.handles['bpod_variables_setup'][key] ,row,col)
                self.horizontalGroupBox_bpod_variables_setup.setLayout(layout_setup)
                
                
                layout_subject = QGridLayout()
                row = 0
                col = -1
                for idx,key in enumerate(variables_subject.keys()):   # Read all variables in json file
                    if key in self.pybpod_variables_to_display:   # But only show part of them
                        col +=1
                        if col > maxcol*2:
                            col = 0
                            row += 1
                        layout_subject.addWidget(QLabel(key+':') ,row,col)
                        col +=1
                        self.handles['bpod_variables_subject'][key] =  QLineEdit(str(variables_subject[key]))
                        self.handles['bpod_variables_subject'][key].returnPressed.connect(self.bpod_save_parameters)
                        self.handles['bpod_variables_subject'][key].textChanged.connect(self.bpod_check_parameters)
                        layout_subject.addWidget(self.handles['bpod_variables_subject'][key] ,row,col)
                        
                self.horizontalGroupBox_bpod_variables_subject.setLayout(layout_subject)
                self.properties['bpod']=dict()
            else:
                self.horizontalGroupBox_bpod_variables_subject.setTitle("Subject: "+subject_now)
                self.horizontalGroupBox_bpod_variables_setup.setTitle("Setup: "+setup_now)
                for key in self.handles['bpod_variables_subject'].keys():
                    if key in variables_subject.keys():
                        self.handles['bpod_variables_subject'][key].setText(str(variables_subject[key]))
                    else:  # Just in case there are missing parameters (due to updated parameter tables) 
                        self.handles['bpod_variables_subject'][key].setText("NA")
                        self.handles['bpod_variables_subject'][key].setStyleSheet('QLineEdit {background: grey;}')
                for key in self.handles['bpod_variables_setup'].keys():
                    self.handles['bpod_variables_setup'][key].setText(str(variables_setup[key]))

            self.properties['bpod']['subject'] = variables_subject
            self.properties['bpod']['setup'] = variables_setup
            self.properties['bpod']['subject_file'] = subject_var_file
            self.properties['bpod']['setup_file'] = setup_var_file
            
    def bpod_check_parameters(self):
        project_now = self.handles['bpod_filter_project'].currentText()
        experiment_now = self.handles['bpod_filter_experiment'].currentText()
        setup_now = self.handles['bpod_filter_setup'].currentText()
        subject_now = self.handles['subject_select'].currentText()
        subject_var_file = os.path.join(self.pybpod_dir,project_now,'subjects',subject_now,'variables.json')
        setup_var_file = os.path.join(self.pybpod_dir,project_now,'experiments',experiment_now,'setups',setup_now,'variables.json')
        with open(subject_var_file) as json_file:
            variables_subject = json.load(json_file)
        with open(setup_var_file) as json_file:
            variables_setup = json.load(json_file)
            
        self.properties['bpod']['subject'] = variables_subject
        self.properties['bpod']['setup'] = variables_setup
        for dicttext in ['subject','setup']:
            for key in self.handles['bpod_variables_'+dicttext].keys(): 
                valuenow = None
                
                # Auto formatting
                if key in self.properties['bpod'][dicttext].keys():  # If json file has the parameter in the GUI (backward compatibility). HH20200730
                    if type(self.properties['bpod'][dicttext][key]) == bool:
                        if 'true' in self.handles['bpod_variables_'+dicttext][key].text().lower() or '1' in self.handles['bpod_variables_'+dicttext][key].text():
                            valuenow = True
                        else:
                            valuenow = False
                    elif type(self.properties['bpod'][dicttext][key]) == float:
                        try:
                            valuenow = float(self.handles['bpod_variables_'+dicttext][key].text())
                        except:
                            print('not proper value')
                            valuenow = None
                    elif type(self.properties['bpod'][dicttext][key]) == int:                   
                        try:
                            valuenow = int(round(float(self.handles['bpod_variables_'+dicttext][key].text())))
                        except:
                            print('not proper value')
                            valuenow = None
                            
                    # Turn the newly changed parameters to red            
                    if valuenow == self.properties['bpod'][dicttext][key]:
                        self.handles['bpod_variables_'+dicttext][key].setStyleSheet('QLineEdit {color: black;}')
                    else:
                        self.handles['bpod_variables_'+dicttext][key].setStyleSheet('QLineEdit {color: red;}')
                else:   # If json file has missing parameters (backward compatibility). HH20200730
                    # self.handles['variables_subject'][key].setText("NA")
                    self.handles['bpod_variables_subject'][key].setStyleSheet('QLineEdit {background: grey;}')
                    
                    
        qApp.processEvents()
        
    def bpod_save_parameters(self):
        project_now = self.handles['bpod_filter_project'].currentText()
        experiment_now = self.handles['bpod_filter_experiment'].currentText()
        setup_now = self.handles['bpod_filter_setup'].currentText()
        subject_now = self.handles['subject_select'].currentText()
        subject_var_file = os.path.join(self.pybpod_dir,project_now,'subjects',subject_now,'variables.json')
        setup_var_file = os.path.join(self.pybpod_dir,project_now,'experiments',experiment_now,'setups',setup_now,'variables.json')
        with open(subject_var_file) as json_file:
            variables_subject = json.load(json_file)
        with open(setup_var_file) as json_file:
            variables_setup = json.load(json_file)
        self.properties['bpod']['subject'] = variables_subject
        self.properties['bpod']['setup'] = variables_setup
        print('save')
        for dicttext in ['subject','setup']:
            for key in self.handles['bpod_variables_'+dicttext].keys(): 
                
                # Auto formatting
                if key in self.properties['bpod'][dicttext].keys():  # If json file has the parameter in the GUI (backward compatibility). HH20200730
                    if type(self.properties['bpod'][dicttext][key]) == bool:
                        if 'true' in self.handles['bpod_variables_'+dicttext][key].text().lower() or '1' in self.handles['bpod_variables_'+dicttext][key].text():
                            self.properties['bpod'][dicttext][key] = True
                        else:
                            self.properties['bpod'][dicttext][key] = False
                    elif type(self.properties['bpod'][dicttext][key]) == float:
                        try:
                            self.properties['bpod'][dicttext][key] = float(self.handles['bpod_variables_'+dicttext][key].text())
                        except:
                            print('not proper value')
                    elif type(self.properties['bpod'][dicttext][key]) == int:                   
                        try:
                            self.properties['bpod'][dicttext][key] = int(round(float(self.handles['bpod_variables_'+dicttext][key].text())))
                        except:
                            print('not proper value')
                            
                else:   # If json file has missing parameters, we add this new parameter (backward compatibility). HH20200730
                    self.properties['bpod'][dicttext][key] = int(self.handles['bpod_variables_'+dicttext][key].text())   # Only consider int now
                        
        with open(self.properties['bpod']['setup_file'], 'w') as outfile:
            json.dump(self.properties['bpod']['setup'], outfile)
        with open(self.properties['bpod']['subject_file'], 'w') as outfile:
            json.dump(self.properties['bpod']['subject'], outfile)
            
        self.bpod_load_parameters()
        self.bpod_check_parameters()

        
        
        ############################################################# BPOD END ##################################################################################
    def bpod_loaddirectorystructure(self,projectnames_needed = None, experimentnames_needed = None,  setupnames_needed=None):
        dirstructure, projectnames, experimentnames, setupnames, sessionnames, subjectnames = utils_pybpod.loaddirstucture(self.pybpod_dir,projectnames_needed, experimentnames_needed,  setupnames_needed)
        self.dirstruct = dirstructure
        self.bpod_alldirs = dict()
        self.bpod_alldirs['projectnames'] = projectnames
        self.bpod_alldirs['experimentnames'] = experimentnames
        self.bpod_alldirs['setupnames'] = setupnames
        self.bpod_alldirs['sessionnames'] = sessionnames        
        self.bpod_alldirs['subjectnames'] = subjectnames     
        print('directory structure reloaded')    
    
    def update_subject(self):   
        subject = self.handles['subject_select'].currentText()
        try:
            configs = np.sort(os.listdir(os.path.join(self.base_dir,'subjects',subject)))[::-1]
        except:
            os.mkdir(os.path.join(self.base_dir,'subjects',subject))
            configs = np.sort(os.listdir(os.path.join(self.base_dir,'subjects',subject)))[::-1]
        self.handles['config_select'].currentIndexChanged.disconnect()
        self.handles['config_select'].clear()
        self.handles['config_select'].addItems(configs)
        self.handles['config_select'].currentIndexChanged.connect(lambda: self.load_config())  
        self.load_config()
        self.bpod_load_parameters()
        self.updatebpodplot()
        
    def load_config(self):
        subject = self.handles['subject_select'].currentText()
        config = self.handles['config_select'].currentText()
        if len(config)==0:
            return None
        file = os.path.join(self.base_dir,'subjects',subject,config)
        with open(file, "r") as read_file:
            new_properties = json.load(read_file)
        print(new_properties)
        
        #% compare new properties with old properties and change if needed
        self.properties['arduino'] = new_properties['arduino']
        if new_properties['zaber']['direction'] != self.properties['zaber']['direction']:
            self.properties['zaber']['direction'] = new_properties['zaber']['direction']
            AllItems = [self.handles['zaber_direction'].itemText(i) for i in range(self.handles['zaber_direction'].count())]
            idx = np.where(AllItems == new_properties['zaber']['direction'])[0]
            self.handles['zaber_direction'].currentIndexChanged.disconnect() 
            self.handles['zaber_direction'].setCurrentIndex(idx)
            self.handles['zaber_direction'].currentIndexChanged.connect(lambda: self.updateZaberUI('details')) 
        if new_properties['zaber']['speed'] != self.properties['zaber']['speed']:
            self.properties['zaber']['speed'] = new_properties['zaber']['speed']
            self.handles['zaber_speed'].setText(str(self.properties['zaber']['speed']))
            self.zaber_change_parameter('speed')
        if new_properties['zaber']['acceleration'] != self.properties['zaber']['acceleration']:
            self.properties['zaber']['acceleration'] = new_properties['zaber']['acceleration']
            self.handles['zaber_acceleration'].setText(str(self.properties['zaber']['acceleration']))
            self.zaber_change_parameter('acceleration')
        if new_properties['zaber']['limit_close'] != self.properties['zaber']['limit_close']:
            self.properties['zaber']['limit_close'] = new_properties['zaber']['limit_close']
            self.handles['zaber_limit_close'].setText(str(self.properties['zaber']['limit_close']))
            self.zaber_change_parameter('limit_close')
        if new_properties['zaber']['limit_far'] != self.properties['zaber']['limit_far']:
            self.properties['zaber']['limit_far'] = new_properties['zaber']['limit_far']
            self.handles['zaber_limit_far'].setText(str(self.properties['zaber']['limit_far']))
            self.zaber_change_parameter('limit_far')
        if new_properties['zaber']['reward_zone'] != self.properties['zaber']['reward_zone']:
            self.properties['zaber']['reward_zone'] = new_properties['zaber']['reward_zone']
            self.handles['zaber_reward_zone_start'].setText(str(self.properties['zaber']['reward_zone']))
        if new_properties['zaber']['max_speed'] != self.properties['zaber']['max_speed']:
            self.properties['zaber']['max_speed'] = new_properties['zaber']['max_speed']
            self.handles['set_max_speed'].setText(str(self.properties['zaber']['max_speed']))
            self.set_max_speed()
        
        self.zaber_set_up_triggers()
        self.updateArduinoUI()
        self.uploadtoArduino()
        
        
    def save_data(self):
        self.properties['zaber']['microstep_size'] = self.microstep_size
        config_name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        subject = self.handles['subject_select'].currentText()
        savefile = os.path.join(self.base_dir,'subjects',subject,'{}.json'.format(config_name))
        with open(savefile, 'w') as fp:
            json.dump(self.properties, fp, indent=2, sort_keys=True)
        self.update_subject() # this reloads the config files, loads and uploads the newest
        
    def set_max_speed(self):
        max_speed = float(self.handles['set_max_speed'].text())
        
        max_step_size = np.abs(self.properties['zaber']['limit_close']-self. properties['zaber']['limit_far'])/10
        speed_of_max_step_size = calculate_step_time(max_step_size,self.properties['zaber']['speed'],self.properties['zaber']['acceleration'])
        absolute_max_speed = max_step_size/speed_of_max_step_size
        if max_speed>absolute_max_speed:
            self.handles['set_max_speed'].setText(str(np.floor(absolute_max_speed)))
            self.set_max_speed()
            return None
        self.properties['zaber']['max_speed'] = int(max_speed)
        s = calculate_step_size_for_max_speed(self.properties['zaber']['speed'],self.properties['zaber']['acceleration'],max_speed)
        self.properties['zaber']['trigger_step_size'] = round(s*1000)
        min_interval = calculate_step_time(s,self.properties['zaber']['speed'],self.properties['zaber']['acceleration'])
        min_interval += extra_time_for_each_step
        function_forward = 'interval = {}/val'.format(round(1024000*min_interval))
        #self.properties['arduino']['function_forward'] = function_forward
        self.handles['arduino_forward_function'].setText(function_forward)
        self.update_arduino_vals()
        
        
    
    def updateArduinoUI(self):
        arduino_ports = find_ports('arduino')
        if len(arduino_ports)==0:
            print('no arduino device found')
            return None
        if self.handles['arduino_port'].currentText()=='?':
            #self.handles['arduino_port'].currentIndexChanged.disconnect()
            self.handles['arduino_port'].clear()
            self.handles['arduino_port'].addItems(arduino_ports)
            #self.handles['arduinor_port'].currentIndexChanged.connect(lambda: self.updateZaberUI('device'))   
            self.properties['arduino']['port'] = arduino_ports[0] 

        
        self.handles['arduino_exec_location'].setText(str(self.properties['arduino']['exec_file_location']))
        self.handles['arduino_analog_pin'].setText(str(self.properties['arduino']['analog_pin']))
        self.handles['arduino_trial_started_pin'].setText(str(self.properties['arduino']['trialStartedPin']))
        self.handles['arduino_digital_out_forward_pin'].setText(str(self.properties['arduino']['digital_out_forward_pin']))
        self.handles['arduino_digital_out_pulse_width'].setText(str(self.properties['arduino']['digital_out_pulse_width']))
        self.handles['arduino_forward_function'].setText(str(self.properties['arduino']['function_forward']))
        self.handles['arduino_min_value_to_move'].setText(str(self.properties['arduino']['min_value_to_move']))
        self.handles['ax_rate_function'].update_freq_plot(self.properties)
    #interval = 323807/val
    def uploadtoArduino(self):
        logging.info('Uploading Zaber triggers')
        self.zaber_set_up_triggers()
        logging.info('Uploading to arduino.. please wait')
        arduino_code_parameters= {'analog_pin':self.properties['arduino']['analog_pin'],
                          'trialStartedPin':self.properties['arduino']['trialStartedPin'],
                          'digital_out_forward_pin':self.properties['arduino']['digital_out_forward_pin'],
                          'activityToBpodPin':self.properties['arduino']['activityToBpodPin'],
                          'digital_out_pulse_width':self.properties['arduino']['digital_out_pulse_width'], #ms
                          'function_forward':self.properties['arduino']['function_forward'],
                          'min_value_to_move':self.properties['arduino']['min_value_to_move'],
                          }
        

        arduino_code = """
class Flasher
{{
  int ledPin;      // the number of the LED pin
  long OnTime;     // milliseconds of on-time
  int ledState;                 // ledState used to set the LED
  unsigned long previousMillis;   // will store last time LED was updated

  public:
  Flasher(int pin, long on)
  {{
  ledPin = pin;
  pinMode(ledPin, OUTPUT);     
    
  OnTime = on;
  ledState = LOW;
  previousMillis = 0;
  }}

  void Update(long off)
  {{
    // check to see if it's time to change the state of the LED
    unsigned long currentMillis = millis();
     
    if((ledState == HIGH) && (currentMillis - previousMillis >= OnTime))
    {{
      ledState = LOW;  // Turn it off
      // previousMillis = currentMillis;  // Remember the time
      digitalWrite(ledPin, ledState);  // Update the actual LED
    }}
    else if ((ledState == LOW) && (currentMillis - previousMillis >= off))
    {{
      ledState = HIGH;  // turn it on
      previousMillis = currentMillis;   // Remember the time
      digitalWrite(ledPin, ledState);   // Update the actual LED
    }}
  }}
}};


Flasher trigger_zaber_forward({digital_out_forward_pin}, {digital_out_pulse_width});
Flasher scanimage_roi_active_to_bpod({activityToBpodPin}, {digital_out_pulse_width});


int analogPin = {analog_pin};
int trialStartedPin = {trialStartedPin};
long val = 0;
long interval = 60000;
int val_trial_is_on = 0;
int val_trial_is_on_multiplier = 0;
void setup() {{
    pinMode(trialStartedPin, INPUT);
}}

void loop() {{
  val_trial_is_on = digitalRead(trialStartedPin);   // read the input pin
  val_trial_is_on_multiplier = (digitalRead(trialStartedPin)==HIGH);
  val = analogRead(analogPin);  // read the input pin
  if(val <= {min_value_to_move})
  {{
    interval = 3000;
  }}
  else {{
    {function_forward};
    scanimage_roi_active_to_bpod.Update(100);
  }}
  val = val*val_trial_is_on_multiplier;
  if(val <= {min_value_to_move})
  {{
    interval = 3000;
  }}
  else {{
    {function_forward};
    trigger_zaber_forward.Update(interval);
  }}
}}
        """.format(**arduino_code_parameters)
        #%%
        self.properties['arduino']['arduino_code']=arduino_code
        self.properties['arduino']['arduino_code_parameters']=arduino_code_parameters
        arduinodir = pathlib.Path(self.properties['arduino']['exec_file_location']).parent.absolute()
        arduinofile = pathlib.Path(self.properties['arduino']['exec_file_location']).name
        os.chdir(arduinodir)
        arduinoProg = arduinofile# r'C:\Program Files (x86)\Arduino\arduino_debug'#
        actionLine = 'upload' #'verify'#
        boardLine= 'arduino:sam:Due' #??? defaults to last used instead
        portLine=self.properties['arduino']['port']
        projectFile= r'C:\Users\bpod\Documents\Python\BCI-motor-control\temp\temp.ino'
        #%%
        file1 = open(projectFile,"w") 
        file1.writelines(arduino_code) 
        file1.close()
        #%%
        #arduinoCommand = arduinoProg + " --" + actionLine + " --board " + boardLine + " --port " + portLine + " --verbose " + projectFile
        arduinoCommand = arduinoProg + " --" + actionLine +  " --port " + portLine + " --verbose " + projectFile
        #%%
        try:
            DETACHED_PROCESS = 0x00000008
            subprocess.call('cmd /k "{}"'.format(arduinoCommand), creationflags=DETACHED_PROCESS)
            #os.system('cmd /k "{}"'.format(arduinoCommand))#presult = subprocess.call(arduinoCommand, shell=True)#, shell=True
            logging.info('Arduino is live')
        except:
            logging.error('Could not upload script to arduino :(')
        print(arduino_code_parameters)
    
    def update_arduino_vals(self):
        #try:
        self.properties['arduino']['exec_file_location']  = self.handles['arduino_exec_location'].text()
        self.properties['arduino']['analog_pin']  = int(self.handles['arduino_analog_pin'].text())
        self.properties['arduino']['trialStartedPin']  = int(self.handles['arduino_trial_started_pin'].text())
        self.properties['arduino']['digital_out_forward_pin']  = int(self.handles['arduino_digital_out_forward_pin'].text())
        self.properties['arduino']['digital_out_pulse_width']  = int(self.handles['arduino_digital_out_pulse_width'].text())
        self.properties['arduino']['function_forward']  = self.handles['arduino_forward_function'].text()
        self.properties['arduino']['min_value_to_move']  = int(self.handles['arduino_min_value_to_move'].text())
    
        self.updateArduinoUI()
        
        
# =============================================================================
#         except:
#             pass
# =============================================================================
    def auto_updatelocation(self):
        if self.handles['zaber_refresh_location_auto'].isChecked():
            self.timer.start()
            self.timer_bpod.start()
        else:
            self.timer.stop()
            self.timer_bpod.stop()
            
    def updatelocation(self):
        self.updateZaberUI('position')
    def updateZaberUI(self,updatefromhere = 'port'):
        self.microstep_size = float(self.handles['zaber_microstep_size'].text())
        zaber_device_ports = find_ports('zaber')
        if len(zaber_device_ports)==0:
            print('no zaber device found')
            return None
        if self.handles['zaber_port'].currentText()=='?' or updatefromhere == 'port':
            self.handles['zaber_port'].currentIndexChanged.disconnect()
            self.handles['zaber_port'].clear()
            self.handles['zaber_port'].addItems(zaber_device_ports)
            self.handles['zaber_port'].currentIndexChanged.connect(lambda: self.updateZaberUI('device'))    
            try:
                port = AsciiSerial(self.handles['zaber_port'].currentText())
                self.zaber_port = port
                self.properties['zaber']['port']=self.handles['zaber_port'].currentText()
            except:
                print('Zaber device not found')
                return None
        # device part
        if updatefromhere in ['port','device']:
            reply = self.zaber_simple_command("get deviceid")
            if type(reply.device_address) == int: #only one device
                if self.handles['zaber_device'].currentText()!=str(reply.device_address):
                    self.handles['zaber_device'].currentIndexChanged.disconnect()
                    self.handles['zaber_device'].clear()
                    self.handles['zaber_device'].addItem(str(reply.device_address))
                    self.handles['zaber_device'].currentIndexChanged.connect(lambda: self.updateZaberUI('axis'))    
                    self.properties['zaber']['device_address'] = reply.device_address
                    self.properties['zaber']['device_id'] =reply.data
            else:
                print('multiple devices.. unhandled')
        # axis part
        if updatefromhere in ['port','device','axis']:
            reply = self.zaber_simple_command("{} get system.axiscount".format(self.properties['zaber']['device_address']))
            axis_list = np.arange(int(reply.data))+1
            AllItems = [self.handles['zaber_axis'].itemText(i) for i in range(self.handles['zaber_axis'].count())]
            if len(AllItems) != len(axis_list) or np.asarray(AllItems) != np.asarray(axis_list,str):
                print('updating axis list')
                self.handles['zaber_axis'].currentIndexChanged.disconnect()
                self.handles['zaber_axis'].clear()
                self.handles['zaber_axis'].addItems(np.asarray(axis_list,str))
                self.properties['zaber']['axis'] = int(self.handles['zaber_axis'].currentText())
            
                self.handles['zaber_axis'].currentIndexChanged.connect(self.zaber_axis_change)  
        # updating all the stuff
        if updatefromhere in ['port','device','axis','details']:
            #self.handles['zaber_trigger_step_size'].setText(str(self.properties['zaber']['trigger_step_size']))
            reply = self.zaber_simple_command("{} {} get maxspeed".format(self.properties['zaber']['device_address'],self.properties['zaber']['axis']))
            speed = round(float(reply.data)*self.microstep_size/1.6384)/1000 #mm/s)
            self.handles['zaber_speed'].setText(str(speed))
            self.properties['zaber']['speed'] = speed
            reply = self.zaber_simple_command("{} {} get accel".format(self.properties['zaber']['device_address'],self.properties['zaber']['axis']))
            accel = round(float(reply.data)*10000*self.microstep_size/1.6384)/1000
            self.handles['zaber_acceleration'].setText(str(accel))
            self.properties['zaber']['acceleration'] = accel
            reply = self.zaber_simple_command("{} {} get limit.home.pos".format(self.properties['zaber']['device_address'],self.properties['zaber']['axis']))
            limit_min = round(float(reply.data)*self.microstep_size)/1000
            reply = self.zaber_simple_command("{} {} get limit.away.pos".format(self.properties['zaber']['device_address'],self.properties['zaber']['axis']))
            limit_max = round(float(reply.data)*self.microstep_size)/1000
            self.properties['zaber']['direction'] = self.handles['zaber_direction'].currentText()
            if self.handles['zaber_direction'].currentText()=='+':
                self.properties['zaber']['limit_close'] = limit_max
                self.properties['zaber']['limit_far'] = limit_min
                
            else:
                self.properties['zaber']['limit_close'] = limit_min
                self.properties['zaber']['limit_far'] = limit_max
            self.handles['zaber_limit_close'].setText(str(self.properties['zaber']['limit_close']))
            self.handles['zaber_limit_far'].setText(str(self.properties['zaber']['limit_far']))
        if updatefromhere in ['port','device','axis','details','position']:
            reply = self.zaber_simple_command("{} {} get pos".format(self.properties['zaber']['device_address'],self.properties['zaber']['axis']))
            position = round(float(reply.data)*self.microstep_size)/1000 #mm
            if 'position' not in self.properties['zaber'].keys() or self.properties['zaber']['position'] != position:
                self.handles['zaber_motor_location'].setText(str(position))
                self.properties['zaber']['position']=position
            reply = self.zaber_simple_command("io get do")
            self.handles['ax_lickport_position'].update_motor_location_plot(self.properties)
# =============================================================================
#             s = self.properties['zaber']['trigger_step_size']/1000
#             v = self.properties['zaber']['speed']
#             a = self.properties['zaber']['acceleration']
#             t = calculate_step_time(s,v,a)
#             print(t*1000)
#             #reply = self.zaber_simple_command("get encoder.pos")
# =============================================================================
     
    
    
    def zaber_move(self,direction = 'value'):
        #print(direction)
        try:
            step_size = float(self.handles['zaber_motor_step_size'].text())/1000
        except:
            step_size = 0.5 #mm
        if direction == 'value':
            pos_mm = float(self.handles['zaber_motor_location'].text())
            pos_microstep = int(1000*pos_mm/self.microstep_size)
            reply = self.zaber_simple_command("{} {} move abs {}".format(self.properties['zaber']['device_address'],self.properties['zaber']['axis'],pos_microstep))
        elif direction == 'close' or direction == 'far':
            zaber_device = self.properties['zaber']['device_address']
            zaber_axis = self.properties['zaber']['axis']
            microstep_size = int(step_size*1000/self.microstep_size)
            direction_of_mouse = float('{}1'.format(self.handles['zaber_direction'].currentText()))
            if direction == 'close':
                microstep_size = int(microstep_size*direction_of_mouse)
            else:
                microstep_size = int(microstep_size*direction_of_mouse*-1)
            reply = self.zaber_simple_command("{} {} move rel {}".format(zaber_device,zaber_axis,microstep_size))
    def zaber_axis_change(self):
        self.properties['zaber']['axis'] = int(self.handles['zaber_axis'].currentText())
        print(self.properties['zaber']['axis'])
        self.updateZaberUI('details')
            
    def zaber_set_up_triggers(self):
        zaber_device = self.properties['zaber']['device_address']
        zaber_axis = self.properties['zaber']['axis']
        #self.properties['zaber']['trigger_step_size'] = float(self.handles['zaber_trigger_step_size'].text())
        microstep_size = int(self.properties['zaber']['trigger_step_size']/self.microstep_size)
        animal_direction = self.handles['zaber_direction'].currentText()
        microstep_size  = int(microstep_size * float('{}1'.format(animal_direction)))
        microstep_home = int(1000*self.properties['zaber']['limit_far']/self.microstep_size)
        microstep_reward = int(1000*float(self.handles['zaber_reward_zone_start'].text())/self.microstep_size)
        self.properties['zaber']['reward_zone'] = float(self.handles['zaber_reward_zone_start'].text())
        if animal_direction == '+':
            reward_compare_function = '>='
            microstep_home += 100
        else:
            reward_compare_function = '<='
            microstep_home -= 100
        reply = self.zaber_simple_command("{} trigger 1 when io di 1 > 0".format(zaber_device))# trigger 1 is digital input 1 from arduino
        reply = self.zaber_simple_command("{} trigger 1 action a {} move rel {}".format(zaber_device,zaber_axis,microstep_size))# trigger 1 is moving towards the animal
        reply = self.zaber_simple_command("{} trigger 1 action b io do 1 toggle".format(zaber_device))# trigger 1 in sends a digital output on do 1
        reply = self.zaber_simple_command("{} trigger 1 enable".format(zaber_device))# trigger 1 in sends a digital output on do 1       
        
        reply = self.zaber_simple_command("{} trigger 2 disable".format(zaber_device))# trigger 1 in sends a digital output on do 1       
        
        reply = self.zaber_simple_command("{} trigger 3 when io di 3 > 0".format(zaber_device))# trigger 3 is digital input 3 from bpod
        reply = self.zaber_simple_command("{} trigger 3 action a {} move abs {}".format(zaber_device,zaber_axis,microstep_home))# trigger 3 is homing
        reply = self.zaber_simple_command("{} trigger 3 action b io do 3 0".format(zaber_device))# also zeroes the digital output 3
        reply = self.zaber_simple_command("{} trigger 3 enable".format(zaber_device))# 
    
        reply = self.zaber_simple_command("{} trigger 4 when {} pos {} {}".format(zaber_device,zaber_axis,reward_compare_function,microstep_reward))# trigger 4 is when motor is at reward zone
        reply = self.zaber_simple_command("{} trigger 4 action a io do 3 1".format(zaber_device))# trigger 1 in sends a digital output on do 3
        reply = self.zaber_simple_command("{} trigger 4 enable".format(zaber_device))# 
        self.update_arduino_vals()
        self.handles['ax_lickport_position'].update_motor_location_plot(self.properties)
        
    def zaber_change_parameter(self,parametername = 'speed'):
        if parametername == 'speed':
            var_to_upload = int(1.6384*float(self.handles['zaber_{}'.format(parametername)].text())*1000/self.microstep_size)
        elif parametername == 'acceleration':
            var_to_upload = int(1.6384*float(self.handles['zaber_{}'.format(parametername)].text())*1000/self.microstep_size/10000)
                
        else:
            var_to_upload = int(float(self.handles['zaber_{}'.format(parametername)].text())*1000/self.microstep_size)
        zaber_device = self.properties['zaber']['device_address']
        zaber_axis = self.properties['zaber']['axis']
        if parametername == 'speed':
            reply = self.zaber_simple_command("{} {} set maxspeed {}".format(zaber_device,zaber_axis,var_to_upload))
        elif parametername == 'acceleration':
            reply = self.zaber_simple_command("{} {} set accel {}".format(zaber_device,zaber_axis,var_to_upload))
        elif (parametername == 'limit_close' and self.handles['zaber_direction'].currentText()=='+') or (parametername == 'limit_far' and self.handles['zaber_direction'].currentText()=='-'):
            reply = self.zaber_simple_command("{} {} get limit.home.pos".format(zaber_device,zaber_axis,var_to_upload))
            home_position = int(reply.data)
            if home_position<var_to_upload:
                if var_to_upload>self.zaber_max_limit:
                    var_to_upload = self.zaber_max_limit
                reply = self.zaber_simple_command("set system.access 2")#limit.sensor.action#maxspeed
                reply = self.zaber_simple_command("{} {} set limit.away.pos {}".format(zaber_device,zaber_axis,var_to_upload))
                reply = self.zaber_simple_command("set system.access 1")#limit.sensor.action#maxspeed
            else:
                print('bad limit value, aborting')
        elif (parametername == 'limit_close' and self.handles['zaber_direction'].currentText()=='-') or (parametername == 'limit_far' and self.handles['zaber_direction'].currentText()=='+'):
            reply = self.zaber_simple_command("{} {} get limit.away.pos".format(zaber_device,zaber_axis,var_to_upload))
            away_position = int(reply.data)
            if away_position>var_to_upload:
                if var_to_upload<self.zaber_min_limit:
                    var_to_upload=self.zaber_min_limit
                reply = self.zaber_simple_command("set system.access 2")#limit.sensor.action#maxspeed
                reply = self.zaber_simple_command("{} {} set limit.home.pos {}".format(zaber_device,zaber_axis,var_to_upload))
                reply = self.zaber_simple_command("set system.access 1")#limit.sensor.action#maxspeed
        self.zaber_set_up_triggers()
        self.updateZaberUI('details')
       
    def zaber_simple_command(self, zaber_ascii_command):
        zaber_command = AsciiCommand(zaber_ascii_command )
        self.zaber_port.write(zaber_command)
        reply = self.zaber_port.read( )
        return(reply)
        
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        
        self.createGridLayout()
        
        
        
        windowLayout = QVBoxLayout()
        windowLayout.addWidget(self.horizontalGroupBox_subject_config)
        windowLayout.addWidget(self.horizontalGroupBox_bpod_variables)
        #windowLayout.addWidget(self.horizontalGroupBox_bpod_plot)
        windowLayout.addWidget(self.horizontalGroupBox_zaber_config)
        windowLayout.addWidget(self.horizontalGroupBox_lickport_pos_axes)
        windowLayout.addWidget(self.horizontalGroupBox_arduino_control)
        windowLayout.addWidget(self.horizontalGroupBox_log)
# =============================================================================
#         windowLayout.addWidget(self.horizontalGroupBox_plot_settings)
#         windowLayout.addWidget(self.horizontalGroupBox_axes)
#         windowLayout.addWidget(self.horizontalGroupBox_variables)
# =============================================================================
        self.setLayout(windowLayout)
        self.show()
    
    def createGridLayout(self):
        self.horizontalGroupBox_bpod_variables = QGroupBox("Bpod variables")
        
        self.horizontalGroupBox_subject_config = QGroupBox("Mouse")
        layout = QGridLayout()
        self.handles['subject_select'] = QComboBox(self)
        self.handles['subject_select'].setFocusPolicy(Qt.NoFocus)
        subjects = os.listdir(os.path.join(self.base_dir,'subjects'))
        self.handles['subject_select'].addItems(subjects)
        self.handles['subject_select'].currentIndexChanged.connect(lambda: self.update_subject())  
        layout.addWidget(QLabel('Mouse ID'),0,0)
        layout.addWidget(self.handles['subject_select'],1, 0)
        
        self.handles['config_select'] = QComboBox(self)
        self.handles['config_select'].setFocusPolicy(Qt.NoFocus)
        subject = self.handles['subject_select'].currentText()
        configs = np.sort(os.listdir(os.path.join(self.base_dir,'subjects',subject)))[::-1]
        self.handles['config_select'].addItems(configs)
        self.handles['config_select'].currentIndexChanged.connect(lambda: self.load_config())  
        layout.addWidget(QLabel('Zaber/Arduino configuration:'),0,1)
        layout.addWidget(self.handles['config_select'],1, 1)
        
        
        
        self.handles['bpod_filter_project'] = QComboBox(self)
        self.handles['bpod_filter_project'].setFocusPolicy(Qt.NoFocus)
        #self.handles['bpod_filter_project'].addItem('?')
        #print(self.alldirs['projectnames'])
        self.handles['bpod_filter_project'].addItems(self.bpod_alldirs['projectnames'])
        self.handles['bpod_filter_project'].currentIndexChanged.connect(lambda: self.bpod_updateUI('filter_project'))
        layout.addWidget(QLabel('Bpod project'),0,2)
        layout.addWidget(self.handles['bpod_filter_project'],1,2)
        self.handles['bpod_filter_experiment'] = QComboBox(self)
        self.handles['bpod_filter_experiment'].setFocusPolicy(Qt.NoFocus)
        self.handles['bpod_filter_experiment'].addItem('?')
        #self.handles['bpod_filter_experiment'].addItems(self.bpod_alldirs['experimentnames'])
        self.handles['bpod_filter_experiment'].currentIndexChanged.connect(lambda: self.bpod_updateUI('filter_experiment'))
        layout.addWidget(QLabel('Bpod experiment'),0,3)
        layout.addWidget(self.handles['bpod_filter_experiment'],1,3)
        self.handles['bpod_filter_setup'] = QComboBox(self)
        self.handles['bpod_filter_setup'].setFocusPolicy(Qt.NoFocus)
        self.handles['bpod_filter_setup'].addItem('?')
        #self.handles['bpod_filter_setup'].addItems(self.bpod_alldirs['setupnames'])
        self.handles['bpod_filter_setup'].currentIndexChanged.connect(lambda: self.bpod_updateUI('filter_setup'))
        layout.addWidget(QLabel('Bpod setup'),0,4)
        layout.addWidget(self.handles['bpod_filter_setup'],1,4)
        self.handles['bpod_loadparams'] = QPushButton('Load bpod variables')
        self.handles['bpod_loadparams'].setFocusPolicy(Qt.NoFocus)
        self.handles['bpod_loadparams'].clicked.connect(self.bpod_load_parameters)
        layout.addWidget(self.handles['bpod_loadparams'],1,5)
        
        
        
        
        self.horizontalGroupBox_subject_config.setLayout(layout)
        
        
       

        
        
        self.horizontalGroupBox_zaber_config = QGroupBox("Zaber setup")
        layout = QGridLayout()
        self.handles['zaber_port'] = QComboBox(self)
        self.handles['zaber_port'].setFocusPolicy(Qt.NoFocus)
        self.handles['zaber_port'].addItem('?')
        self.handles['zaber_port'].currentIndexChanged.connect(lambda: self.updateZaberUI('device'))  
        self.handles['zaber_device'] = QComboBox(self)
        self.handles['zaber_device'].setFocusPolicy(Qt.NoFocus)
        self.handles['zaber_device'].addItem('?')
        self.handles['zaber_device'].currentIndexChanged.connect(lambda: self.updateZaberUI('axis'))    
        self.handles['zaber_axis'] = QComboBox(self)
        self.handles['zaber_axis'].setFocusPolicy(Qt.NoFocus)
        self.handles['zaber_axis'].addItem('?')
        self.handles['zaber_axis'].currentIndexChanged.connect(self.zaber_axis_change)    
        self.handles['zaber_direction'] = QComboBox(self)
        self.handles['zaber_direction'].setFocusPolicy(Qt.NoFocus)
        self.handles['zaber_direction'].addItems(['-','+'])
        self.handles['zaber_direction'].currentIndexChanged.connect(lambda: self.updateZaberUI('details'))    
        self.handles['zaber_speed'] = QLineEdit(self)
        self.handles['zaber_speed'].setText('?')
        self.handles['zaber_speed'].returnPressed.connect(lambda: self.zaber_change_parameter(parametername='speed'))
        self.handles['zaber_acceleration'] = QLineEdit(self)
        self.handles['zaber_acceleration'].setText('?')
        self.handles['zaber_acceleration'].returnPressed.connect(lambda: self.zaber_change_parameter(parametername='acceleration'))
        
        self.handles['zaber_limit_close'] = QLineEdit(self)
        self.handles['zaber_limit_close'].setText('?')
        self.handles['zaber_limit_close'].returnPressed.connect(lambda: self.zaber_change_parameter(parametername='limit_close'))
        
        self.handles['zaber_reward_zone_start'] = QLineEdit(self)
        self.handles['zaber_reward_zone_start'].setText('10')
        self.handles['zaber_reward_zone_start'].returnPressed.connect(self.zaber_set_up_triggers)
        
        self.handles['zaber_limit_far'] = QLineEdit(self)
        self.handles['zaber_limit_far'].setText('?')
        self.handles['zaber_limit_far'].returnPressed.connect(lambda: self.zaber_change_parameter(parametername='limit_far'))
        
# =============================================================================
#         self.handles['zaber_trigger_step_size']= QLineEdit(self)
#         self.handles['zaber_trigger_step_size'].setText('?')
#         self.handles['zaber_trigger_step_size'].returnPressed.connect(lambda: self.zaber_set_up_triggers())
# =============================================================================
        
        self.handles['set_max_speed']= QLineEdit(self)
        self.handles['set_max_speed'].setText(str(self.properties['zaber']['max_speed']))
        self.handles['set_max_speed'].returnPressed.connect(lambda: self.set_max_speed())
        
        self.handles['zaber_microstep_size'] = QLineEdit(self)
        self.handles['zaber_microstep_size'].setText('0.09525')
        self.handles['zaber_microstep_size'].returnPressed.connect(lambda: self.updateZaberUI('details')) 
        
        
        
        self.handles['zaber_download_parameters'] = QPushButton('Download Zaber config')
        self.handles['zaber_download_parameters'].setFocusPolicy(Qt.NoFocus)
        self.handles['zaber_download_parameters'].clicked.connect(lambda: self.updateZaberUI('details'))
        
        
        
        self.handles['zaber_save_parameters'] = QPushButton('Upload config to Zaber and Arduino')
        self.handles['zaber_save_parameters'].setFocusPolicy(Qt.NoFocus)
        self.handles['zaber_save_parameters'].clicked.connect(lambda: self.save_data())
        
        
        
        # TODO add load parameters from motor, send parameters to zaber, limits, update location (and auto update checkbox)

        layout.addWidget(QLabel('Zaber port'),0,0)
        layout.addWidget(self.handles['zaber_port'],1,0)
        layout.addWidget(QLabel('device'),0,1)
        layout.addWidget(self.handles['zaber_device'],1,1)
        layout.addWidget(QLabel('axis'),0,2)
        layout.addWidget(self.handles['zaber_axis'],1,2)
        layout.addWidget(QLabel('direction to mouse'),0,3)
        layout.addWidget(self.handles['zaber_direction'],1,3)
        layout.addWidget(QLabel('Zaber max speed (mm/s)'),0,4)
        layout.addWidget(self.handles['zaber_speed'],1,4)
        layout.addWidget(QLabel('Zaber acceleration mm/s^2'),0,5)
        layout.addWidget(self.handles['zaber_acceleration'],1,5)
        layout.addWidget(QLabel('Close position (mm)'),0,6)
        layout.addWidget(self.handles['zaber_limit_close'],1,6)
        layout.addWidget(QLabel('Reward zone start'),0,7)
        layout.addWidget(self.handles['zaber_reward_zone_start'],1,7)
        layout.addWidget(QLabel('Far position (mm)'),0,8)
        layout.addWidget(self.handles['zaber_limit_far'],1,8)
# =============================================================================
#         layout.addWidget(QLabel('Triggered step size (microns)'),0,9)
#         layout.addWidget(self.handles['zaber_trigger_step_size'],1,9)
# =============================================================================
        layout.addWidget(QLabel('Maximum BCI speed (mm/s)'),0,9)
        layout.addWidget(self.handles['set_max_speed'],1,9)
        layout.addWidget(QLabel('microstep size (microns)'),0,10)
        layout.addWidget(self.handles['zaber_microstep_size'],1,10)
        layout.addWidget(self.handles['zaber_download_parameters'],1,11)
        layout.addWidget(self.handles['zaber_save_parameters'],1,12)
        
        self.horizontalGroupBox_zaber_config.setLayout(layout)

        # ----- Lickport location -----
        self.horizontalGroupBox_lickport_pos_axes = QGroupBox("lickport position")
        layout_axes = QGridLayout()
        layout_axes.setColumnStretch(0, 200)
# =============================================================================
#         layout_axes.setRowStretch(0, 0)
#         layout_axes.setRowStretch(1, 0)
#         layout_axes.setRowStretch(2, 10)
# =============================================================================
        self.handles['ax_lickport_position'] = PlotCanvas(self, width=5, height=4)
        layout_axes.addWidget(self.handles['ax_lickport_position'],0, 1,10,1)
        
        self.handles['ax_bpod_results'] = PlotCanvas(self, width=5, height=4)        
        layout_axes.addWidget(self.handles['ax_bpod_results'],0, 0,10,1)
        
        
        
        self.handles['zaber_move_closer'] = QPushButton('Move Closer')
        self.handles['zaber_move_closer'].clicked.connect(lambda: self.zaber_move('close'))
        self.handles['zaber_move_closer'].setFocusPolicy(Qt.NoFocus)
        layout_axes.addWidget(self.handles['zaber_move_closer'],1, 2)
        layout_axes.addWidget(QLabel('Current location (mm)'),0,3)
        self.handles['zaber_motor_location'] = QLineEdit(self)
        self.handles['zaber_motor_location'].resize(5,40)
        self.handles['zaber_motor_location'].setText('?')
        self.handles['zaber_motor_location'].returnPressed.connect(lambda: self.zaber_move('value')) 
        layout_axes.addWidget(self.handles['zaber_motor_location'],1, 3)
        self.handles['zaber_move_away'] = QPushButton('Move Away')
        self.handles['zaber_move_away'].clicked.connect(lambda: self.zaber_move('far'))
        self.handles['zaber_move_away'].setFocusPolicy(Qt.NoFocus)
        layout_axes.addWidget(self.handles['zaber_move_away'],1, 4)
        self.handles['zaber_refresh_location'] = QPushButton('Refresh location')
        self.handles['zaber_refresh_location'].clicked.connect(lambda: self.updateZaberUI('position'))
        self.handles['zaber_refresh_location'].setFocusPolicy(Qt.NoFocus)
        layout_axes.addWidget(self.handles['zaber_refresh_location'],2, 3)
        self.handles['zaber_refresh_location_auto'] = QCheckBox(self)
        self.handles['zaber_refresh_location_auto'].setText('auto refresh location')
        self.handles['zaber_refresh_location_auto'].stateChanged.connect(self.auto_updatelocation)
        layout_axes.addWidget(self.handles['zaber_refresh_location_auto'],2, 4)
        
        layout_axes.addWidget(QLabel('Step size (microns)'),3,2)
        self.handles['zaber_motor_step_size'] = QLineEdit(self)
        self.handles['zaber_motor_step_size'].resize(5,40)
        self.handles['zaber_motor_step_size'].setText('500')
        layout_axes.addWidget(self.handles['zaber_motor_step_size'],3, 3)
        
        
        self.horizontalGroupBox_lickport_pos_axes.setLayout(layout_axes)
        
        
        
        self.horizontalGroupBox_arduino_control = QGroupBox("arduino control")
        layout_arduino_cfg = QGridLayout()
        
        self.handles['ax_rate_function'] = PlotCanvas(self, width=5, height=4)
        layout_arduino_cfg.addWidget(self.handles['ax_rate_function'],2, 0,1,60)
        
        self.handles['arduino_port'] = QComboBox(self)
        self.handles['arduino_port'].setFocusPolicy(Qt.NoFocus)
        self.handles['arduino_port'].addItem('?')
        #self.handles['arduino_port'].currentIndexChanged.connect(lambda: self.updateZaberUI('device')) 
        layout_arduino_cfg.addWidget(QLabel('arduino port'),0,0)
        layout_arduino_cfg.addWidget(self.handles['arduino_port'],1, 0)
        
        
        self.handles['arduino_exec_location'] = QLineEdit(self)
        self.handles['arduino_exec_location'].setText('?')
        self.handles['arduino_exec_location'].returnPressed.connect(lambda: self.update_arduino_vals())#self.update_arduino_vals()) 
        layout_arduino_cfg.addWidget(QLabel('arduino exec file'),0,1)
        layout_arduino_cfg.addWidget(self.handles['arduino_exec_location'],1, 1)
        
        self.handles['arduino_analog_pin'] = QLineEdit(self)
        self.handles['arduino_analog_pin'].setText('?')
        #self.handles['arduino_analog_pin'].returnPressed.connect(lambda: self.zaber_move('value')) 
        layout_arduino_cfg.addWidget(QLabel('analog pin'),0,2)
        layout_arduino_cfg.addWidget(self.handles['arduino_analog_pin'],1, 2)
        
        self.handles['arduino_trial_started_pin'] = QLineEdit(self)
        self.handles['arduino_trial_started_pin'].setText('?')
        #self.handles['arduino_trial_started_pin'].returnPressed.connect(lambda: self.zaber_move('value')) 
        layout_arduino_cfg.addWidget(QLabel('trial started pin'),0,3)
        layout_arduino_cfg.addWidget(self.handles['arduino_trial_started_pin'],1, 3)
        
        self.handles['arduino_digital_out_forward_pin'] = QLineEdit(self)
        self.handles['arduino_digital_out_forward_pin'].setText('?')
        #self.handles['arduino_digital_out_forward_pin'].returnPressed.connect(lambda: self.zaber_move('value')) 
        layout_arduino_cfg.addWidget(QLabel('out fwd pin'),0,4)
        layout_arduino_cfg.addWidget(self.handles['arduino_digital_out_forward_pin'],1, 4)
        
        self.handles['arduino_digital_out_pulse_width'] = QLineEdit(self)
        self.handles['arduino_digital_out_pulse_width'].setText('?')
        #self.handles['arduino_digital_out_pulse_width'].returnPressed.connect(lambda: self.zaber_move('value')) 
        layout_arduino_cfg.addWidget(QLabel('pulse width'),0,5)
        layout_arduino_cfg.addWidget(self.handles['arduino_digital_out_pulse_width'],1, 5)
        
        
        self.handles['arduino_min_value_to_move'] = QLineEdit(self)
        self.handles['arduino_min_value_to_move'].setText('?')
        self.handles['arduino_min_value_to_move'].returnPressed.connect(lambda: self.update_arduino_vals())#self.update_arduino_vals()) 
        layout_arduino_cfg.addWidget(QLabel('minimum ai to move'),0,6)
        layout_arduino_cfg.addWidget(self.handles['arduino_min_value_to_move'],1, 6)
        
        
        self.handles['arduino_forward_function'] = QLineEdit(self)
        self.handles['arduino_forward_function'].setText('?')
        self.handles['arduino_forward_function'].returnPressed.connect(lambda: self.update_arduino_vals())#self.update_arduino_vals()) 
        layout_arduino_cfg.addWidget(QLabel('forward function'),0,7)
        layout_arduino_cfg.addWidget(self.handles['arduino_forward_function'],1, 7)
        
# =============================================================================
#         self.handles['arduino_upload'] = QPushButton('upload to arduino')
#         self.handles['arduino_upload'].clicked.connect(lambda: self.uploadtoArduino())
#         self.handles['arduino_upload'].setFocusPolicy(Qt.NoFocus)
#         layout_arduino_cfg.addWidget(self.handles['arduino_upload'],1, 8)
# =============================================================================
        
        
        
        
        self.horizontalGroupBox_arduino_control.setLayout(layout_arduino_cfg)
        
        self.horizontalGroupBox_log = QGroupBox("logs")
        
        logTextBox = QTextEditLogger(self)
        # You can format what is printed to text box
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(logTextBox)
        # You can control the logging level
        logging.getLogger().setLevel(logging.DEBUG)

# =============================================================================
#         self._button = QPushButton(self)
#         self._button.setText('Test Me')
# =============================================================================

        layout =  QGridLayout()#QVBoxLayout()
        # Add the new logging box widget to the layout
        layout.addWidget(logTextBox.widget)
# =============================================================================
#         layout.addWidget(self._button)
# =============================================================================
        self.setLayout(layout)
        
        self.horizontalGroupBox_log.setLayout(layout)
        
        
    
        
    
        #%%
class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=2, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        
        # Use one canvas for all plots, which makes axis control more straightforward. HH20200729
        #  self.axes = fig.add_subplot(111)
        # self.axes = fig.subplots(2,1, sharex=True)
        # fig.tight_layout() 
        
        self.ax1 = self.fig.add_subplot(1,1,1)
        self.ax2 = self.ax1.twinx()
        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self,
                QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        #self.plot()
    
    def update_bpod_plot(self,data):
        #print(data.keys())
        self.ax1.cla()
        self.ax2.cla()
        time_to_hit = np.asarray(data['time_to_hit'])
        trial_num = np.asarray(data['trial_num'])
        trial_hit = np.asarray(data['trial_hit'])
        file_start_trialnum = np.asarray(data['file_start_trialnum'])
        #time_to_hit[np.isnan(time_to_hit)] = 0
        self.ax1.semilogy(trial_num[trial_hit],time_to_hit[trial_hit],'go',markersize = 1)
        miss_idx = trial_hit == False
        self.ax1.plot(trial_num[miss_idx],np.ones(sum(miss_idx)),'ro',markersize = 1)
        self.ax2.plot(trial_num,np.convolve(trial_hit,np.ones(10)/10,'same')*100,'k-')
        self.ax1.set_ylabel('response time (s)')
        self.ax1.set_xlabel('Trial #')
        self.ax2.set_ylabel('Hit rate (%)')
        self.ax2.vlines(file_start_trialnum, 0, 100, colors='b', linestyles='dashed')
        self.ax1.set_title('Trials: {} Hits: {}'.format(len(trial_hit[file_start_trialnum[-1]:]),sum(trial_hit[file_start_trialnum[-1]:])))
        self.draw()
    def update_freq_plot(self,properties):
        #try:
        self.ax1.cla()
        self.ax2.cla()
        step_size = properties['zaber']['trigger_step_size']/1000 ## mm
        function_string = properties['arduino']['function_forward']
        function_string  = function_string[function_string.find('=')+1:]
        val = np.arange(0,1024,1)
        intervals = None
        
        
        d = {'val':val}
        print(function_string)
        exec('intervals = {}/1000'.format(function_string),d) #in seconds
        
        freq = 1/(d['intervals'])
        freq[val<properties['arduino']['min_value_to_move']]= 0
        self.ax1.plot(val,freq*step_size)
        self.ax2.plot(val,freq)
        self.ax1.set_xlabel('input analog signal')
        self.ax1.set_ylabel('movement speed (mm/s)')
        self.ax2.set_ylabel('movement rate (Hz)')
        self.draw()
    
    def update_motor_location_plot(self,properties):
        #try:
        self.ax1.cla()
        self.ax2.cla()
        limit_close = properties['zaber']['limit_close']
        limit_far = properties['zaber']['limit_far']
        direction = properties['zaber']['direction']
        reward_zone = properties['zaber']['reward_zone']
        position =  properties['zaber']['position']
        self.ax1.plot([limit_far,limit_far],[0,1], 'r-',linewidth=4)
        self.ax1.plot([limit_close,limit_close],[0,1], 'r-',linewidth=4)
        self.ax1.plot([reward_zone,reward_zone],[0,1], 'g--',linewidth=2)
        self.ax1.plot(position,.5, 'bo',markersize = 20)
        self.ax1.set_xlim([np.min([limit_close,limit_far])-1,np.max([limit_close,limit_far])+1])
        self.ax1.set_ylim([0,1])
        self.draw()
# =============================================================================
#         except:
#             pass
# =============================================================================
        
        
# =============================================================================
#     
#     def update_plots(self, times, values, win_width):
#                 
#         # --- Plotting ---
#         self.plot_licks_and_rewards(times)
#         self.plot_bias(times, values, win_width)
#         self.plot_matching(times, win_width)
# =============================================================================
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())        