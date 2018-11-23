# Author: Barbara Stefanovska 
import time
import LibrforPi as lfp
import os
import cv2
import datetime as dt
import sys
from subprocess import call

def main():
    # For sky-scanner camera : 10.208.8.43/video.mjpg | usr = LI20411 pass = Bustehrad27343
    # For cheap camera http://10.208.249.205/JpegStream.cgi?username=A626F32064EC55686A788FCF789120FB90A666830053AEAC36546976D5B7558F&password=A626F32064EC55686A788FCF789120FB90A666830053AEAC36546976D5B7558F&channel=1&secret=1&key=42090Bmdmhf
    # Camera inside UCEEB: usr = admin pass = admin ip = 192.168.0.10
    #cap = cv2.VideoCapture('http://admin:admin@192.168.0.10/video.mjpg')
    #cap = cv2.VideoCapture('http://192.168.0.10/JpegStream.cgi?username=4A0B23AFD8988EA318DD569661C7A83845EC450673899D7491F0F29BD382D026&password=4A0B23AFD8988EA318DD569661C7A83845EC450673899D7491F0F29BD382D026&channel=1&secret=1&key=25C1D5BDBppdmh')
    while (True):
        sec = str(dt.datetime.now())
        sec = sec[17:19]
        sec = int(sec)
        cap = cv2.VideoCapture('http://192.168.0.10/JpegStream.cgi?username=4A0B23AFD8988EA318DD569661C7A83845EC450673899D7491F0F29BD382D026&password=4A0B23AFD8988EA318DD569661C7A83845EC450673899D7491F0F29BD382D026&channel=1&secret=1&key=25C1D5BDBppdmh')
        
        if (sec % 10 == 0):
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
                #image = resize
                #image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                #cv2.imshow('Current image ',image) # ------> Currently unnecessary
                               
                image_name = str(image_name)+'.jpg'
                path = '/home/pi/code'
                cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)  # Saving image to disk so it can be sent
                sys.stdout.write('Image saved to disk\nReady to send\n')

                if lfp.check_connectivity() == True:

#                    try:
                    pipe = call(["python","pic.py","server"]) # Sends a single image to server
                    #pipe.read()
                    
##                    sys.stdout.write("Image sent!\n")
##                    #p.close()
##                    outdata , outerror = pipe.communicate()
##                    sys.stdout.write(str(outdata))
##                    sys.stdout.write(str(outerror))
##                    pipe.terminate()
##                    os.system("python pic.py server")
##                    except:
##                        #sys.stdout.write(str(e))
##                        sys.stdout.write('ERROR: calling server script fail!\n')
##                        sys.stdout.write('Storing image ...\n')
##                        path = '/home/pi/code'
##                        cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)
##                        lfp.stack_storage()
##                        sys.stdout.write('Done.\n')
##                        sys.stdout.write('_____________________________________')
                        
                if lfp.check_connectivity() == False:
                    sys.stdout.write('Connectivity error\nStoring image...\n')
                    path = '/home/pi/code/STORAGE'
                    cv2.imwrite(os.path.join(os.path.expanduser('~'), path, image_name), img=image)
                    lfp.stack_storage()
                    sys.stdout.write('Done.\n')
                    sys.stdout.write('_________________________________________\n')

                lfp.pause_time(hour,minute)
                sys.stdout.write("__________________________________________\n")

            else:
                sys.stdout.write('Camera unavailable. -> Possible solution: Reboot RaspberryPi with "sudo reboot" \n')
        lfp.delete_image()
        time.sleep(0.5)
        
if __name__ == '__main__':
    sys.stdout.write("Running program...")
    main()