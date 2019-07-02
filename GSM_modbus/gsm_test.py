import LibrforPiV2 as lfp
import cv2
import datetime as dt
import configparser 
import logging 
import os
import GSM_modbus 
import threading

SMS_text="SkyImg end, df "

#GSM_modbus.sentSMS('608643XXX',SMS_text,'/dev/ttyUSB0')
 #inicialize logging
logger,console_logger=lfp.set_logger(logging.DEBUG)
    

# read config file
path_config = os.path.dirname(os.path.realpath(__file__))+'/config.ini' 
conf = lfp.config_obj(path_config,logger)

#inicialize log to file
conf.log_file_handler= lfp.set_log_to_file(conf.log_path,conf.log_to_console,logger,console_logger)


#thread = threading.Thread(target=GSM_modbus.GSM_worker,args=(conf,logger))
#thread.start()
#GSM_modbus.qu.put(GSM_modbus.C_send_log(logger,conf,gzip.compress(str.encode("pokus"))))
#GSM_modbus.qu.put(GSM_modbus.C_sleep(logger,conf.GSM_port))

#conf.counter=0
#while True:
#    GSM_modbus.enable_internet(conf.GSM_port,logger,conf.GSM_ppp_config_file)
#    GSM_modbus.disable_internet(logger)
#SkyImagerV2.processImage(5,conf,logger)
#GSM_modbus.synch_time(conf.GSM_port,logger,conf.GSM_ppp_config_file)

#GSM_modbus.sentSMS(conf.GSM_phone_no,SMS_text,conf.GSM_port)
irradinace ,ext_temperature,cell_temperature =GSM_modbus.get_data_irradiance(conf.MODBUS_port,conf.MODBUS_sensor_address,conf.MODBUS_baudrate ,conf.MODBUS_bytesize,conf.MODBUS_parity,conf.MODBUS_stopbits,logger)
            