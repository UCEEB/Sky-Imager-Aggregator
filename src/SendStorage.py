from time import sleep
import LibrforPi as lfp
import os
import cv2
import datetime as dt
import logging


def main():
    f = open('log_storage.txt',"w+")
    while (True):
        imgnm, hour, minute = lfp.nameimage()

        if lfp.time_for_storage(hour,minute) == True:
            f.write('Thiiiis line is after time_for_storage()')

            if lfp.check_storage_content() == True:
                f.write('Storage is not empty')

                if lfp.check_connectivity() == True:
                    f.write('Connection status: OK')
                    try:
                        p = os.popen('python pic2.py server') # Sends STORAGE to server
                        f.write("This should be output: ", p.read())
                        p.close()
                        f.write("Pipe closed!")
                    except IOError:
                        f.write('ERROR: calling server script fail!')
                        p.close()
                        f.write("Pipe closed because of error...")
                        continue
                elif lfp.check_connectivity() == False:
                    f.write("No connection")

        f.write('Not time for storage yet')
        sleep(3600)
        f.close()
if __name__ == '__main__':
    print("Running program...")
    main()
