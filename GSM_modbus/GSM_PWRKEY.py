#!/usr/bin/python3
import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BOARD)
GPIO.setup(7, GPIO.OUT)
while True:
	GPIO.output(7, GPIO.LOW)
	time.sleep(2)
	GPIO.output(7, GPIO.HIGH)
	break
GPIO.cleanup()
