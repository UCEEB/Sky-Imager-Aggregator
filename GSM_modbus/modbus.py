#!/usr/bin/env python3
import minimalmodbus1
import serial
import time
minimalmodbus1.BAUDRATE
def get_data_irradiance(port,address,baudrate ,bytesize ,parity,stopbits  ):
    #slaveaddress,port,baudrate ,bytesize ,parity,stopbits,rtscts,dsrdtr
    #instrument = minimalmodbus1.Instrument(port, address,baudrate=baudrate ,bytesize ,parity,stopbits) # port name, slave address (in decimal)
    #def __init__(self, slaveaddress,port,baudrate ,bytesize ,parity,stopbits,rtscts,dsrdtr, mode=MODE_RTU):
    instrument = minimalmodbus1.Instrument(address,port ,baudrate,bytesize,parity,stopbits,False,False) # port name, slave address (in decimal)

    #instrument.debug = True
    irradinace = instrument.read_register(0,1, 4,False)
    ext_temperature = instrument.read_register(8,1, 4,True)
    cell_temperature =instrument.read_register(7,1, 4,True)
    return irradinace , ext_temperature, cell_temperature



if __name__ == '__main__':
    while True:
      try:
        irradinace ,ext_temperature,cell_temperature =get_data_irradiance('COM4',11,19200 ,8,'E',1)
        print ('irrad:', irradinace )
        print ('temp:',ext_temperature)
        print ('cell_temp:',cell_temperature )
      except Exception as e:
        print( "Exception " +str(e))
      #time.sleep(3)
