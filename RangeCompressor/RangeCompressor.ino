// Range Cpmpressor
// for IOProcessor Board J006021 - Teensy 3.5
// Utilizes the ADC in section of the board
// 
//  Read the input and send out USB
//   
//
// Steve Sawtelle
// ID&F
// Janelia
// HHMI 
//

#define VERSION "20210414"
// ===== VERSIONS ======

// 20210414 sws
// - redid ranging calculations
// - added commands

// 20210222 sws
// - adapted from lick port IO Processor code

#include <Cmd.h>

#define adcPin A14

#define testPin 35

static unsigned long SAMPLEMICROS = 50;  // == 100 = 10000 Hz, 50 = 20000

int16_t newVal = 0;
int16_t lastVal = 0;
unsigned long lastMicros;
unsigned long newMicros;
int last = 0;
int32_t sum = 0;
int16_t outVal;

// limiter
// input is 0 to 8191, for -3000 to 2000 mVolts
// so we have 1.6382 counts / mV
#define cntsPerMv 1.6382
#define mvPerCnt (1.0 / cntsPerMv)

#define minMv -3000.0
#define maxMv 2000.0

// and 0 = -3000 mVolts, so zero Counts = 3000 * 1.6382
float zeroMv = 3000.0;
float zeroCnts = (zeroMv * cntsPerMv);

float limitHighMv = 1000.0; // mVolts
float limitLowMv  = -2000.0; // mVolts
int eventMode = 0; // true/false
float timeConstant = 1000; //ms - only in event mode
float eventAmplitude = 1000; // mV - only in event mode
float minEventLength = 1000; // microseconds - only in event mode



void newLower(int arg_cnt, char **args)
{
  Stream *s = cmdGetStream();

  if( arg_cnt > 1 )
  {
    float tLower = cmdStr2Float(args[1]);
    if( (tLower >= minMv) && (tLower < limitHighMv) ) limitLowMv = tLower;
  }
  else
  {
    s->println(limitLowMv);
  }
}

void newUpper(int arg_cnt, char **args)
{
  Stream *s = cmdGetStream();

  if( arg_cnt > 1 )
  {
    float tUpper = cmdStr2Float(args[1]);
    if( (tUpper <= maxMv) && (tUpper > limitLowMv) ) limitHighMv = tUpper;
  }
  else
  {
    s->println(limitHighMv);
  }
}

void newEventmode(int arg_cnt, char **args)
{
  Stream *s = cmdGetStream();

  if( arg_cnt > 1 )
  {
    float tEventmode = cmdStr2Float(args[1]);
    if( (tEventmode >= 1) ) 
      eventMode = 1;
    else 
      eventMode = 0;
  }
  else
  {
    s->println(eventMode);
  }
}

void newTimeConstant(int arg_cnt, char **args)
{
  Stream *s = cmdGetStream();

  if( arg_cnt > 1 )
  {
    float tTimeConstant = cmdStr2Float(args[1]);
    if( (tTimeConstant > 1) ) 
      timeConstant = tTimeConstant;
  }
  else
  {
    s->println(timeConstant);
  }
}

void newAmplitude(int arg_cnt, char **args)
{
  Stream *s = cmdGetStream();

  if( arg_cnt > 1 )
  {
    float tAmplitude = cmdStr2Float(args[1]);
    if( (tAmplitude <= 3300) && (tAmplitude > 0) ) eventAmplitude = tAmplitude;
  }
  else
  {
    s->println(eventAmplitude);
  }
}

void newEventLength(int arg_cnt, char **args)
{
  Stream *s = cmdGetStream();

  if( arg_cnt > 1 )
  {
    float tEventLength = cmdStr2Float(args[1]);
    if( tEventLength > 0 ) 
      minEventLength = tEventLength;
  }
  else
  {
    s->println(minEventLength);
  }
}

void setup()
{
    pinMode (testPin, OUTPUT);

    Serial.begin(230400);  
    analogReadResolution(13);  
    analogReference( EXTERNAL);
    analogWriteResolution(12);
    
    cmdInit(&Serial);
    
    Serial.print("Range Compressor V:");
    Serial.println(VERSION);

    cmdAdd("LMV", newLower);
    cmdAdd("UMV", newUpper);
    cmdAdd("EM", newEventmode);
    cmdAdd("TC", newTimeConstant);
    cmdAdd("AMP", newAmplitude);
    cmdAdd("MEL", newEventLength);

    lastMicros = micros();  
}


int16_t maxV = 0;
int16_t minV = 32000;

void loop()
{

      cmdPoll();  // check for new commands
      
      do  // wait for next sample time
      {
        newMicros = micros();
      } while( (newMicros - lastMicros) <= SAMPLEMICROS );
      digitalWriteFast(testPin, HIGH);
      lastMicros = newMicros;
     // newVal = 8192 - analogRead(adcPin);  // need to invert since we use inverting opamp on input
      newVal = analogRead(adcPin);

      float fout = (newVal * mvPerCnt) - zeroMv; // convert to mV and sub out zero offset

//  Serial.print(newVal);
//  Serial.print(" ");
//  Serial.println(fout);
  
      if( fout > limitHighMv ) fout = limitHighMv;  // bound output to limits
      if( fout < limitLowMv  ) fout = limitLowMv;

      // map mV out to output range which extends from low to high limit
      int16_t outVal = (int16_t)((fout - limitLowMv) * 4096 / (limitHighMv - limitLowMv));
      // be sure we are in DAC's range
      if( outVal < 0 ) outVal = 0;
      if( outVal > 4095) outVal = 4095;

      analogWrite(A22, outVal); //

      if( newVal > maxV ) 
         maxV = newVal;
      else if( newVal < minV ) 
         minV = newVal;
         
    //  Serial.println(newVal);
 
      digitalWriteFast(testPin, LOW);

//   Serial.print(minV);
//   Serial.print(" ");
//   Serial.println(maxV);
//   


}
