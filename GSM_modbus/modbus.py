#!/usr/bin/env python3
import minimalmodbus
import serial
import time

def get_data_irradiance(port,address,baudrate ,bytesize ,parity,stopbits  ):
	instrument = minimalmodbus.Instrument('/dev/'+port, 11) # port name, slave address (in decimal)
	#instrument.debug = True
	instrument.serial.baudrate = baudrate 
	instrument.serial.bytesize = bytesize 
	instrument.serial.parity = parity
	instrument.serial.stopbits = stopbits
	instrument.serial.timeout  = 0.1   # seconds

	irradinace = instrument.read_register(0,1, 4,False)
	ext_temperature = instrument.read_register(8,1, 4,True)
	cell_temperature =instrument.read_register(7,1, 4,True)
	return irradinace , ext_temperature, cell_temperature



if __name__ == '__main__':
	while True:
		irradinace ,ext_temperature,cell_temperature =get_data_irradiance('ttyAMA0',11,19200 ,8,'E',1)
		print ('irrad:', irradinace )
		print ('temp:',ext_temperature)
		print ('cell_temp:',cell_temperature )
		time.sleep(3)
