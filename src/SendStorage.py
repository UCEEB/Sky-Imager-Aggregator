from time import sleep
import LibrforPi as lfp
from subprocess import call
import sys


def main():

    while (True):
        imgnm, hour, minute = lfp.nameimage()

        if lfp.time_for_storage(hour,minute) == True:

            if lfp.check_storage_content() == True:
                sys.stdout.write('Storage is not empty')

                if lfp.check_connectivity() == True:
                    sys.stdout.write('Connection status: OK')
                    try:
                        pipe = call(['python','pic2.py','server']) # Sends STORAGE to server
                        sys.stdout.write("Storage sent!")
                        sys.stdout.write("Pipe closed!")
                    except IOError:
                        sys.stdout.write('ERROR: calling server script fail!')
                        sys.stdout.write("Pipe closed because of error...")
                        continue
                elif lfp.check_connectivity() == False:
                    sys.stdout.write("No connection")

        sys.stdout.write('Not time for storage yet')
        sleep(3600)

if __name__ == '__main__':
    print("Running program...")
    main()
