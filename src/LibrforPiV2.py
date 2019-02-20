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

from astral import Astral, Location
import configparser
import logging 


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
def upload_json(image,file_time,server):

    skyimage = base64.b64encode(image).decode('ascii')
    dateString = file_time.strftime("%Y-%m-%dT%H:%M:%S+02:00")


    id = 72
    key = b"cuFo4Fx2PHQduNrE7TeKVFhVXXcyvHLufQZum0RkX8yGSK9naZptuvqz2zaHi1s0"

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
    sun = l.sun(date=date)
    return sun['sunrise'], sun['sunset']

## Functon saves image to local storage
# @param[in] img image object to save
# @param[in] path path to local storage
# @param[in] name name of saved image
# @param[in] logger logger object
def save_to_storage(img,path,name,logger):
    try:
        img.tofile(path+'/'+name)
    except Exception as e:
        logger.error('save to local storage error : '+str(e))
    else:
        logger.info('image '+path+'/'+name+' saved to storage' )

## class consist of configuration variables of application that are read from config.ini
class config_obj:
    def __init__(self,path_config,logger):

        config = configparser.ConfigParser()
   
        try:
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
            self.cap_mod=config.get('SETTING','cap_mod')
            self.added_time=config.getint('SETTING','added_time')

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
    

