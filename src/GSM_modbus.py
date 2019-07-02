## GSM modbus library
# @package   SkyImagerV1auto
# @details    Library includes the functions needed the RaspberryPi for work GSM modem and modbus irradiance sensor
#
# @version   1.0
# @author   Jan Havrlant
#  

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
    import minimalmodbus1


##check GSM modem state, if is ON or OFF
#port is dev/ttyS0 or dev/ttyUSB0 
# @param[in] port port is dev/ttyS0 or dev/ttyUSB0 or dev/ttyAMA0
# @param[in] logger logger object
# @return False if GSM modem is OFF and True if GSM modem is ON
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

##switch GSM modem by pin 
#port is dev/ttyS0 or dev/ttyUSB0 or dev/ttyAMA0
# @param[in] logger logger object
def _GSM_switch(logger):
    pin=12 #pin wchich is switch
    logger.debug("switching modem")
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(3)
    GPIO.output(pin, GPIO.HIGH)	
    #GPIO.cleanup() #pin must leave set as outpot and not reset to input


##switch GSM modem ON  
# @param[in] port port is dev/ttyS0 or dev/ttyUSB0 or dev/ttyAMA0
# @param[in] logger logger object
# @return False if GSM modem is OFF and True if GSM modem is ON
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

##switch GSM modem OFF  
# @param[in] port is dev/ttyS0 or dev/ttyUSB0 or dev/ttyAMA0
# @param[in] logger logger object
# @return False if GSM modem is ON and True if GSM modem is OFF
def _GSM_switch_off(port,logger):
    logger.debug('switch modem OFF')
    if _get_GSM_state(port,logger)==False:
        return True
    _GSM_switch(logger)
    if _get_GSM_state(port,logger)==False:
        return True
    else:
        return False

##Send SMS to phone_num
# @param[in] phone_num phone number string
# @param[in] SMS_text text to send
# @param[in] port port is dev/ttyS0 or dev/ttyUSB0 
# @param[in] logger logger object
# @return data which response GSM modem
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

##Get irradiance and temperature from Light sensor
# @param[in] port port is dev/ttyS0 or dev/ttyUSB0 
# @param[in] address modbus address
# @param[in] baudrate port baudrate
# @param[in] bytesize number of data bits
# @param[in] parity enable parity checking
# @param[in] stopbits number of stop bits
# @param[in] logger logger object
# @return irradiance, temperature of external sensor, internal temperature
def get_data_irradiance(port,address,baudrate ,bytesize ,parity,stopbits ,logger ):
    #logger.debug(str(port)+" "+str(address)+" "+str(baudrate) +" "+str(bytesize) +" "+str(parity)+" "+str(stopbits))
    #instrument = minimalmodbus.Instrument(port, address) # port name, slave address (in decimal)
    instrument = minimalmodbus1.Instrument(address,port ,baudrate,bytesize,parity,stopbits,False,True) # port name, slave address (in decimal)

    #time.sleep(0.5)
    irradinace = instrument.read_register(0,1, 4,False)
    ext_temperature = instrument.read_register(8,1, 4,True)
    cell_temperature =instrument.read_register(7,1, 4,True)

    return irradinace , ext_temperature, cell_temperature



##Function wait until start ppp connection
# to work you must add row to script /etc/ppp/ip-up
# echo "pppd UP" > /tmp/pppipe
# @param[in] logger logger object
# @param[in] timeout time to wait connection is establish
# @return True if connection is establish and False if connection is not establish until time out
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

##Function start ppp connection
# @param[in] GSM_ppp_config_file name of file in /etc/ppp/peers where is ppp configuration
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

##Test if pppd process is running
def _test_ppp_pr():
    if os.system('ps -A|grep pppd >null')==0:
        return True
    return False

##Test if pppd process is running
def _test_ppp():
    proc = subprocess.Popen(["ifconfig"], stdout=subprocess.PIPE)
    (out, err) = proc.communicate()
    if out.find(b'ppp0')!=-1:
        return True
    return False

##Disable ppp process
def _disable_ppp(logger):
    logger.debug('disabling ppp')
    os.system('sudo killall pppd 2>null')
    time.sleep(1)

##Start internet connection via GSM modem
# @param[in] GSM_ppp_config_file name of file in /etc/ppp/peers where is ppp configuration
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
##Stop internet connection via GSM modem
def _disable_internet(logger):
    _disable_ppp(logger)

##Try time synchronization
# @param[in] GSM_ppp_config_file name of file in /etc/ppp/peers where is ppp configuration
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


##Upload thumbnail to server
# @param[in] image thumbnail image
# @param[in] image_time creation time of image
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

##Upload log file to server
# @param[in] log string with uploaded log rows
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

##Processes request to GSM modem
def GSM_worker(logger,conf):

    while True:
        try:
            item = qu.get() #block  until an item is available
            logger.debug('execute command from queue')
            item.exec()
            qu.task_done()
        except Exception as e:
            logger.error('GSM worker error: '+str(e))


## queue of requests to GSM modem
qu = queue.Queue()

##Class store request to send SMS
class C_send_SMS:
    def __init__(self, phone_num,SMS_text,port,logger):
         self.phone_num=phone_num
         self.SMS_text=SMS_text
         self.port=port
         self.logger=logger
    def exec(self):
        re = _sendSMS(self.phone_num,self.SMS_text,self.port,self.logger)
        self.logger.debug('Send SMS return'+re.decode("ascii") )
        
        
##Class to store request to upload thumbnail
class C_send_thumbnail:
    def __init__(self,logger,conf,image,image_time):
        self.logger=logger
        self.conf=conf
        self.image=image
        self.image_time=image_time
    def exec(self):
        _upload_thumbnail(self.logger,self.conf,self.image,self.image_time)

##Class to store request to synchronization time
class C_synch_time:
    def __init__(self, port,logger,GSM_ppp_config_file):
        self.port=port
        self.logger=logger
        self.GSM_ppp_config_file=GSM_ppp_config_file
    def exec(self):
        synch_time(self.port,self.logger,self.GSM_ppp_config_file)

##Class to store request to upload log to server
class C_send_log:
    def __init__(self,logger,conf,log):
        self.logger=logger
        self.conf=conf
        self.log=log

    def exec(self):
        _upload_logfile(self.logger,self.conf,self.log)

##Class to store request to switch OFF modem
class C_sleep:
    def __init__(self,logger,port):
        self.logger=logger
        self.port=port

    def exec(self):
        _GSM_switch_off(self.port,self.logger)

##Class derive logging.Handler
# special logger, which store log rows and upload its to server if achieves given value of rows
class TailLogHandler(logging.Handler):

# @param[in] log_queue number of rows which is uploaded together on server
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

## upload log rows to server
    def send_to_server(self):
        if self.count>0:
            self.count=0
            qu.put(C_send_log(self.logger,self.conf,gzip.compress(str.encode(self.store))))
            self.store=""

