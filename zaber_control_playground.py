#%%
from zaber.serial import AsciiSerial,AsciiCommand
#%% basic parameters
port = AsciiSerial("/dev/ttyACM7")

device_address = 0
axis_number = 1
max_speed = 30000
acceleration = 400
#%% movement related stuff
zaber_ascii_command = "move vel -000000"#"trigger info"#"get pos" #"get limit.min"#"move rel 1000"# "set maxspeed {}".format(max_speed) #"set accel {}".format(acceleration) 
zaber_command = AsciiCommand(device_address,axis_number, zaber_ascii_command )
port.write(zaber_command)
reply = port.read( )
print(reply)

#%% configuring triggers for analog input
def zaber_trigger_command(zaber_ascii_command):
    zaber_command = AsciiCommand(device_address, zaber_ascii_command )
    port.write(zaber_command)
    reply = port.read( )
    return(reply)
def zaber_read_command(zaber_ascii_command):
    zaber_command = AsciiCommand(zaber_ascii_command )
    port.write(zaber_command)
    reply = port.read( )
    return(reply)

#%%
zaber_voltage_range_lower_bounds = [40000,70000,100000] #V
zaber_speeds = [0,20000,50000,100000]
for trigger_i, voltage in enumerate(zaber_voltage_range_lower_bounds):
    for direction_i in [1,2]:
        trigger_num = 7-(direction_i+trigger_i*2)
        if direction_i == 1:
            cmd = "trigger {} when io ai 1 < {} ".format(trigger_num,voltage)
            reply = zaber_trigger_command(cmd)#"trigger show"#"trigger info"
            print([cmd,str(reply)])
            cmd ="trigger {} action a {} move vel {} ".format(trigger_num,axis_number,zaber_speeds[trigger_i])
            reply = zaber_trigger_command(cmd)#"trigger show"#"trigger info"
            print([cmd,str(reply)])
        else:
            cmd = "trigger {} when io ai 1 > {} ".format(trigger_num,voltage)
            reply = zaber_trigger_command(cmd)#"trigger show"#"trigger info"
            print([cmd,str(reply)])
            cmd =  "trigger {} action a {} move vel {} ".format(trigger_num,axis_number,zaber_speeds[trigger_i+1])
            reply = zaber_trigger_command(cmd)#"trigger show"#"trigger info"
            print([cmd,str(reply)])
        reply = zaber_trigger_command("trigger {} disable".format(trigger_num))#"trigger show"#"trigger info"
        print(reply)
#%% triggers for digital input from arduino    
microstep_size = 500
cmd = "{} trigger 1 when io di 1 > 0 ".format(device)
reply = zaber_trigger_command(cmd)#"trigger show"#"trigger info"
cmd ="trigger 1 action a {} move rel {} ".format(axis_number,microstep_size)
reply = zaber_trigger_command(cmd)
cmd ="trigger 1 action a {} move rel {} ".format(axis_number,microstep_size)
reply = zaber_trigger_command(cmd)


reply = zaber_trigger_command("trigger 1 enable".format(trigger_num))#"trigger show"#"trigger info"
print(reply)
    
    

#%%stop trigger

reply = zaber_trigger_command("trigger dist 1 1 100")
print(reply)
reply = zaber_trigger_command("trigger dist 1 action a {} move vel {} ".format(axis_number,0))#"trigger show"#"trigger info"
print(reply)
reply = zaber_trigger_command("trigger dist 1 enable")#"trigger show"#"trigger info"
print(reply)
reply = zaber_trigger_command("trigger 6 when io di 1 > 0")
print(reply)
reply = zaber_trigger_command("trigger 6 action a {} move vel {} ".format(axis_number,0))#"trigger show"#"trigger info"
print(reply)
reply = zaber_trigger_command("trigger 6 enable")#"trigger show"#"trigger info"
print(reply)
#%%
reply = zaber_trigger_command("trigger show")
print(reply)
#%%
reply = zaber_trigger_command("system restore")#limit.sensor.action#maxspeed
print(reply)
#%%
reply = zaber_trigger_command("io set do 3 0")#limit.sensor.action#maxspeed
reply = zaber_trigger_command("io get do")#limit.sensor.action#maxspeed
print(reply)
#%%

reply = zaber_trigger_command("set system.access 2")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 1 set limit.c.edge 1")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 1 set limit.c.action 0")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 set limit.c.type 0")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 set limit.d.edge 0")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 set limit.d.action 0")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 set limit.d.type 0")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("set system.access 1")#limit.sensor.action#maxspeed
print(reply)
#%%
reply = zaber_trigger_command("set system.access 2")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 1 set limit.home.pos 0")#limit.sensor.action#maxspeed
print(reply)
# =============================================================================
# reply = zaber_trigger_command("1 1 set limit.c.posupdate 1")#limit.sensor.action#maxspeed
# print(reply)
# reply = zaber_trigger_command("1 1 set limit.c.type 2")#limit.sensor.action#maxspeed
# print(reply)
# =============================================================================

# =============================================================================
# reply = zaber_trigger_command("1 1 set limit.c.edge 1")#limit.sensor.action#maxspeed
# print(reply)
# reply = zaber_trigger_command("1 1 set limit.c.action 0")#limit.sensor.action#maxspeed
# print(reply)
# 
# =============================================================================
reply = zaber_trigger_command("set system.access 1")#limit.sensor.action#maxspeed
print(reply)
#%%
reply = zaber_trigger_command("1 get limit.away.pos")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 get limit.home.edge")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 get limit.home.action")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 get limit.home.type")#limit.sensor.action#maxspeed
print(reply)
reply = zaber_trigger_command("1 get limit.home.state")#limit.sensor.action#maxspeed
print(reply)
#%%
reply = zaber_trigger_command("1 1 move abs 110000")#limit.sensor.action#maxspeed
print(reply)


#%%
reply = zaber_trigger_command("1 get pos")#limit.sensor.action#maxspeed
print(reply)
#%%
reply = zaber_read_command("io get di 1")
print(reply)




#%% compose arduino code
arduino_code_parameters= {'analog_pin':0,
                          'trialStartedPin':12,
                          'digital_out_forward_pin':13,
                          'digital_out_pulse_width':1, #ms
                          'function_forward':'interval = 1000/val'
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

int analogPin = {analogPin};
int trialStartedPin = {trialStartedPin};
long val = 0;
long interval = 60000;
void setup() {{
    pinMode(trialStartedPin, INPUT)
}}

void loop() {{
  val_trial_is_on = digitalRead(inPin);   // read the input pin
  val = analogRead(analogPin);  // read the input pin
  val = val*val_trial_is_on
  if(val < 10)
  {{
    interval = 3000;
  }}
  else {{
    {function_forward};
  }}
  trigger_zaber_forward.Update(interval);
}}
""".format(**arduino_code_parameters)

#%% upload arduino code to arduino
import subprocess
import sys

arduinoProg = '/home/rozmar/Scripts/Python/pybpod/arduino-1.8.9/arduino' # the software
actionLine = 'upload' #'verify'#
boardLine= 'arduino:sam:Due' #??? defaults to last used instead
portLine="/dev/ttyACM2"
projectFile= '/home/rozmar/Scripts/Python/Zaber/temp.ino'
file1 = open(projectFile,"w") 
file1.writelines(arduino_code) 
file1.close()
#%
#arduinoCommand = arduinoProg + " --" + actionLine + " --board " + boardLine + " --port " + portLine + " --verbose " + projectFile
arduinoCommand = arduinoProg + " --" + actionLine +  " --port " + portLine + " --verbose " + projectFile
presult = subprocess.call(arduinoCommand, shell=True)



#%% show speed profile
fig =  plt.figure(figsize = [15,10])
ax_max_speed = fig.add_subplot(1,1,1)
ax_max_freq = ax_max_speed.twinx()
a = 500
v = 60
s_list = np.arange(1,1000,5)
ts = list()
for s in s_list: 
    ts.append(calculate_step_time(s/1000,v,a))
freqs = 1/np.asarray(ts)
ax_max_speed.plot(s_list,freqs*s_list/1000,'k-', label = 'maximum speed')
ax_max_speed.plot(s_list,30*s_list/1000,'b-', label = 'speed at 30 Hz')
ax_max_freq.semilogy(s_list,freqs,'r-', label = 'maximum frequency')
ax_max_speed.set_xlabel('step size (microns)')
ax_max_speed.set_ylabel('maximum speed (mm/s)')
ax_max_freq.set_ylabel('maximum frequency (Hz)')
ax_max_freq.yaxis.label.set_color('red')
ax_max_freq.tick_params(axis='y', colors='red')
ax_max_speed.legend()
ax_max_freq.legend()

ax_max_freq.set_ylim([1,1000])
ax_max_speed.set_ylim([0,35])