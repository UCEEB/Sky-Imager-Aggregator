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

    def set_requirements(self):
        if not self.GPRS.hasInternetConnection():
            self.GPRS.enable_GPRS()
        self.scheduler.sync_time()
        self.Messenger.send_sms(
            self.GSM_phone_no,
            'SOME MESSAGE AND INFO'
        )

    def _pick_name(self):
        return datetime.utcnow().strftime('{}.jpg'.format(self.time_format))

    def scan(self):
        output = os.path.join(self.storage_path, self._pick_name())
        self.cam.cap_pic(output=output)

    def preprocess(self, image):
        # Apply mask
        self.preproc.apply_mask(image, self.mask_path)

    def upload(self):
        pass

