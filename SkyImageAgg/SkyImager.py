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

from SkyImageAgg.Configuration import Configuration
from SkyImageAgg.Controller import Controller
from SkyImageAgg.GSM import Messenger, GPRS, retry_on_failure

_parent_dir_ = os.path.dirname(os.path.dirname(__file__))


def loop_infinitely(time_gap=3):
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            while True:
                kick_off = time.time()
                if time_gap:
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
            camera_latitude=self.config.camera_latitude,
            camera_longitude=self.config.camera_longitude,
            camera_altitude=self.config.camera_altitude,
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
            log_stream=self.config.log_to_console,
            irradiance_sensor=self.config.light_sensor
        )
        try:
            self.Messenger = Messenger()
            self.GPRS = GPRS(ppp_config_file=self.config.GSM_ppp_config_file)
            self.mask = self.get_binary_image(self.config.mask_path)
        except Exception as e:
            self.logger.exception(e)

        self.upload_stack = LifoQueue()
        self.write_stack = LifoQueue()
        self.day_no = dt.datetime.utcnow().timetuple().tm_yday
        self.sunrise, self.sunset = self.get_today_twilight_times(day_no=self.day_no)
        self.daytime = False

    # TODO
    def check_requirements(self):
        if not os.path.exists(_twilight_coll_):
            try:
                self.collect_annual_twilight_times(dir_path=_parent_dir_)
            except Exception as e:
                self.logger.exception(e)

        if os.path.exists(_twilight_coll_):
            self.logger.info('twilight times are already collected')

            with open(_twilight_coll_, 'rb') as handle:
                col = pickle.load(handle)

                if col['geo_loc'] != (self.config.camera_latitude, self.config.camera_longitude):
                    self.logger.info('your location has changed. Collecting new twilight data...')
                    try:
                        self.collect_annual_twilight_times(_parent_dir_)
                    except Exception as e:
                        self.logger.exception(e)

        if not self.GPRS.hasInternetConnection():
            try:
                self.GPRS.enable_GPRS()
                self.Messenger.send_sms(self.GSM_phone_no, 'SOME MESSAGE AND INFO')
            except Exception as e:
                self.logger.exception(e)

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
                    self.sunrise, self.sunset = self.get_today_twilight_times(day_no=self.day_no)
                except Exception as e:
                    self.logger.exception(e)

    def run(self):
        try:
            jobs = []
            self.logger.info('Initializing the watcher!')
            watcher = threading.Thread(name='Watcher', target=self.watch_time)
            jobs.append(watcher)
            self.logger.info('Initializing the uploader!')
            uploader = threading.Thread(name='Uploader', target=self.execute_periodically)
            jobs.append(uploader)
            self.logger.info('Initializing the retriever!')
            retriever = threading.Thread(name='Retriever', target=self.check_upload_stack)
            jobs.append(retriever)
            self.logger.info('Initializing the writer!')
            writer = threading.Thread(name='Writer', target=self.check_write_stack)
            jobs.append(writer)
            self.logger.info('Initializing the disk checker!')
            disk_checker = threading.Thread(name='Disk Checker', target=self.check_disk)
            jobs.append(disk_checker)

            for job in jobs:
                job.start()
        except Exception:
            self.logger.critical('Sky Scanner has stopped working!', exc_info=True)


if __name__ == '__main__':
    s = SkyScanner()
    s.run()
