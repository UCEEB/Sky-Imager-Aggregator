import subprocess
import os

if os.name == 'posix':
    try:
        cp_service = 'sudo cp systemd/sky_image_aggr-send_storage.service /lib/systemd/system/'
        cp_timer = 'sudo cp systemd/sky_image_aggr-send_storage.timer /lib/systemd/system/'
        enable_timer = 'sudo systemctl enable sky_image_aggr-send_storage.timer'
        start_timer = 'sudo systemctl start sky_image_aggr-send_storage.timer'

        cp_aggr = 'sudo cp systemd/sky_image_aggr.service /lib/systemd/system/'
        enable_aggr = 'sudo systemctl enable sky_image_aggr.service'
        start_aggr = 'sudo systemctl start sky_image_aggr.service'

        subprocess.call(cp_service, shell=True)
        subprocess.call(cp_timer, shell=True)
        subprocess.call(enable_timer, shell=True)
        subprocess.call(start_timer, shell=True)
        subprocess.call(cp_aggr, shell=True)
        subprocess.call(enable_aggr, shell=True)
        subprocess.call(start_aggr, shell=True)
    except OSError as e:
        print('Error: ' + str(e))
