# Author: Barbara Stefanovska 
# ...
# This library includes all the functions needed for the RaspberryPi
import cv2
import numpy as np
import datetime as dt
import base64
import json
import hashlib, hmac
import requests
from astral import Astral, Location
import configparser
import logging 



def maskImg(image,mask_path):
    # OpenCV loads the images as multi-dimensional NumPy arrays but in reverse order: We need to convert BGR to RGB
    # The mask is previously created in matlab in the format bmp
    mask = cv2.imread(mask_path)/255

    return np.multiply(mask,image)


def hmac_sha256(message, key):
    #messageBytes = bytes(message).encode('utf-8')
    #keyBytes = bytes(key).encode('utf-8')
    return hmac.new(key,bytes(message,"ascii"), digestmod=hashlib.sha256).hexdigest()

def http(url, data):
    postdata = {
        "data": data
    }
    
    return requests.post(url, data=postdata)

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

    
    ###############################################################################

def is_daytime(camera_latitude,camera_longitude,camera_altitude,print_time ):
    a = Astral()
    a.solar_depression = 'civil'
    l = Location(('custom', 'region', camera_latitude, camera_longitude, "UTC", camera_altitude))    
    now = dt.datetime.now(dt.timezone.utc)
    #now = dt.datetime(2019,2,6,16,20,0,0,dt.timezone.utc)
    sun = l.sun(date=now.date())
    if print_time:
        print('sunrise '+str(sun['sunrise'])+"  sunset "+str(sun['sunset'])+"UTC\n")
    if(sun['sunrise']<now and sun['sunset']>now):
       return True
    return False

#unused
def get_SunR_SunS(camera_latitude,camera_longitude,camera_altitude,print_time,date=dt.datetime.now(dt.timezone.utc).date() ):
    a = Astral()
    a.solar_depression = 'civil'
    l = Location(('custom', 'region', camera_latitude, camera_longitude, "UTC", camera_altitude))    
    #date = dt.datetime.now(dt.timezone.utc)
    #now = dt.datetime(2019,2,6,16,20,0,0,dt.timezone.utc)
    sun = l.sun(date=date)
    return sun['sunrise'], sun['sunset']

def save_to_storage(img,path,name,logger):
    try:
        img.tofile(path+'/'+name)
    except Exception as e:
        logger.error('save to local storage error : '+str(e))
    else:
        logger.info('image '+path+'/'+name+' saved to storage' )


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

            
            '''unused
            sunrise=config.get('SETTING','today_sunrise')
            sunset=config.get('SETTING','today_sunset')
            new_value=False
            try:
                self.sunrise=dt.datetime.strptime(sunrise,'%Y-%m-%d %H:%M:%S%z')
                self.sunset=dt.datetime.strptime(sunset,'%Y-%m-%d %H:%M:%S%z')
            except Exception as e:
               self.sunrise, self.sunset = get_SunR_SunS(self.camera_latitude,self.camera_longitude,self.camera_altitude,self.debug_mode)
               new_value=True
            else:
                if(self.sunrise.date()!=dt.datetime.now(dt.timezone.utc).date()):
                    self.sunrise, self.sunset = get_SunR_SunS(self.camera_latitude,self.camera_longitude,self.camera_altitude,self.debug_mode)
                    new_value=True
            if(new_value):
                config.set('SETTING','today_sunrise',dt.datetime.strftime( self.sunrise,'%Y-%m-%d %H:%M:%S%z'))
                config.set('SETTING','today_sunset',dt.datetime.strftime( self.sunset,'%Y-%m-%d %H:%M:%S%z'))
            '''
                #with open(path_config, 'w') as configfile:    # save
                #    config.write(configfile)


        except Exception as e:
            logger.critical('config file error : '+str(e))
            return 
        
        
def set_logger(log_level):
    logger = logging.getLogger('myapp')
    console_logger=logging.StreamHandler()
    logger.addHandler(console_logger) #logging to console
    logger.setLevel(log_level )
    logger.info("Running program...")
    return logger,console_logger

def set_log_to_file(log_path,log_to_console,logger,console_logger):    
    try:
        hdlr = logging.FileHandler(log_path+'/'+str(dt.date.today())+'.log')
        hdlr.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(hdlr) 
    except Exception as e:
        logger.error('log file error : '+str(e))
    
    if not log_to_console:
            logger.removeHandler(console_logger)#disable console logging
    return hdlr


def set_log_to_file_new_day(log_path,logger,hdlr):  
    logger.removeHandler(hdlr)
    try:
        hdlr = logging.FileHandler(log_path+'/'+str(dt.date.today())+'.log')
        hdlr.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(hdlr) 
    except Exception as e:
        logger.error('log file error : '+str(e))
    return hdlr
    

