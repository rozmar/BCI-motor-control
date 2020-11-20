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
#from scipy import stats
try:
    import zaber.serial as zaber_serial
except:
    pass
#%%
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
        t=calculate_step_time(s,v,a)
        speed = s/t
    return s
#%%
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
        
        zaber_properties = {'trigger_step_size':100}
        arduino_properties = {'analog_pin':0,
                              'trialStartedPin':12,
                              'digital_out_forward_pin':9,
                              'digital_out_pulse_width':1, #ms
                              'function_forward':'interval = 10000/val',
                              'exec_file_location': r'C:\Program Files (x86)\Arduino\arduino.exe',
                              'min_value_to_move':10}
        self.properties = {'zaber':zaber_properties,
                           'arduino':arduino_properties}
        self.zaber_port = None
        self.zaber_max_limit = 310000
        self.zaber_min_limit = 0
        self.initUI()
        self.updateZaberUI()
        self.updateArduinoUI()
        
    def set_max_speed(self):
        max_speed = float(self.handles['set_max_speed'].text())
        
        max_step_size = np.abs(self.properties['zaber']['limit_close']-self. properties['zaber']['limit_far'])/10
        speed_of_max_step_size = calculate_step_time(max_step_size,self.properties['zaber']['speed'],self.properties['zaber']['acceleration'])
        absolute_max_speed = max_step_size/speed_of_max_step_size
        if max_speed>absolute_max_speed:
            self.handles['set_max_speed'].setText(str(np.floor(absolute_max_speed)))
            return None
        s = calculate_step_size_for_max_speed(self.properties['zaber']['speed'],self.properties['zaber']['acceleration'],max_speed)
        self.properties['zaber']['trigger_step_size'] = round(s*1000)
        min_interval = calculate_step_time(s,self.properties['zaber']['speed'],self.properties['zaber']['acceleration'])
       # min_interval += +.001
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
  val = val*val_trial_is_on_multiplier;
  if(val < {min_value_to_move})
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
            os.system('cmd /k "{}"'.format(arduinoCommand))#presult = subprocess.call(arduinoCommand, shell=True)#, shell=True
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
                self.handles['zaber_axis'].currentIndexChanged.connect(lambda: self.updateZaberUI('details'))    
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
            self.handles['zaber_motor_location'].setText(str(position))
            reply = self.zaber_simple_command("io get do")
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
                
            
    def zaber_set_up_triggers(self):
        zaber_device = self.properties['zaber']['device_address']
        zaber_axis = self.properties['zaber']['axis']
        #self.properties['zaber']['trigger_step_size'] = float(self.handles['zaber_trigger_step_size'].text())
        microstep_size = int(self.properties['zaber']['trigger_step_size']/self.microstep_size)
        animal_direction = self.handles['zaber_direction'].currentText()
        microstep_size  = int(microstep_size * float('{}1'.format(animal_direction)))
        microstep_home = int(1000*self.properties['zaber']['limit_far']/self.microstep_size)
        microstep_reward = int(1000*float(self.handles['zaber_reward_zone_start'].text())/self.microstep_size)
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
        self.handles['zaber_axis'].currentIndexChanged.connect(lambda: self.updateZaberUI('details'))    
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
        #self.handles['zaber_reward_zone_start'].returnPressed.connect(lambda: self.zaber_change_parameter(parametername='limit_close'))
        
        self.handles['zaber_limit_far'] = QLineEdit(self)
        self.handles['zaber_limit_far'].setText('?')
        self.handles['zaber_limit_far'].returnPressed.connect(lambda: self.zaber_change_parameter(parametername='limit_far'))
        
# =============================================================================
#         self.handles['zaber_trigger_step_size']= QLineEdit(self)
#         self.handles['zaber_trigger_step_size'].setText('?')
#         self.handles['zaber_trigger_step_size'].returnPressed.connect(lambda: self.zaber_set_up_triggers())
# =============================================================================
        
        self.handles['set_max_speed']= QLineEdit(self)
        self.handles['set_max_speed'].setText('3')
        self.handles['set_max_speed'].returnPressed.connect(lambda: self.set_max_speed())
        
        self.handles['zaber_microstep_size'] = QLineEdit(self)
        self.handles['zaber_microstep_size'].setText('0.09525')
        self.handles['zaber_microstep_size'].returnPressed.connect(lambda: self.updateZaberUI('details')) 
        
        
        
        self.handles['zaber_download_parameters'] = QPushButton('Download Zaber config')
        self.handles['zaber_download_parameters'].setFocusPolicy(Qt.NoFocus)
        self.handles['zaber_download_parameters'].clicked.connect(lambda: self.updateZaberUI('details'))
        
        
        
        self.handles['zaber_save_parameters'] = QPushButton('Save Zaber config')
        self.handles['zaber_save_parameters'].setFocusPolicy(Qt.NoFocus)
        #self.handles['zaber_save_parameters'].clicked.connect(self.loadthedata)
        
        
        
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
        layout_axes.addWidget(self.handles['ax_lickport_position'],0, 0,10,1)
        
        
        
        
        self.handles['zaber_move_closer'] = QPushButton('Move Closer')
        self.handles['zaber_move_closer'].clicked.connect(lambda: self.zaber_move('close'))
        self.handles['zaber_move_closer'].setFocusPolicy(Qt.NoFocus)
        layout_axes.addWidget(self.handles['zaber_move_closer'],1, 1)
        layout_axes.addWidget(QLabel('Current location (mm)'),0,2)
        self.handles['zaber_motor_location'] = QLineEdit(self)
        self.handles['zaber_motor_location'].resize(5,40)
        self.handles['zaber_motor_location'].setText('?')
        self.handles['zaber_motor_location'].returnPressed.connect(lambda: self.zaber_move('value')) 
        layout_axes.addWidget(self.handles['zaber_motor_location'],1, 2)
        self.handles['zaber_move_away'] = QPushButton('Move Away')
        self.handles['zaber_move_away'].clicked.connect(lambda: self.zaber_move('far'))
        self.handles['zaber_move_away'].setFocusPolicy(Qt.NoFocus)
        layout_axes.addWidget(self.handles['zaber_move_away'],1, 3)
        self.handles['zaber_refresh_location'] = QPushButton('Refresh location')
        self.handles['zaber_refresh_location'].clicked.connect(lambda: self.updateZaberUI('position'))
        self.handles['zaber_refresh_location'].setFocusPolicy(Qt.NoFocus)
        layout_axes.addWidget(self.handles['zaber_refresh_location'],2, 2)
        self.handles['zaber_refresh_location_auto'] = QCheckBox(self)
        self.handles['zaber_refresh_location_auto'].setText('auto refresh location')
        layout_axes.addWidget(self.handles['zaber_refresh_location_auto'],2, 3)
        
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
        
        self.handles['arduino_upload'] = QPushButton('upload to arduino')
        self.handles['arduino_upload'].clicked.connect(lambda: self.uploadtoArduino())
        self.handles['arduino_upload'].setFocusPolicy(Qt.NoFocus)
        layout_arduino_cfg.addWidget(self.handles['arduino_upload'],1, 8)
        
        
        
        
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