# Author: Barbara Stefanovska and Jan Havrlant
#import time
import LibrforPiV2 as lfp
#import os
import cv2
import datetime as dt
#import sys
import configparser 
import logging 
import os


def main():
    #inicialize logging
    logger,console_logger=lfp.set_logger(logging.DEBUG)
    path_config = os.path.dirname(os.path.realpath(__file__))+'/config.ini' 

    # read config file
    conf = lfp.config_obj(path_config,logger)

    #inicialize log to file
    lfp.set_log_to_file(conf.log_path,conf.log_to_console,logger,console_logger)

    #test if is daytime
    #timeUTC = dt.datetime.now(dt.timezone.utc)
    #if not  conf.sunrise<timeUTC and  conf.ssunset>timeUTC:
    #    return 

    if not lfp.is_daytime(conf.camera_latitude,conf.camera_longitude,conf.camera_altitude,conf.debug_mode ):
        return


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
        #image = frame[45:1970,340:2265]
        #image = frame[41:1967,331:2257]
        image = frame[conf.crop[1]:conf.crop[1]+conf.crop[3],conf.crop[0]:conf.crop[0]+conf.crop[2]] 
        # Masking image :
        #image = lfp.maskImg(resize) #UNDER RECONSTRUCTION!
        

        is_success, buffer = cv2.imencode(".jpg", image,[int(cv2.IMWRITE_JPEG_QUALITY), conf.image_quality])
        success = True
        try:
            response=lfp.upload_json(buffer,image_time,conf.server)
        except Exception as e:
            logger.error('upload to server error : '+str(e))
            success=False
        if success==False or conf.debug_mode==True:            
            lfp.save_to_storage(buffer,conf.path_storage,image_time.strftime(conf.filetime_format),logger)

        if success==True:
            logger.info('upload to server OK' ) 
    else:
        
        logger.error('Camera unavailable. -> Possible solution: Reboot RaspberryPi with "sudo reboot" \n')


    
if __name__ == '__main__':
    #sys.stdout.write("Running program...")
    

    main()

