#!/usr/bin/python3
# Filename: text.py
import serial
import time
ser = serial.Serial("/dev/ttyUSB0",115200)      #inicialize
W_buff = [b"AT\r\n", b"AT+CMGF=1\r\n", b"AT+CMGS=\"608643XXX\"\r\n",b"helloworld"]
print('send data')
print( ser.write(W_buff[0]))
time.sleep(1)
print(ser.read(ser.inWaiting()))
print('finish')
if ser != None:
	ser.close()
