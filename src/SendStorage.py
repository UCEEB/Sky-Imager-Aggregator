from time import sleep
import LibrforPi as lfp
from subprocess import call
import sys


def main():
    #inicialize logging
    logger=lfp.set_logger(logging.DEBUG)

    path_config = 'C:/Users/havrljan/Documents/GitHub/Sky-Imager-Aggregator/src/config.ini' # to do

    # read config file
    conf = lfp.config_obj(path_config,logger)

    #inicialize log to file
    lfp.set_log_to_file(conf.log_path,conf.log_to_console,logger)



    #imgnm, hour, minute = lfp.nameimage()

    #if lfp.time_for_storage(hour,minute) == True:

    if os.listdir(conf.path_storage):
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



if __name__ == '__main__':
    print("Running program...1")
    main()
