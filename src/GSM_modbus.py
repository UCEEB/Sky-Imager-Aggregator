#!/usr/bin/python3
# Filename: text.py

import time
import os
import LibrforPiV2 as lfp
import subprocess
import threading
import queue
import datetime as dt
import logging
import gzip
if os.name != 'nt':
    import serial
    import RPi.GPIO as GPIO
    import minimalmodbus


#send sms_text to phone_num
#port is dev/ttyS0 or dev/ttySMS0 
def _get_GSM_state(port,logger):
    logger.debug('test modem state')
    _disable_ppp(logger)
    time.sleep(1)
    try:
        ser = serial.Serial(port,115200)      #inicialize
    except Exception as e:
        logger.error('serial port error: '+str(e))
        return False
    W_buff = b"AT\r\n"
    #print('send data')
    ser.write(W_buff)
    time.sleep(0.5)
    r=ser.read(ser.inWaiting())	
    if ser != None:
        ser.close()
    if r.find(b'OK')!= -1:
        logger.debug('modem is On ')
        return True
    logger.debug('modem is Off '+str(r))
    return False

def _GSM_switch(logger):
    
    logger.debug("switching modem")
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(12, GPIO.OUT)
    GPIO.output(12, GPIO.LOW)
    time.sleep(3)
    GPIO.output(12, GPIO.HIGH)	
    #GPIO.cleanup() #pin must leave set as outpot and not reset to input



def _GSM_switch_on(port,logger):
    logger.debug('switch modem ON')
    if _get_GSM_state(port,logger)==True:
        return True
    count=0
    while True:
        _GSM_switch(logger)
        time.sleep(12)
        count=count+1
        if _get_GSM_state(port,logger)==True:
            return True
        if count>3:
            logger.error('Error switch modem ON')
            return False
    return False

def _GSM_switch_off(port,logger):
    logger.debug('switch modem OFF')
    if _get_GSM_state(port,logger)==False:
        return True
    _GSM_switch(logger)
    if _get_GSM_state(port,logger)==False:
        return True
    else:
        return False

def _sendSMS(phone_num,SMS_text,port,logger):
    _disable_internet(logger)
    _GSM_switch_on(port,logger)
    ser = serial.Serial(port,115200)      #inicializace
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
        data1 = ser.read(ser.inWaiting())
    except Exception as e:
        if ser != None:
            ser.close()
        return "Exception " +str(e)
    return data1

def get_data_irradiance(port,address,baudrate ,bytesize ,parity,stopbits  ):
    instrument = minimalmodbus.Instrument(port, address) # port name, slave address (in decimal)
    #instrument.debug = True
    instrument.serial.baudrate = baudrate 
    instrument.serial.bytesize = bytesize 
    instrument.serial.parity = parity
    instrument.serial.stopbits = stopbits
    instrument.serial.timeout  = 0.1   # seconds
    time.sleep(0.5)
    irradinace = instrument.read_register(0,1, 4,False)
    ext_temperature = instrument.read_register(8,1, 4,True)
    cell_temperature =instrument.read_register(7,1, 4,True)
    return irradinace , ext_temperature, cell_temperature

def _test_ppp():
    proc = subprocess.Popen(["ifconfig"], stdout=subprocess.PIPE)
    (out, err) = proc.communicate()
    if out.find(b'ppp0')!=-1:
        return True
    return False


def _wait_for_start(logger,timeout):
    pipe_path = "/tmp/pppipe"
    if not os.path.exists(pipe_path):
        os.mkfifo(pipe_path)
    # Open the fifo. We need to open in non-blocking mode or it will stalls until
    # someone opens it for writting
    pipe_fd = os.open(pipe_path, os.O_RDONLY | os.O_NONBLOCK)
    count=0
    with os.fdopen(pipe_fd) as pipe:
        while True:
            count=count+1
            try:
                message = pipe.read()
            
                if message.find('UP')!= -1:
                    logger.debug('ppp UP')
                    return True

            except Exception as e:
                logger.info('error' +str(e))
                return False
            time.sleep(0.5)
            logger.debug('wait')
            if count>timeout:
                break
    return False


def _enable_ppp(port,logger,GSM_ppp_config_file):
    if _GSM_switch_on(port,logger)==False:
        logger.error('GSM modem not switch on')
        return False
    _disable_ppp(logger)
    time.sleep(1)
    logger.debug('sudo pppd call ')
    os.system('sudo pppd call '+GSM_ppp_config_file)
    
    logger.debug('start ppp')
    if _wait_for_start(logger,100)==False:
        logger.error('no ppp enabled')
        return False


    os.system('sudo ip route add default dev ppp0 2>null')
    time.sleep(1)
    count=0
    while True:
        if _test_ppp_pr():
            return True
        else:
            count=count+1
            time.sleep(2)
        if count>10:
            break
           
    logger.error('no ppp enabled')
    return False


def _test_ppp_pr():
    if os.system('ps -A|grep pppd >null')==0:
        return True
    return False

def _disable_ppp(logger):
    logger.debug('disabling ppp')
    os.system('sudo killall pppd 2>null')
    time.sleep(1)


def _enable_internet(port,logger,GSM_ppp_config_file):
    if lfp.test_internet_connection(logger)==True:
            logger.debug('internet connection OK')
            return True
    _enable_ppp(port,logger,GSM_ppp_config_file)
    time.sleep(5)
    count=0
    while True:
        if lfp.test_internet_connection(logger)==True:
            logger.debug('internet connection OK')
            return True
            
        else:
            count=count+1
            time.sleep(2)
        if count>11:
            break
        if count==5:
            _disable_ppp(logger)
            _enable_ppp(port,logger,GSM_ppp_config_file)
        if count==9:
            _GSM_switch_off(port,logger)
            _enable_ppp(port,logger,GSM_ppp_config_file)
           
    logger.error('No internet connection')
    return False

def _disable_internet(logger):
    _disable_ppp(logger)

def synch_time(port,logger,GSM_ppp_config_file):
    #_disable_ppp()
    if _enable_internet(port,logger,GSM_ppp_config_file)==False:
        #disable_internet(logger)
        return False
    count=0
    while True:
        logger.debug('try time sync')
        if os.system('sudo ntpdate -u tik.cesnet.cz')==0:
            logger.info('time sync OK')
            break
        else:
            count=count+1
            time.sleep(1)
        if count>10:
            logger.error('time sync error')
            break
    #disable_internet(logger)
    
def _upload_thumbnail(logger,conf,image,image_time):

    logger.debug('start upload thumbnail to server' )
    count=0
    while True:
        count=count+1
        _enable_internet(conf.GSM_port,logger,conf.GSM_ppp_config_file)
        try:
            #attempt to send an image to the server
            response=lfp.upload_bson(image,image_time,conf.GSM_thumbnail_upload_server,conf) 
            logger.info('upload thumbnail to server OK' )
            
            #disable_internet(logger)
            return
        except Exception as e:
            logger.error('upload thumbnail to server error : '+str(e))
             
    
        #disable_internet(logger)
        if count>5:
            logger.error('error upload thumbnail to server' ) 
            break
    
    logger.debug('end upload thumbnail to server' ) 

def _upload_logfile(logger,conf,log):

    logger.debug('start upload log to server' )
    count=0
    while True:
        count=count+1
        _enable_internet(conf.GSM_port,logger,conf.GSM_ppp_config_file)
        try:
            #attempt to send an image to the server
            response=lfp.upload_bson(log,dt.datetime.utcnow(),conf.GSM_log_upload_server,conf) 
            logger.info('upload log to server OK' )
            
            #disable_internet(logger)
            return
        except Exception as e:
            logger.error('upload log to server error : '+str(e))
             
    
        #disable_internet(logger)
        if count>5:
            logger.error('error upload log to server' ) 
            break
    
    logger.debug('end upload log to server' ) 


def GSM_worker(logger,conf):

    while True:

        item = qu.get() #block  until an item is available
        item.exec()
        qu.task_done()



qu = queue.Queue()


class C_send_SMS:
    def __init__(self, phone_num,SMS_text,port,logger):
         self.phone_num=phone_num
         self.SMS_text=SMS_text
         self.port=port
         self.logger=logger
    def exec(self):
        re = _sendSMS(self.phone_num,self.SMS_text,self.port,self.logger)
        self.logger.debug('Send SMS return'+re.decode("ascii") )
        
        

class C_send_thumbnail:
    def __init__(self,logger,conf,image,image_time):
        self.logger=logger
        self.conf=conf
        self.image=image
        self.image_time=image_time
    def exec(self):
        _upload_thumbnail(self.logger,self.conf,self.image,self.image_time)

class C_synch_time:
    def __init__(self, port,logger,GSM_ppp_config_file):
        self.port=port
        self.logger=logger
        self.GSM_ppp_config_file=GSM_ppp_config_file
    def exec(self):
        synch_time(self.port,self.logger,self.GSM_ppp_config_file)

class C_send_log:
    def __init__(self,logger,conf,log):
        self.logger=logger
        self.conf=conf
        self.log=log

    def exec(self):
        _upload_logfile(self.logger,self.conf,self.log)

class C_sleep:
    def __init__(self,logger,port):
        self.logger=logger
        self.port=port

    def exec(self):
        _GSM_switch_off(self.port,self.logger)

class TailLogHandler(logging.Handler):

    def __init__(self, log_queue,logger,conf):
        logging.Handler.__init__(self)
        self.store=""
        self.count=0
        self.log_queue=log_queue
        self.logger=logger
        self.conf=conf

    def emit(self, record):
        self.store=self.store+self.format(record)+'\n'
        self.count=self.count+1
        if self.count>=self.log_queue:
            self.send_to_server()

    def send_to_server(self):
        if self.count>0:
            self.count=0
            qu.put(C_send_log(self.logger,self.conf,gzip.compress(str.encode(self.store))))
            self.store=""

