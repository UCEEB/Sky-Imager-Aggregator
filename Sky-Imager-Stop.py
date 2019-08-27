import subprocess
import os

if os.name == 'posix':
    try:
        #stop_timer = 'sudo systemctl stop sky_image_aggr-send_storage.timer'
        #disable_timer = 'sudo systemctl disable sky_image_aggr-send_storage.timer'

        stop_aggr = 'sudo systemctl stop sky_image_aggr.service'
        disable_aggr = 'sudo systemctl disable sky_image_aggr.service'

        #subprocess.call(stop_timer, shell=True)
        #subprocess.call(disable_timer, shell=True)
        subprocess.call(stop_aggr, shell=True)
        subprocess.call(disable_aggr, shell=True)
    except OSError as e:
        print('Error: ' + str(e))
