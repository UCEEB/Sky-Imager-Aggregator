#!/usr/bin/env python
# serial_port_loopback.py
# Will also work on Python3.
# Serial port testing for a RaspberryPi.

from __future__ import print_function
import serial
import time
#test_string = '\x0b\x03\x00\x00\x00\x01\x84\xa0'.encode('utf-8')
test_string = b'\x0b\x04\x00\x00\x00\x02\x71\x61' ### Will also work
#test_string = b'\x0b\x08\x00\x00\x00\x01\x21\x61' ### Will also work


port_listU = [ "/dev/ttyUSB0"]
port_list = [ "/dev/ttyAMA0"]

while True:

    try:
        serialPortU = serial.Serial("/dev/ttyAMA0", 19200, timeout = 2,parity=serial.PARITY_EVEN)
        serialPortA = serial.Serial("/dev/ttyUSB0", 19200, timeout = 2,parity=serial.PARITY_EVEN)
        
        serialPortA.flushInput()
        serialPortA.flushOutput()
        serialPortU.flushInput()
        serialPortU.flushOutput() 

        print("Opened port for testing:")
        bytes_sent = serialPortU.write(test_string)
        print ("Sent", bytes_sent, "bytes ",test_string.encode("hex"))
        time.sleep(0.1)

        loopback = serialPortU.read(bytes_sent)
        print ("Received data", loopback.encode("hex"), "over Serial port\n")
        serialPortU.close()
    except IOError:
        print ("Failed at", port, "\n")

