
class Flasher
{
  int ledPin;      // the number of the LED pin
  long OnTime;     // milliseconds of on-time
  int ledState;                 // ledState used to set the LED
  unsigned long previousMillis;   // will store last time LED was updated

  public:
  Flasher(int pin, long on)
  {
  ledPin = pin;
  pinMode(ledPin, OUTPUT);     
    
  OnTime = on;
  ledState = LOW;
  previousMillis = 0;
  }

  void Update(long off)
  {
    // check to see if it's time to change the state of the LED
    unsigned long currentMillis = millis();
     
    if((ledState == HIGH) && (currentMillis - previousMillis >= OnTime))
    {
      ledState = LOW;  // Turn it off
      // previousMillis = currentMillis;  // Remember the time
      digitalWrite(ledPin, ledState);  // Update the actual LED
    }
    else if ((ledState == LOW) && (currentMillis - previousMillis >= off))
    {
      ledState = HIGH;  // turn it on
      previousMillis = currentMillis;   // Remember the time
      digitalWrite(ledPin, ledState);   // Update the actual LED
    }
  }
};


Flasher trigger_zaber_forward(9, 1);

int analogPin = 0;
int trialStartedPin = 12;
long val = 0;
long interval = 60000;
int val_trial_is_on = 0;
int val_trial_is_on_multiplier = 0;
void setup() {
    pinMode(trialStartedPin, INPUT);
}

void loop() {
  val_trial_is_on = digitalRead(trialStartedPin);   // read the input pin
  val_trial_is_on_multiplier = (digitalRead(trialStartedPin)==HIGH);
  val = analogRead(analogPin);  // read the input pin
  val = val*val_trial_is_on_multiplier;
  if(val < 10)
  {
    interval = 3000;
  }
  else {
    interval = 15395/val;
    trigger_zaber_forward.Update(interval);
  }
}
        