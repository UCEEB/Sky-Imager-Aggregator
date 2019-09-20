#!/usr/bin/python3
import os
from datetime import datetime

from SkyImageAgg.Controller import Uploader, Scheduler
from SkyImageAgg.GSM import Messenger, GPRS
from SkyImageAgg.Collector import RPiCam, GeoVisionCam, IrrSensor
from SkyImageAgg.Configuration import Configuration
from SkyImageAgg.Processor import ImageProcessor


class SkyScanner(Configuration):
    def __init__(self):
        super().__init__()
        if self.light_sensor:
            self.sensor = IrrSensor(
                port=self.MODBUS_port,
                address=self.MODBUS_sensor_address,
                baudrate=self.MODBUS_baudrate,
                bytesize=self.MODBUS_bytesize,
                parity=self.MODBUS_parity,
                stopbits=self.MODBUS_stopbits
            )
        if self.integrated_cam:
            self.cam = RPiCam()
        else:
            self.cam = GeoVisionCam(
                cam_address=self.cam_address,
                username=self.cam_username,
                pwd=self.cam_pwd
            )

        self.uploader = Uploader(
            server=self.server,
            camera_id=self.id,
            auth_key=self.key,
            storage_path=self.storage_path,
            ext_storage_path=self.ext_storage_path,
            time_format=self.time_format,
            autonomous_mode=self.autonomous_mode
        )
        self.preproc = ImageProcessor()
        self.scheduler = Scheduler()
        self.Messenger = Messenger()
        self.GPRS = GPRS(ppp_config_file=self.GSM_ppp_config_file)

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

    def preprocess(self):
        pass

    def upload(self):
        pass

