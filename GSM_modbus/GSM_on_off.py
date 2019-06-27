#!/usr/bin/python3
# Filename: text.py
import serial
import time
import RPi.GPIO as GPIO

#send sms_text to phone_num
#port is ttyS0 or ttySMS0 
def get_GSM_state(port):
	ser = serial.Serial("/dev/"+port,115200)      #inicialize
	W_buff = b"AT\r\n"
	#print('send data')
	ser.write(W_buff)
	time.sleep(0.5)
	r=ser.read(ser.inWaiting())	
	if ser != None:
		ser.close()
	if r.find(b'OK')!= -1:
		return True
	return False

def GSM_switch():
	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(7, GPIO.OUT)
	GPIO.output(7, GPIO.LOW)
	time.sleep(2)
	GPIO.output(7, GPIO.HIGH)	
	GPIO.cleanup()
	time.sleep(1)


def GSM_switch_on(port):
	if get_GSM_state(port)==True:
		return True
	GSM_switch()
	if get_GSM_state(port)==True:
		return True
	else:
		return False

def GSM_switch_off(port):
	if get_GSM_state(port)==False:
		return True
	GSM_switch()
	if get_GSM_state(port)==False:
		return True
	else:
		return False
	
	        
if __name__ == '__main__':
    d=GSM_switch_on('ttyUSB0')
    print(d)