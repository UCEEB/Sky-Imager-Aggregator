#!/usr/bin/python3
# Filename: text.py
import serial
import time
#send sms_text to phone_num
#port is ttyS0 or ttySMS0 
def sentSMS(phone_num,SMS_text,port):
	ser = serial.Serial("/dev/"+port,115200)      #inicializace
	W_buff = [b"AT\r\n", b"AT+CMGF=1\r\n", b"AT+CMGS=\""+phone_num.encode()+b"\"\r\n",SMS_text.encode()]
	
	ser.write(W_buff[0])
	time.sleep(0.2)
	if ser.inWaiting()==0:
		return "fail"
	data = b""
	try:   
		data += ser.read(ser.inWaiting())
		time.sleep(0.1)
		data += ser.read(ser.inWaiting())
		ser.write(W_buff[1])
		time.sleep(0.1)
		data += ser.read(ser.inWaiting())
		ser.write(W_buff[2])
		time.sleep(0.2)
		ser.write(W_buff[3])
		ser.write(b"\x1a\r\n")# 0x1a : send   0x1b : Cancel send
		time.sleep(0.2)
		data += ser.read(ser.inWaiting())      	 
	
	except KeyboardInterrupt:
		if ser != None:
			ser.close()
		return "keyb interupt"
	return data
	        
if __name__ == '__main__':
    d=sentSMS('608643071','test SMS','ttyS0')
    print(d)