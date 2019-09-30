#!/usr/bin/python3
import os
from datetime import datetime

from SkyImageAgg.Controller import Controller, Scheduler
from SkyImageAgg.GSM import Messenger, GPRS
from SkyImageAgg.Collector import IrrSensor
from SkyImageAgg.Configuration import Configuration


class SkyScanner(Controller, Configuration):
    def __init__(self):
        self.config = Configuration()
        super().__init__(
            server=self.config.server,
            camera_id=self.config.id,
            image_quality=self.config.image_quality,
            auth_key=self.config.key,
            storage_path=self.config.storage_path,
            ext_storage_path=self.config.ext_storage_path,
            time_format=self.config.time_format,
            autonomous_mode=self.config.autonomous_mode,
            cam_address=self.config.cam_address,
            username=self.config.cam_username,
            pwd=self.config.cam_pwd,
            rpi_cam=self.config.integrated_cam
        )
        if self.config.light_sensor:
            self.sensor = IrrSensor(
                port=self.config.MODBUS_port,
                address=self.config.MODBUS_sensor_address,
                baudrate=self.config.MODBUS_baudrate,
                bytesize=self.config.MODBUS_bytesize,
                parity=self.config.MODBUS_parity,
                stopbits=self.config.MODBUS_stopbits
            )
        self.scheduler = Scheduler()
        self.Messenger = Messenger()
        self.GPRS = GPRS(ppp_config_file=self.config.GSM_ppp_config_file)
        self.mask = self.get_binary_image(self.config.mask_path)

    def set_requirements(self):
        if not self.GPRS.hasInternetConnection():
            self.GPRS.enable_GPRS()
        self.scheduler.sync_time()
        self.Messenger.send_sms(
            self.GSM_phone_no,
            'SOME MESSAGE AND INFO'
        )

    def _stamp_current_time(self):
        return datetime.utcnow().strftime(self.time_format)

    def scan(self):
        # store the current time according to the time format
        cap_time = self._stamp_current_time()
        # set the path to save the image
        output_path = os.path.join(self.storage_path, cap_time)
        return cap_time, output_path, self.cam.cap_pic(output=output_path, return_arr=True)

    def preprocess(self, image_arr):
        # Crop
        image_arr = self.crop(image_arr, self.config.crop)
        # Apply mask
        return self.apply_binary_mask(self.mask, image_arr)

    def upload(self):
        pass


if __name__ == '__main__':
    import time

    s = SkyScanner()
    count = 0
    tic = time.time()
    while count < 100:
        tac = time.time()
        img = s.scan()
        s.save_as_pic(s.preprocess(img[1]), img[0])
        print('{} took {} second(s)'.format(img[0], time.time() - tac))
        count += 1
    print('whole process took {} seconds'.format(time.time() - tic))
