## LibrforPiV2
# @package   SkyImagerV2
# @details   Script at a given interval access the camera, get image and try to send to remote storage. 
#If there is no internet connection, script save image to local storage. These images try send to remote sotage SendStorageV2.py
# @version   2.0
# @author   Jan Havrlant and Barbara Stefanovska
#  

import LibrforPiV2 as lfp
import cv2
import datetime as dt
import configparser 
import logging 
import os
import GSM_modbus 
import threading

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

## Creates text string with information about given job for save to log file
# @param[in] job job object
# @return text string with information about job
def get_job_parametr(job):
    paremetr=''
    paremetr+='name '+job.name+' start time '+str(job.trigger.start_date)+' end time '+str(job.trigger.end_date)+' '+str(job.trigger)
    return paremetr

## functon adds job to scheduler object for given day 
# Send SMS on end of day in autonomous mode
# Job starts at sunrise and finish at sunset
# @param[in] sched apscheduler object
# @param[in] conf object with configuration
# @param[in] logger logger object
# @param[in] date date of jobs, default value is today
def add_Image_job(sched,conf,logger,date=dt.datetime.now(dt.timezone.utc).date()):
    if conf.autonomous_mode:
        if conf.thread.is_alive()==False:
            conf.thread.start()
        if conf.counter!=-1:  #end of day
            if conf.GSM_phone_no!="":
                SMS_text="SkyImg end, df "+lfp.get_freespace_storage(conf)+' saved '+str(conf.counter)+' img, time '+dt.datetime.utcnow().strftime("%y-%m-%d_%H-%M-%S")
                logger.info('Send SMS:'+SMS_text)
                GSM_modbus.qu.put(GSM_modbus.C_send_SMS(conf.GSM_phone_no,SMS_text,conf.GSM_port,logger))
                
            if conf.GSM_send_log:
                conf.log_internet.send_to_server()
            conf.counter=-1
            GSM_modbus.qu.put(GSM_modbus.C_sleep(logger,conf.GSM_port))
    sunrise, sunset = lfp.get_SunR_SunS(conf.camera_latitude,conf.camera_longitude,conf.camera_altitude,conf.debug_mode,date)
    if( dt.datetime.now(dt.timezone.utc)>sunset):
        date =dt.date.today() + dt.timedelta(days=1)
        sunrise, sunset = lfp.get_SunR_SunS(conf.camera_latitude,conf.camera_longitude,conf.camera_altitude,conf.debug_mode,date)
    sunrise-=dt.timedelta(minutes=conf.added_time);
    sunset+=dt.timedelta(minutes=conf.added_time);
    #for test
    #sunrise=dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=2);
    #sunset=dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=4);
    #for test
    sched.add_job(processImage, 'cron',[sched,conf,logger], second ='*/'+str(conf.cap_mod),start_date =sunrise,end_date =sunset,name=str(date))
    ls=sched.get_jobs()
    logger.info('add job '+get_job_parametr(ls[len(ls)-1]))
    

## owns core of the script that gets image from camera and sends to remote server
# @param[in] sched apscheduler object
# @param[in] conf object with configuration
# @param[in] logger logger object
def processImage(sched,conf,logger):
    if conf.autonomous_mode and conf.counter==-1: #start of day
        if conf.GSM_time_sync:        
                #re =GSM_modbus.synch_time(conf.GSM_port,logger,conf.GSM_ppp_config_file)
                GSM_modbus.qu.put(GSM_modbus.C_synch_time(conf.GSM_port,logger,conf.GSM_ppp_config_file))
            
        if conf.GSM_phone_no!="":
            SMS_text="SkyImg start, df "+lfp.get_freespace_storage(conf)+', time '+dt.datetime.utcnow().strftime("%y-%m-%d_%H-%M-%S")
            logger.info('Send SMS:'+SMS_text)
            GSM_modbus.qu.put(GSM_modbus.C_send_SMS(conf.GSM_phone_no,SMS_text,conf.GSM_port,logger))
                
        conf.counter=0


    image_time=dt.datetime.utcnow()
    if conf.light_sensor:
        try:
            irradinace ,ext_temperature,cell_temperature =GSM_modbus.get_data_irradiance(conf.MODBUS_port,conf.MODBUS_sensor_address,conf.MODBUS_baudrate ,conf.MODBUS_bytesize,conf.MODBUS_parity,conf.MODBUS_stopbits,logger)
            logger.debug('irradiance '+str(irradinace))
            time_csv=image_time.strftime("%y-%m-%d_%H-%M-%S")
            lfp.save_irradiance_csv(conf,time_csv,irradinace ,ext_temperature,cell_temperature,logger)
        except Exception as e:
            logger.error('unable to get data from light sensor'+str(e))

    #inicialize camera
    cap = cv2.VideoCapture(conf.cap_url) # OpenCV functions don't throw errors, they print out a message, there are some errors that can't be caught
    if cap.isOpened() != True:
        logger.error('camera connection error ')
        return

    # Opening camera feed:
    logger.debug("Download image from camera")
    ret, frame = cap.read()
    if cap.isOpened():
        # Resizing in case of wrong dimensions:
        #image = frame[41:1967,331:2257]
        image = frame[conf.crop[1]:conf.crop[1]+conf.crop[3],conf.crop[0]:conf.crop[0]+conf.crop[2]] 
        # Masking image :
        if len(conf.mask_path)>0:
            image = lfp.maskImg(image,conf.mask_path)        
        #encode image to jpeg image format
        is_success, buffer = cv2.imencode(".jpg", image,[int(cv2.IMWRITE_JPEG_QUALITY), conf.image_quality])

        success = True
        if len(conf.server)>0:
            try:
                #attempt to send an image to the server
                response=lfp.upload_json(buffer,image_time,conf.server,conf) 
            except Exception as e:
                logger.error('upload to server error : '+str(e))
                success=False
        else:
            success = False
        if success==False or conf.debug_mode==True:
            #save image to storage
            lfp.save_to_storage(buffer,conf,image_time.strftime(conf.filetime_format),logger,image_time)
            if conf.autonomous_mode:  
                conf.counter = conf.counter+1
                #send image thumbnail in given time interval
                if conf.GSM_send_thumbnail and  int(image_time.timestamp())%conf.GSM_thumbnail_upload_time_interval<conf.cap_mod:
                    logger.info("Free space: "+lfp.get_freespace_storage(conf))
                    res = cv2.resize(image, dsize=(conf.GSM_thumbnail_size, conf.GSM_thumbnail_size), interpolation=cv2.INTER_NEAREST)
                    is_success, buffer = cv2.imencode(".jpg", res,[int(cv2.IMWRITE_JPEG_QUALITY), conf.image_quality])
                    GSM_modbus.qu.put(GSM_modbus.C_send_thumbnail(logger,conf,buffer,image_time))
                    #upload_thread = threading.Thread(target=GSM_modbus.upload_thumbnail, args=(logger,conf,buffer,image_time))
                    #upload_thread.start()
                #print ("saved fo file ",conf.counter)
        if success==True:
            logger.info('upload to server OK' ) 
    else:        
        logger.error('Camera unavailable. -> Possible solution: Reboot RaspberryPi with "sudo reboot" \n')

    #check if job is scheduled, for sure
    ls=sched.get_jobs()
    if(len(ls)==0):
        date =dt.date.today() + dt.timedelta(days=1)
        add_Image_job(sched,conf,logger,date)
        logger.info('added new job for '+str(date)) 
    return


## auxiliary function that checks whether the main job is running
# @param[in] sched apscheduler object
# @param[in] conf object with configuration
# @param[in] logger logger object
def control_job(sched,conf,logger):
    conf.log_file_handler = lfp.set_log_to_file_new_day(conf.log_path,logger,conf.log_file_handler)
    ls=sched.get_jobs()
    logger.debug('run control job '+str(dt.date.today()))
    if(len(ls)==0):
        add_Image_job(sched,conf,logger)
        logger.error('some problem, I must add extra job for '+str(dt.date.today()))
        

## entry point of script that create main and auxiliary job
def main():

    #inicialize logging
    logger,console_logger=lfp.set_logger(logging.DEBUG)
    

    # read config file
    path_config = os.path.dirname(os.path.realpath(__file__))+'/config.ini' 
    conf = lfp.config_obj(path_config,logger)

    
    #synch time
    if conf.autonomous_mode:
            if conf.GSM_time_sync:
               GSM_modbus.synch_time(conf.GSM_port,logger,conf.GSM_ppp_config_file)
            if conf.GSM_send_log:
                log_handler = GSM_modbus.TailLogHandler(100,logger,conf)
                log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
                log_handler.setLevel(logging.INFO)
                logger.addHandler(log_handler)
                conf.log_internet=log_handler
            #start thread to GSM modem request
            conf.thread = threading.Thread(target=GSM_modbus.GSM_worker,args=(logger,conf))
            conf.thread.start()
                

            
    #inicialize log to file
    conf.log_file_handler= lfp.set_log_to_file(conf.log_path,conf.log_to_console,logger,console_logger)


    #create jobs
    main_sched = BlockingScheduler()
    auxiliary_sched = BackgroundScheduler()

    auxiliary_sched.add_job(control_job, 'cron',[main_sched,conf,logger], hour ='*', minute ='30',second ='5')
    auxiliary_sched.start()

    add_Image_job(main_sched,conf,logger)
    main_sched.start()


if __name__ == '__main__':
    main()
