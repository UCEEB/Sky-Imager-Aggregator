#!/usr/bin/python3
import datetime as dt
import glob
import os
import pickle
import threading
import time
from queue import LifoQueue

import numpy as np
from astral import Astral, Location

from SkyImageAgg.Collector import IrrSensor
from SkyImageAgg.Configuration import Configuration
from SkyImageAgg.Controller import Controller
from SkyImageAgg.GSM import Messenger, GPRS, retry_on_failure

_parent_dir_ = os.path.dirname(os.path.dirname(__file__))
_twilight_coll_ = os.path.join(_parent_dir_, 'ann_twilight_coll.pkl')


def loop_infinitely(time_gap=3):
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            while True:
                if time_gap:
                    kick_off = time.time()
                    f(*args, **kwargs)
                    try:
                        wait = time_gap - (time.time() - kick_off)
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
            rpi_cam=self.config.integrated_cam,
            log_dir=self.config.log_path,
            log_stream=True
        )
        try:
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
        except Exception as e:
            self.logger.exception(e)

        self.upload_stack = LifoQueue()
        self.write_stack = LifoQueue()
        self.day_no = dt.datetime.utcnow().timetuple().tm_yday
        self.sunrise, self.sunset = self.get_today_twilight_times()
        self.daytime = False

    # TODO
    def check_requirements(self):
        if not os.path.exists(_twilight_coll_):
            try:
                self.collect_annual_twilight_times()
            except Exception as e:
                self.logger.exception(e)

        if os.path.exists(_twilight_coll_):
            self.logger.info('twilight times are already collected and stored at {}'.format(_twilight_coll_))

            with open(_twilight_coll_, 'rb') as handle:
                col = pickle.load(handle)

                if col['geo_loc'] != (self.config.camera_latitude, self.config.camera_longitude):
                    self.logger.info('it seems your location has changed. Collecting new twilight data...')
                    try:
                        self.collect_annual_twilight_times()
                    except Exception as e:
                        self.logger.exception(e)

        if not self.GPRS.hasInternetConnection():
            try:
                self.GPRS.enable_GPRS()
                self.Messenger.send_sms(self.GSM_phone_no, 'SOME MESSAGE AND INFO')
            except Exception as e:
                self.logger.exception(e)

    def sync_time(self):
        self.logger.info('synchronizing the time with {}'.format(self.config.ntp_server))
        if os.system('sudo /usr/sbin/ntpd {}'.format(self.config.ntp_server)) == 0:
            return True

    def get_sunrise_and_sunset_time(self, date=None):
        if not date:
            date = dt.datetime.now(dt.timezone.utc).date()

        astral = Astral()
        astral.solar_depression = 'civil'
        location = Location((
            'custom',
            'region',
            self.config.camera_latitude,
            self.config.camera_longitude,
            'UTC',
            self.config.camera_altitude
        ))
        sun = location.sun(date=date)

        return sun['sunrise'].time(), sun['sunset'].time()

    def collect_annual_twilight_times(self):
        self.logger.info('collecting the annual twilight times based on your given location')
        collection = {
            'geo_loc': (self.config.camera_latitude,
                        self.config.camera_longitude)
        }

        dates = np.arange(
            # 2021 is chosen as it's a leap year with 366 days
            dt.datetime(2020, 1, 1),
            dt.datetime(2021, 1, 1),
            dt.timedelta(days=1)
        ).astype(dt.datetime).tolist()

        for date in dates:
            collection[date.timetuple().tm_yday] = self.get_sunrise_and_sunset_time(date=date)

        with open(_twilight_coll_, 'wb') as file:
            pickle.dump(collection, file, protocol=pickle.HIGHEST_PROTOCOL)

        return collection

    def get_today_twilight_times(self):
        with open(_twilight_coll_, 'rb') as handle:
            col = pickle.load(handle)
        return col[self.day_no]

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
        if not image_arr.shape == (1920, 1920):
            image_arr = self.crop(image_arr, self.config.crop)
        # Apply mask
        image_arr = self.apply_binary_mask(self.mask, image_arr)
        return image_arr

    def execute(self):
        # capture the image and set the proper name and path for it
        cap_time, img_path, img_arr = self.scan()
        # preprocess the image
        preproc_img = self.preprocess(img_arr)
        # try to upload the image to the server, if failed, save it to storage
        try:
            self.upload_as_json(preproc_img, time_stamp=cap_time)
            self.logger.info('Uploading {} was successful!'.format(img_path))
        except Exception:
            self.logger.warning('Couldn\'t upload {}! Queueing for retry!'.format(img_path))
            self.upload_stack.put((cap_time, img_path, preproc_img))

    @retry_on_failure(attempts=2)
    def retry_upload(self, image, time_stamp):
        self.upload_as_json(image, time_stamp)

    @loop_infinitely(time_gap=10)
    def execute_periodically(self):
        if self.daytime:
            try:
                self.execute()
            except Exception as e:
                self.logger.exception(e)

    @loop_infinitely(time_gap=False)
    def check_upload_stack(self):
        if not self.upload_stack.empty():
            cap_time, img_path, img_arr = self.upload_stack.get()
            try:
                self.retry_upload(image=img_arr, time_stamp=cap_time)
                self.logger.info('retrying to upload {} was successful!'.format(img_path))
            except Exception as e:
                self.logger.warning('retrying to upload {} failed! Queueing for saving on disk'.format(img_path))
                self.logger.exception(e)
                self.write_stack.put((cap_time, img_path, img_arr))
        else:
            time.sleep(5)

    @loop_infinitely(time_gap=False)
    def check_write_stack(self):
        if not self.write_stack.empty():
            cap_time, img_path, img_arr = self.write_stack.get()
            try:
                self.save_as_pic(image_arr=img_arr, output_name=img_path)
                self.logger.info('{} was successfully written on disk.'.format(img_path))
            except Exception as e:
                self.logger.warning('failed to write {} on disk'.format(img_path))
                self.logger.exception(e)
                time.sleep(10)
        else:
            time.sleep(5)

    @loop_infinitely(time_gap=False)
    def check_disk(self):
        if len(os.listdir(self.storage_path)) == 0:
            time.sleep(10)
        else:
            for image in glob.iglob(os.path.join(self.storage_path, '*.jpg')):
                time_stamp = os.path.split(image)[-1].split('.')[0]
                try:
                    self.logger.info('uploading {} to the server'.format(image))
                    self.retry_upload(image=image, time_stamp=time_stamp)  # try to upload
                    self.logger.info('{} was successfully uploaded from disk to the server'.format(image))
                    os.remove(image)
                    self.logger.info('{} was removed from disk'.format(image))
                except Exception as e:
                    self.logger.warning('failed to upload {} from disk to the server'.format(image))
                    self.logger.exception(e)
                    time.sleep(30)

    @loop_infinitely(time_gap=30)
    def watch_time(self):
        curr_time = dt.datetime.utcnow()  # get the current utc time

        if self.sunrise < curr_time.time() < self.sunset:
            if not self.daytime:
                self.logger.info('Daytime has started!')
                self.daytime = True
        else:
            if self.daytime:
                self.logger.info('Daytime is over!')
                self.daytime = False
            if curr_time.timetuple().tm_yday != self.day_no:  # check if the day has changed
                self.day_no = curr_time.timetuple().tm_yday
                try:
                    self.sunrise, self.sunset = self.get_today_twilight_times()
                except Exception as e:
                    self.logger.exception(e)

    def run(self):
        jobs = []
        print('Initiating the watcher!')
        watcher = threading.Thread(name='Watcher', target=self.watch_time)
        jobs.append(watcher)
        print('Initiating the uploader!')
        uploader = threading.Thread(name='Uploader', target=self.execute_periodically)
        jobs.append(uploader)
        print('Initiating the retriever!')
        retriever = threading.Thread(name='Retriever', target=self.check_upload_stack)
        jobs.append(retriever)
        print('Initiating the writer!')
        writer = threading.Thread(name='Writer', target=self.check_write_stack)
        jobs.append(writer)
        print('Initiating the disk checker!')
        disk_checker = threading.Thread(name='Disk Checker', target=self.check_disk)
        jobs.append(disk_checker)

        for job in jobs:
            job.start()


if __name__ == '__main__':
    s = SkyScanner()
    s.run()
