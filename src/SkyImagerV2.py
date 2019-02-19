# Author: Barbara Stefanovska and Jan Havrlant
#todo
#optimalize daytime test

#import time
import LibrforPiV2 as lfp
#import os
import cv2
import datetime as dt
#import sys
import configparser 
import logging 
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

def get_job_parametr(job):
    paremetr=''
    paremetr+='name '+job.name+' start time '+str(job.trigger.start_date)+' end time '+str(job.trigger.end_date)+' '+str(job.trigger)
    return paremetr

def add_Image_job(sched,conf,logger,date=dt.datetime.now(dt.timezone.utc).date()):
    
    sunrise, sunset = lfp.get_SunR_SunS(conf.camera_latitude,conf.camera_longitude,conf.camera_altitude,conf.debug_mode,date)
    if( dt.datetime.now(dt.timezone.utc)>sunset):
        date =dt.date.today() + dt.timedelta(days=1)
        sunrise, sunset = lfp.get_SunR_SunS(conf.camera_latitude,conf.camera_longitude,conf.camera_altitude,conf.debug_mode,date)
    sunrise-=dt.timedelta(minutes=conf.added_time);
    sunset+=dt.timedelta(minutes=conf.added_time);
    sched.add_job(processImage, 'cron',[sched,conf,logger], second ='*/'+conf.cap_mod,start_date =sunrise,end_date =sunset,name=str(date))
    ls=sched.get_jobs()
    logger.info('add job '+get_job_parametr(ls[len(ls)-1]))

def processImage(sched,conf,logger):
    #inicialize camera
    cap = cv2.VideoCapture(conf.cap_url) # OpenCV functions don't throw errors, they print out a message, there are some errors that can't be caught
    if cap.isOpened() != True:
        logger.error('camera connection error ')
        return

    image_time=dt.datetime.now()

    # Opening camera feed:
    logger.info("Download image from camera")
    ret, frame = cap.read()
    if cap.isOpened():
        # Resizing in case of wrong dimensions:
        #image = frame[41:1967,331:2257]
        image = frame[conf.crop[1]:conf.crop[1]+conf.crop[3],conf.crop[0]:conf.crop[0]+conf.crop[2]] 
        # Masking image :
        image = lfp.maskImg(image,conf.mask_path)        
        #encode image to jpeg image format
        is_success, buffer = cv2.imencode(".jpg", image,[int(cv2.IMWRITE_JPEG_QUALITY), conf.image_quality])

        success = True
        try:
            #try upload image to server
            response=lfp.upload_json(buffer,image_time,conf.server) 
        except Exception as e:
            logger.error('upload to server error : '+str(e))
            success=False
        if success==False or conf.debug_mode==True:
            #save image to storage
            lfp.save_to_storage(buffer,conf.path_storage,image_time.strftime(conf.filetime_format),logger)

        if success==True:
            logger.info('upload to server OK' ) 
    else:        
        logger.error('Camera unavailable. -> Possible solution: Reboot RaspberryPi with "sudo reboot" \n')
    ls=sched.get_jobs()
    if(len(ls)==0):
        date =dt.date.today() + dt.timedelta(days=1)
        add_Image_job(sched,conf,logger,date)
        logger.info('added new job for '+str(date)) 
    return



def control_job(sched,conf,logger):
    conf.log_file_handler = lfp.set_log_to_file_new_day(conf.log_path,logger,conf.log_file_handler)
    ls=sched.get_jobs()
    logger.info('run control job '+str(dt.date.today()))
    if(len(ls)==0):
        add_Image_job(sched,conf,logger)
        logger.error('some problem, I must add extra job for '+str(dt.date.today()))
        

def main():

    #inicialize logging
    logger,console_logger=lfp.set_logger(logging.DEBUG)
    

    # read config file
    path_config = os.path.dirname(os.path.realpath(__file__))+'/config.ini' 
    conf = lfp.config_obj(path_config,logger)

    #inicialize log to file
    conf.log_file_handler= lfp.set_log_to_file(conf.log_path,conf.log_to_console,logger,console_logger)


    sched = BlockingScheduler()
    

    sched1 = BackgroundScheduler()
    sched1.add_job(control_job, 'cron',[sched,conf,logger], hour ='*', minute ='30',second ='5')
    sched1.start()
    
   
    add_Image_job(sched,conf,logger)
    sched.start()


if __name__ == '__main__':
    #sys.stdout.write("Running program...")
    main()
