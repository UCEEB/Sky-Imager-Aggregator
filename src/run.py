# Author: Barbara Stefanovska 
#... Alternative to runPi.py

import LibrforPi as lfp
import cv2
from time import sleep
import datetime as dt
import os
import configparser

def main():
    # For sky-scanner camera : 10.208.8.43/video.mjpg | usr = LI20411 pass = Bustehrad27343
    # For cheap camera http://10.208.249.205/JpegStream.cgi?username=A626F32064EC55686A788FCF789120FB90A666830053AEAC36546976D5B7558F&password=A626F32064EC55686A788FCF789120FB90A666830053AEAC36546976D5B7558F&channel=1&secret=1&key=42090Bmdmhf
    # Camera inside UCEEB: usr = admin pass = admin ip = 192.168.0.10
    #cap = cv2.VideoCapture('http://admin:admin@192.168.0.10/video.mjpg')
    ##cap = cv2.VideoCapture('http://192.168.0.10/JpegStream.cgi?username=163CA3D491AFA4E09404D6F98F9E6E7F27F798C80FB2A9029E67FA36E6BC935D&password=5589BA4CDA78706E9E37EBD1A28F204E6D9EA5126E7329A69FB8F44F89F14F19&channel=1&secret=1&key=89D9caaik')
    #multiprocess_flag = 0 # Setting a flag for the second process | flag for sending_storage_content()

    # read config file
    config = configparser.ConfigParser()
    config.read('./config/config.ini')
    cap_mod = int(config['DEFAULT']['cap_mod'])
    cap_url = config['DEFAULT']['cap_url']
    
    cap = cv2.VideoCapture(cap_url)

    

    while (True):

        sec = str(dt.datetime.now())
        sec = sec[17:19]
        sec = int(sec)

        if (sec % cap_mod == 0):

            # Opening camera feed:
            ret, frame = cap.read()
            # Resizing in case of wrong dimensions:
            resize = cv2.resize(frame, (1536, 1536), interpolation=cv2.INTER_CUBIC)
            # Masking image :
            image = lfp.maskImg(resize)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            #cv2.imshow('Current image ',image) # ------> Currently unnecessary
            image_name, hour, minute = lfp.nameimage()
            image_name = str(image_name)+'.jpg'
            path = '/home/pi/code'
            cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)  # Saving image to disk so it can be sent
            print('Image saved to disk...\nReady to send... ')
            print("checking connection...")
            if lfp.check_connectivity() == True:
               try:
                   print('calling sever...')
                   p1 = os.popen('python pic.py server')
                   pp1 = p1.read()
                   print("Image sent!")
                   p1.close()

               except OSError:
                   print('Error calling server script')


            elif lfp.check_connectivity() == False:
                print('Internet connection: FAIL')
                print('Storing image ...')
                path = '/home/pi/code/STORAGE'
                cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)
                lfp.stack_storage()
                print('Done.')
                print('.........................')

            print('Deleting image from tmp')
            lfp.delete_image()
            print(hour, ':', minute)
            print('_______________________')

        else:
            storage_flag = lfp.check_storage_content()
            if storage_flag == 1:
                print("Storage is not empty!")
                print('Sending storage...')
                p = os.popen('python pic2.py server')
                pp = p.read()
                print('1 sec passed')
                p.close()
            else:
                print("Storage empty")
        
        print('Continuing in main process')
        if cv2.waitKey(1) & 0xFF == ord('q'):
             break


if __name__ == '__main__':
    print("Running program...")
    main()
