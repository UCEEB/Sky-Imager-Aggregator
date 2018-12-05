# Author: Barbara Stefanovska 
import time
import LibrforPi as lfp
import os
import cv2
import datetime as dt
import sys
from subprocess import call
import configparser

def main():
    # For sky-scanner camera : 10.208.8.43/video.mjpg | usr = LI20411 pass = Bustehrad27343
    # For cheap camera http://10.208.249.205/JpegStream.cgi?username=A626F32064EC55686A788FCF789120FB90A666830053AEAC36546976D5B7558F&password=A626F32064EC55686A788FCF789120FB90A666830053AEAC36546976D5B7558F&channel=1&secret=1&key=42090Bmdmhf
    # Camera inside UCEEB: usr = admin pass = admin ip = 192.168.0.10
    #cap = cv2.VideoCapture('http://admin:admin@192.168.0.10/video.mjpg')
    #cap = cv2.VideoCapture('http://192.168.0.10/JpegStream.cgi?username=4A0B23AFD8988EA318DD569661C7A83845EC450673899D7491F0F29BD382D026&password=4A0B23AFD8988EA318DD569661C7A83845EC450673899D7491F0F29BD382D026&channel=1&secret=1&key=25C1D5BDBppdmh')

    path = '/home/pi/Sky-Imager-Aggregator/config/config.ini'
    abspath = os.path.abspath(path) #To use config.ini files you need an absolute path to file relative to the directory you are in now
    sys.stdout.write(abspath)
    # read config file
    config = configparser.ConfigParser()
    config.read(abspath)
    #cap_mod = int(config['DEFAULT']['cap_mod'])
    cap_mod = config.getint('DEFAULT','cap_mod')
    #cap_url = config['DEFAULT']['cap_url']
    cap_url = config.get('DEFAULT','cap_url')

    
    while (True):
        sec = str(dt.datetime.now())
        sec = sec[17:19]
        sec = int(sec)
        
        #cap = cv2.VideoCapture('http://192.168.0.10/JpegStream.cgi?username=4A0B23AFD8988EA318DD569661C7A83845EC450673899D7491F0F29BD382D026&password=4A0B23AFD8988EA318DD569661C7A83845EC450673899D7491F0F29BD382D026&channel=1&secret=1&key=25C1D5BDBppdmh')
        cap = cv2.VideoCapture(cap_url)
        
        if (sec % cap_mod == 0):
            image_name, hour, minute = lfp.nameimage()
            sys.stdout.write(image_name)
            sys.stdout.write('\n')
            # Opening camera feed:
            ret, frame = cap.read()
            if cap.isOpened():
                # Resizing in case of wrong dimensions:
                crop = frame[45:1970,340:2265]
                resize = cv2.resize(crop, (1536, 1536), interpolation=cv2.INTER_CUBIC)
                # Masking image :
                image = lfp.maskImg(resize) #UNDER RECONSTRUCTION!
                image_name = str(image_name)+'.jpg'
                path = '/home/pi/code'
                cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)  # Saving image to disk so it can be sent
                sys.stdout.write('Image saved to disk\nReady to send\n')

                if lfp.check_connectivity() == True:
                    try:
                        pipe = call(["python","pic.py","server"]) # Sends a single image to server

                    except:
                        sys.stdout.write('ERROR: calling server script fail!\n')
                        sys.stdout.write('Storing image ...\n')
                        path = '/home/pi/code'
                        cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)
                        lfp.stack_storage()
                        sys.stdout.write('Done.\n')
                        sys.stdout.write('_____________________________________')
                        
                if lfp.check_connectivity() == False:
                    sys.stdout.write('Connectivity error\nStoring image...\n')
                    path = '/home/pi/code/STORAGE'
                    cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)
                    lfp.stack_storage()
                    sys.stdout.write('Done.\n')
                    sys.stdout.write('_________________________________________\n')

                sys.stdout.write("__________________________________________\n")
                lfp.pause_time(hour,minute)
            else:
                sys.stdout.write('Camera unavailable. -> Possible solution: Reboot RaspberryPi with "sudo reboot" \n')
       
        try:
            lfp.delete_image()
        
        time.sleep(0.5)
    
if __name__ == '__main__':
    sys.stdout.write("Running program...")
    main()
