# Author: Barbara Stefanovska
#...
#Thise program is ment to be the executable program for the RaspberryPis' local system functions

import cv2
from time import sleep
import LibrforPi as lfp
import multiprocessing
import subprocess
import os


def main():
    # For sky-scanner camera : 10.208.8.43/video.mjpg | usr = LI20411 pass = Bustehrad27343
    # For cheap camera http://10.208.249.205/JpegStream.cgi?username=A626F32064EC55686A788FCF789120FB90A666830053AEAC36546976D5B7558F&password=A626F32064EC55686A788FCF789120FB90A666830053AEAC36546976D5B7558F&channel=1&secret=1&key=42090Bmdmhf
    # Camera inside UCEEB: usr = admin pass = admin ip = 192.168.0.10
    #cap = cv2.VideoCapture('http://admin:admin@192.168.0.10/video.mjpg')
    cap = cv2.VideoCapture('http://192.168.0.10/JpegStream.cgi?username=163CA3D491AFA4E09404D6F98F9E6E7F27F798C80FB2A9029E67FA36E6BC935D&password=5589BA4CDA78706E9E37EBD1A28F204E6D9EA5126E7329A69FB8F44F89F14F19&channel=1&secret=1&key=89D9caaik')
    multiprocess_flag = 0 # Setting a flag for the second process | flag for sending_storage_content()


    while (True):

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
        path = '/home/barbara/git/cloud_tracking/Files_for_RaspberryPi'
        cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)  # Saving image to disk so it can be sent
        print('Image saved to disk...\nReady to send... ')


        try:
            subprocess.call(['python pic.py server']) # Sends a single image to server
            print("Image sent!\nChecking storage...")


            storage_flag = lfp.check_storage_content()
            if storage_flag == 1:
                print("Storage is not empthy!")
                if multiprocess_flag == 0:
                    try:
                        send_storage = multiprocessing.Process(target = lfp.send_storage_content())
                        multiprocess_flag += 1
                        print("Sending storage!")
                        if send_storage.is_alive() != True:
                            multiprocess_flag = 0
                    except:
                        continue


        except OSError:
            print('Communication line ERROR!')
            print('Storing image ...')
            #lfp.store_image(image) ---> Not functional
            path = '/home/barbara/git/cloud_tracking/Files_for_RaspberryPi/STORAGE'
            cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)
            lfp.stack_storage()
            print('Done.')
            print('.........................')
        try:
            lfp.pause_time(hour, minute)
        except:
            continue

        lfp.delete_image()
        sleep(8)

        if cv2.waitKey(1) & 0xFF == ord('q'):
             break


if __name__ == '__main__':
    print("Running program...")
    main()