#!/usr/bin/python3
import glob
import os
import datetime as dt
import threading
from queue import LifoQueue
import time

from astral import Astral, Location

from SkyImageAgg.Controller import Controller
from SkyImageAgg.GSM import Messenger, GPRS, retry_on_failure
from SkyImageAgg.Collector import IrrSensor
from SkyImageAgg.Configuration import Configuration


def loop_it(time_gap=3):
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            while True:
                if time_gap:
                    kick_off = time.time()
                    f(*args, **kwargs)
                    try:
                        wait = time_gap - (time.time() - kick_off)
                        print('Waiting {} seconds...'.format(round(wait, 1)))
                        time.sleep(wait)
                    except ValueError:
                        pass
                else:
                    f(*args, **kwargs)

        return f_retry

    return deco_retry


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
        self.Messenger = Messenger()
        self.GPRS = GPRS(ppp_config_file=self.config.GSM_ppp_config_file)
        self.mask = self.get_binary_image(self.config.mask_path)
        self.upload_stack = LifoQueue()
        self.write_stack = LifoQueue()

    # TODO
    def set_requirements(self):
        if not self.GPRS.hasInternetConnection():
            self.GPRS.enable_GPRS()
        self.Messenger.send_sms(
            self.GSM_phone_no,
            'SOME MESSAGE AND INFO'
        )

    @staticmethod
    def sync_time():
        if os.system('sudo ntpdate -u tik.cesnet.cz') == 0:
            return True

    @staticmethod
    def get_sunrise_and_sunset_time(cam_latitude, cam_longitude, cam_altitude, date=None):
        if not date:
            date = dt.datetime.now(dt.timezone.utc).date()

        astral = Astral()
        astral.solar_depression = 'civil'
        location = Location(('custom', 'region', cam_latitude, cam_longitude, 'UTC', cam_altitude))
        sun = location.sun(date=date)

        return sun['sunrise'], sun['sunset']

    def _stamp_curr_time(self):
        return dt.datetime.utcnow().strftime(self.time_format)

    def scan(self):
        # store the current time according to the time format
        cap_time = self._stamp_curr_time()
        # set the path to save the image
        output_path = os.path.join(self.storage_path, cap_time)
        return cap_time, output_path, self.cam.cap_pic(output=output_path, return_arr=True)

    def preprocess(self, image_arr):
        # Crop
        image_arr = self.crop(image_arr, self.config.crop)
        # Apply mask
        image_arr = self.apply_binary_mask(self.mask, image_arr)
        return image_arr

    def execute(self):
        # capture the image and set the proper name and path
        cap_time, img_path, img_arr = self.scan()
        # preprocess the image
        preproc_img = self.preprocess(img_arr)
        # try to upload the image to the server, if failed, save it to storage
        try:
            self.upload_as_json(preproc_img, time_stamp=cap_time)
            print('Uploading {} was successful!'.format(img_path))
        except Exception:
            print('Couldn\'t upload {}! Queueing for retry!'.format(img_path))
            self.upload_stack.put((cap_time, img_path, img_arr))

    @retry_on_failure(attempts=2)
    def retry_upload(self, image, time_stamp, convert_to_arr=False):
        self.upload_as_json(image, time_stamp, convert_to_arr)

    @loop_it(time_gap=10)
    def execute_periodically(self):
        self.execute()

    @loop_it(time_gap=False)
    def check_upload_stack(self):
        if not self.upload_stack.empty():
            cap_time, img_path, img_arr = self.upload_stack.get()
            try:
                self.retry_upload(image=img_arr, time_stamp=cap_time)
                print('Retrying to upload {} was successful!'.format(img_path))
            except Exception:
                print('Retrying to upload {} failed! Queueing for saving on disk'.format(img_path))
                self.write_stack.put((cap_time, img_path, img_arr))
        else:
            time.sleep(5)

    @loop_it(time_gap=False)
    def check_write_stack(self):
        if not self.write_stack.empty():
            cap_time, img_path, img_arr = self.write_stack.get()
            try:
                self.save_as_pic(image_arr=img_arr, output_name=img_path)
                print('{} saved to storage.'.format(img_path))
            except Exception:
                time.sleep(10)
        else:
            time.sleep(5)

    @loop_it(time_gap=False)
    def upload_images_in_storage(self):
        if len(os.listdir(self.storage_path)) == 0:
            time.sleep(10)
            print('{} is empty!'.format(self.storage_path))
        else:
            for image in glob.iglob(os.path.join(self.storage_path, '*.jpg')):
                time_stamp = os.path.split(image)[-1].split('.')[0]
                try:
                    print('uploading {}'.format(image))
                    self.retry_upload(image=image, time_stamp=time_stamp, convert_to_arr=True)
                    os.remove(image)
                except Exception:
                    print('failed')
                    time.sleep(30)

    def run(self):
        jobs = []
        print('Initiating the uploader!')
        uploader = threading.Thread(target=self.execute_periodically)
        jobs.append(uploader)
        print('Initiating the retriever!')
        retriever = threading.Thread(target=self.check_upload_stack)
        jobs.append(retriever)
        print('Initiating the writer!')
        writer = threading.Thread(target=self.check_write_stack)
        jobs.append(writer)
        print('Initiating the disk checker!')
        disk_checker = threading.Thread(target=self.upload_images_in_storage)
        jobs.append(disk_checker)

        for job in jobs:
            job.start()


if __name__ == '__main__':
    s = SkyScanner()
    s.upload_images_in_storage()
