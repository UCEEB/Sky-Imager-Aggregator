## LibrforPiV2
# @package   LibrforPiV2
# @details   Library includes all the functions needed for the RaspberryPi
# @version   2.0
# @author   Jan Havrlant and Barbara Stefanovska
#  

import requests
import hashlib, hmac
import json
import base64
import numpy as np
import cv2
import datetime as dt
import os

from astral import Astral, Location
import configparser
import logging 
import csv
import socket


## Apply mask to the image
#OpenCV loads the images as multi-dimensional NumPy arrays but in reverse order:
# The mask is previously created in matlab in the format bmp or png
# @note Image and mask must have same dimension
# @param[in] image source image in which we apply the mask
# @param[in] mask_path path to black and white mask
# @return return masked image
def maskImg(image,mask_path):
    
    mask = cv2.imread(mask_path)/255

    return np.multiply(mask,image)

## Calculate keyed - hash for communication authentication
# @param[in] message text string to be hashed
# @param[in] key hash key
# @return hash
def hmac_sha256(message, key):

    return hmac.new(key,bytes(message,"ascii"), digestmod=hashlib.sha256).hexdigest()

## Sends POST request
# @param[in] url destination url
# @param[in] data sending data
# @return return response object
def http(url, data):
    postdata = {
        "data": data
    }
    
    return requests.post(url, data=postdata)

## Functon prepares and sends data to server.
# Data send in JSON format
# @param[in] image masked image intended for sending
# @param[in] file_time image file time
# @param[in] server remote server url
# @return respose of server
def upload_json(image,file_time,server, conf):

    skyimage = base64.b64encode(image).decode('ascii')
    dateString = file_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")


    id = conf.id # = 72
    key=conf.key #= b"cuFo4Fx2PHQduNrE7TeKVFhVXXcyvHLufQZum0RkX8yGSK9naZptuvqz2zaHi1s0"

    data = {
        "status": "ok",
        "id": id,
        "time": dateString,
        "coding": "Base64",
        "data": skyimage
         }
    jsondata = json.dumps(data)
    signature = hmac_sha256(jsondata, key)

    url =  server + signature
    
    response = http(url, jsondata)
    try:
        json_response=json.loads(response.text)
    except Exception as e:
        raise Exception(response)

    if json_response['status']!='ok':
        raise Exception(json_response['message'])           
    return json_response

def upload_bson(image,file_time,server,conf):

    #skyimage = base64.b64encode(image).decode('ascii')
    dateString = file_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")


    id = conf.id
    key = conf.key 

    data = {
        "status": "ok",
        "id": id,
        "time": dateString,
        "coding": "none",
        #"data": image.tostring()
         }
    jsondata = json.dumps(data)
    signature = hmac_sha256(jsondata, key)
    #signature=hmac.new(key,jsondata, digestmod=hashlib.sha256).hexdigest()


    
    #response = http(url, bsondata)
    if isinstance(image, str) or isinstance(image, bytes):
        files = [('image', image), ('json',jsondata)]
    else:
        files = [('image', image.tostring()), ('json',jsondata)]
    #postdata = {
    #    "data": data
    #}
    
    response=requests.post(server + signature, files=files)
    try:
        json_response=json.loads(response.text)
    except Exception as e:
        raise Exception(response)

    if json_response['status']!='ok':
        raise Exception(json_response['message'])           
    return json_response



## Functon calculates sunrise and sunset
# @param[in] camera_latitude camera position - latitude
# @param[in] camera_longitude camera position - longitude
# @param[in] camera_altitude camera position - altitude
# @param[in] print_time unused
# @param[in] date day in which sunrise und sunset calculates
# @return sunrise and sunset datetime
def get_SunR_SunS(camera_latitude,camera_longitude,camera_altitude,print_time,date=dt.datetime.now(dt.timezone.utc).date() ):
    a = Astral()
    a.solar_depression = 'civil'
    l = Location(('custom', 'region', camera_latitude, camera_longitude, "UTC", camera_altitude))    
    #date = dt.datetime.now(dt.timezone.utc)
    #now = dt.datetime(2019,2,6,16,20,0,0,dt.timezone.utc)
    try:
        sun = l.sun(date=date)
    except Exception as e:
        return dt.datetime.combine(date,  dt.time(3,0,0,0,dt.timezone.utc)),dt.datetime.combine(date,  dt.time(21,0,0,0,dt.timezone.utc))
    return sun['sunrise'], sun['sunset']

## Functon saves image to local storage
# @param[in] img image object to save
# @param[in] path1 path to local storage
# @param[in] path2 path to alternative local storage
# @param[in] name name of saved image
# @param[in] logger logger object
def save_to_storage(img,conf,name,logger):
    path=get_path_to_storage(conf)
    if conf.autonomous_mode:
        try:
            img.tofile(path+'/'+name)
        except Exception as e:
            logger.error('save to local storage error : '+str(e))
        else:
            logger.info('image '+path+'/'+name+' saved to storage' )
            return
        
    try:
        img.tofile(conf.path_storage+'/'+name)
    except Exception as e:
        logger.error('save to local storage error : '+str(e))
    else:
        logger.info('image '+conf.path_storage+'/'+name+' saved to storage' )

## class consist of configuration variables of application that are read from config.ini
class config_obj:
    def __init__(self,path_config,logger):

        config = configparser.ConfigParser()
   
        try:
            self.counter=-1
            config.read(path_config)

            self.cap_url = config.get('SETTING','cap_url')
            self.path_storage = config.get('SETTING','path_storage')

            self.server = config.get('SETTING','upload_server')
            self.log_path = config.get('SETTING','log_path')
            self.log_to_console=config.getboolean('SETTING','log_to_console')
            self.upload_format=config.get('SETTING','upload_format')
            self.camera_latitude=config.getfloat('SETTING','camera_latitude')
            self.camera_longitude=config.getfloat('SETTING','camera_longitude')
            self.camera_altitude=config.getfloat('SETTING','camera_altitude')
            self.debug_mode=config.getboolean('SETTING','debug_mode')
            self.filetime_format=config.get('SETTING','filetime_format')
            self.image_quality=config.getint('SETTING','image_quality')
            self.crop= [int(x) for x in config.get('SETTING','crop').split(",")] #map(int, config.get('SETTING','crop').split(","))
            self.mask_path=config.get('SETTING','mask_path')
            self.cap_mod=config.getint('SETTING','cap_mod')
            self.added_time=config.getint('SETTING','added_time')
            self.id=config.get('SETTING','camera_id')
            self.key=bytes(config.get('SETTING','sha256_key'),"ascii")

            self.autonomous_mode=config.getboolean('SETTING','autonomous_mode')
            self.light_sensor=config.getboolean('SETTING','light_sensor')
            if self.autonomous_mode:
                self.GSM_path_storage_usb1 = config.get('GSM','path_storage_usb1')
                self.GSM_path_storage_usb2 = config.get('GSM','path_storage_usb2')
                self.GSM_port = config.get('GSM','port')
                self.GSM_phone_no = config.get('GSM','phone_no')
                self.GSM_send_thumbnail=config.getboolean('GSM','send_thumbnail')
                self.GSM_thumbnail_size=config.getint('GSM','thumbnail_size')
                self.GSM_thumbnail_upload_server=config.get('GSM','thumbnail_upload_server')
                self.GSM_thumbnail_upload_time_interval=config.getint('GSM','thumbnail_upload_time_interval')
                self.GSM_time_sync=config.getboolean('GSM','time_sync')
                self.GSM_send_log=config.getboolean('GSM','send_log')
                self.GSM_log_upload_server=config.get('GSM','log_upload_server')
                self.GSM_ppp_config_file=config.get('GSM','ppp_config_file')

            if self.light_sensor:
                self.MODBUS_port = config.get('MODBUS','port')
                self.MODBUS_log_temperature = config.getboolean('MODBUS','log_temperature')
                self.MODBUS_sensor_address = config.getint('MODBUS','sensor_address')
                self.MODBUS_baudrate = config.getint('MODBUS','baudrate')
                self.MODBUS_bytesize = config.getint('MODBUS','bytesize')
                self.MODBUS_parity = config.get('MODBUS','parity')
                self.MODBUS_stopbits = config.getint('MODBUS','stopbits')
                self.MODBUS_csv_name = config.get('MODBUS','csv_name')

        except Exception as e:
            logger.critical('config file error : '+str(e))
            return 
        
        
## Function creates and initializes logging
# @param[in] log_level level of logger
# @return logger object and console logger
def set_logger(log_level):
    logger = logging.getLogger('myapp')
    console_logger=logging.StreamHandler()
    logger.addHandler(console_logger) #logging to console
    logger.setLevel(log_level )
    logger.info("Running program...")
    return logger,console_logger

## Function sets logging to file for given day
# @param[in] log_path path to log files storage
# @param[in] log_to_console boolen value to remove log to console
# @param[in] logger logger object
# @param[in] console_logger console logger handler
# @return  logging.FileHandler
def set_log_to_file(log_path,log_to_console,logger,console_logger):    
    try:
        hdlr = logging.FileHandler(log_path+'/'+str(dt.date.today())+'.log')
        hdlr.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(hdlr) 
    except Exception as e:
        logger.error('log file error : '+str(e))
        return
    
    if not log_to_console:
        logger.removeHandler(console_logger) #disable console logging
    return hdlr

## Function creates new log file which is unique for every day
# @param[in] log_path path to log files storage
# @param[in] logger logger object
# @param[in] hdlr old logging.FileHandler
# @return new logging.FileHandler
def set_log_to_file_new_day(log_path,logger,hdlr):  
    logger.removeHandler(hdlr)
    try:
        hdlr = logging.FileHandler(log_path+'/'+str(dt.date.today())+'.log')
        hdlr.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(hdlr) 
    except Exception as e:
        logger.error('log file error : '+str(e))
    return hdlr

def get_path_to_storage(conf):
    path=conf.path_storage
    if conf.autonomous_mode:
        if  os.access(conf.GSM_path_storage_usb1,os.W_OK):
            path=conf.GSM_path_storage_usb1
        elif os.access(conf.GSM_path_storage_usb2,os.W_OK):
            path=conf.GSM_path_storage_usb2
    return path


def save_irradiance_csv(conf,time,irradinace ,ext_temperature,cell_temperature,logger):
    path=get_path_to_storage(conf)
    try:
        f=open(path+'/'+conf.MODBUS_csv_name, 'a',newline='')
        csvFile = csv.writer(f, delimiter=';', quotechar='\'', quoting=csv.QUOTE_MINIMAL)
        if conf.MODBUS_log_temperature:
            csvFile.writerow([time,irradinace ,ext_temperature,cell_temperature]) 
        else:
            csvFile.writerow([time,irradinace ]) 
        f.close()
    except Exception as e:
        logger.error('csv save to local storage error : '+str(e))
    else:
        logger.debug('csv row saved in'+path+'/'+conf.MODBUS_csv_name )
        logger.info('irradiance saved '+str(irradinace))

def get_freespace_storage(conf):
    path=get_path_to_storage(conf)
    info=os.statvfs(path)
    freespace=info.f_bsize*info.f_bfree/1048576
    return '%.0f MB' % freespace

def test_internet_connection(logger,host="8.8.8.8", port=53, timeout=3):
  """
  Host: 8.8.8.8 (google-public-dns-a.google.com)
  OpenPort: 53/tcp
  Service: domain (DNS/TCP)
  """
  try:
    socket.setdefaulttimeout(timeout)
    socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
    return True
  except Exception as e:
    logger.error('no internet connection : '+str(e))
    return False

