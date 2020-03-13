#!/usr/bin/python3
import datetime as dt
import glob
import logging
import os
import shutil
import time
from os.path import dirname
from os.path import join
from queue import LifoQueue
import csv

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler

from SkyImageAgg.Collectors.IrradianceSensor import IrrSensor
from SkyImageAgg.Configuration import Config
from SkyImageAgg.Controller import Controller
from SkyImageAgg.Controller import TwilightCalc
from SkyImageAgg.GSM import GPRS
from SkyImageAgg.GSM import has_internet
from SkyImageAgg.GSM import Messenger
from SkyImageAgg.Logger import Logger

_base_dir = dirname(dirname(__file__))
_tmp_dir = join(_base_dir, 'temp')
_log_dir = join(_base_dir, 'log')
_data_dir = join(_base_dir, 'data')

if not os.path.exists(_tmp_dir):
    os.mkdir(_tmp_dir)

if not os.path.exists(_log_dir):
    os.mkdir(_log_dir)

if not os.path.exists(_data_dir):
    os.mkdir(_data_dir)

# a LIFO stack for storing failed uploads to be accessible by uploader job.
upload_stack = LifoQueue(maxsize=5)

# executors for job schedulers (max threads: 30)
sched = BlockingScheduler(executors={'default': ThreadPoolExecutor(30)})

# Application logger
logger = Logger(name='SkyScanner')

if Config.log_to_console:
    logger.add_stream_handler()

if Config.log_path:
    log_file_path = join(Config.log_path, logger.name)
    logger.add_timed_rotating_file_handler(log_file=log_file_path)

if Config.dashboard_enabled:
    logger.add_influx_handler(
        username=Config.influxdb_user,
        pwd=Config.influxdb_pwd,
        host=Config.influxdb_host,
        database=Config.influxdb_database,
        measurement='app_log',
        tags={
            'latitude': Config.camera_latitude,
            'longitude': Config.camera_longitude,
            'host': os.uname()[1]
        }
    )

# Logger object to collect irradiance sensor data and send the to an influxDB server
if Config.irr_sensor_enabled and Config.dashboard_enabled:
    sensor_logger = Logger(name='IrrSensor')
    log_file_path = join(Config.log_path, sensor_logger.name)
    sensor_logger.add_timed_rotating_file_handler(log_file=log_file_path)
    sensor_logger.add_sensor_handler(
        username=Config.influxdb_user,
        pwd=Config.influxdb_pwd,
        host=Config.influxdb_host,
        database=Config.influxdb_database,
        measurement='sensor_log',
        tags={
            'latitude': Config.camera_latitude,
            'longitude': Config.camera_longitude,
            'host': os.uname()[1]
        }
    )
else:
    sensor_logger = logging.getLogger(name='IrrSensor')
    sensor_logger.addHandler(logging.NullHandler())


class SkyScanner(Controller):
    """
    Capture pictures from sky and either store them locally or upload them to a remote server.

    `SkyScanner`,  as a child of controller, is responsible for coordination  and  aggregation of the images  taken
    by the device. It  configures its necessary attributes  via the help of `Config` class and simultaneously takes
    photos   from sky  and  measures the irradiance and  temperature. For that  cron jobs are run in the given time
    frames. It also calculates the twilight time within a year with the help of `TwilightCalc` class inherited from
    `Controller` class.

    Attributes
    ----------
    twl_calc : TwilightCalc
        Twilight Calculator object.
    day_of_year : int
        the day of year (DOY) is the sequential day number starting with day 1 on January 1st.
    sunrise : datetime.time
        sunrise time.
    sunset : datetime.time
        sunset time.
    irr_sensor : IrrSensor
        an instance of `Collectors.IrradianceSensor.IrrSensor` to collect irradiance data.
    jpeg_quality : int
        the desired jpeg quality for the captured/loaded image.
    messenger : Messenger
        an instance of `Messenger` class for sending sms texts.
    gprs : GPRS
        an instance of `GPRS` class for connecting the device to internet through GPRS service.
    daytime : `boolean`
        True if daytime, false otherwise.
    """

    def __init__(self):
        """
        Initializes a SkyScanner instance.
        """
        super().__init__(
            server=Config.server,
            client_id=Config.client_id,
            auth_key=Config.key,
            storage_path=Config.storage_path,
            time_format=Config.time_format,
            cam_username=Config.cam_username,
            cam_pwd=Config.cam_pwd,
            cam_address=Config.cam_address
        )

        self.twl_calc = TwilightCalc(
            latitude=Config.camera_latitude,
            longitude=Config.camera_longitude,
            altitude=Config.camera_altitude,
            ntp_server=Config.ntp_server,
            in_memory=False,
            file=join(_base_dir, 'twilight_times.pkl')
        )

        self.day_of_year = dt.datetime.utcnow().timetuple().tm_yday
        self.sunrise, self.sunset = self.twl_calc.get_twilight_times_by_day(day_of_year=self.day_of_year)

        if self.twl_calc.has_location_changed():
            # if device location changed or twilight times have not been collected
            logger.info('Collecting twilight times within a year...')
            self.twl_calc.collect_annual_twilight_times()

        if Config.irr_sensor_enabled:
            self.irr_sensor = IrrSensor(
                port=Config.irr_sensor_port,
                address=Config.irr_sensor_address,
                baudrate=Config.irr_sensor_baudrate,
                bytesize=Config.irr_sensor_bytesize,
                parity=Config.irr_sensor_parity,
                stopbits=Config.irr_sensor_stopbits
            )

        self.set_mask(Config.mask_path)
        self.set_crop_size(Config.image_size)
        self.jpeg_quality = Config.jpeg_quality

        if Config.gsm_enabled:
            self.messenger = Messenger(logger=logger)
            self.gprs = GPRS(ppp_config_file=Config.gsm_ppp_config_file, logger=logger)
        else:
            self.messenger = None
            self.gprs = None

        self.daytime = False

    def measure_irradiance(self, timestamp='now'):
        """
        Measure the irradiance and temperature.

        Parameters
        ----------
        timestamp : datetime.datetime or str
            timestamp of the data

        Returns
        -------
        dict of {str: str}
        """
        try:
            sensor_data = self.irr_sensor.get_data()
            if timestamp.lower() == 'now':
                timestamp = dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

            ms = {
                'timestamp': timestamp,
                'irradiance': sensor_data[0],  # irradiance (W/m^2)
                'ext_temp': sensor_data[1],  # external temperature (°C)
                'cell_temp': sensor_data[2]  # cell temperature (°C)
            }
            # get sensor data (irr, ext_temp, cell_temp)
            sensor_logger.info(ms)

            # send to dashboard
            logger.info(
                f"irr: {ms['irradiance']}, "
                f"ext_t: {ms['ext_temp']}, "
                f"cel_t:  {ms['cell_temp']}"
            )

            # store in data directory
            if Config.irr_sensor_store:
                with open(join(_data_dir, time.strftime('irr-%Y%m%d.csv')), 'a+') as f:
                    writer = csv.DictWriter(f, fieldnames=list(ms.keys()))
                    writer.writerow(ms)

        except Exception as e:
            logger.error(f'Couldn\'t collect data from irradiance sensor!\n{e}')

    def scan(self):
        """
        Take picture and measure the solar irradiance.
        """
        # snap a pic
        self.snap_picture()
        # store the current time according to the time format
        self.timestamp = self.timestamp.strftime(Config.time_format)
        # set the path to save the image
        self.set_path(os.path.join(_tmp_dir, self.timestamp))

        if Config.irr_sensor_enabled:
            # get sensor data (irr, ext_temp, cell_temp)
            self.measure_irradiance(timestamp=self.timestamp)

            if Config.irr_sensor_store:
                with open(join(_data_dir, time.strftime('irr-%Y%m%d.csv')), 'a+') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        self.timestamp,
                        ms['irradiance'],
                        ms['ext_temp'],
                        ms['cell_temp']
                    ])

    def preprocess(self):
        """
        Preprocess the image before upload or save.
        """
        # Crop
        if Config.cropping_enabled:
            self.crop()
        # Apply mask
        if Config.masking_enabled:
            self.apply_mask()

    def execute_and_upload(self):
        """
        Take a picture from sky, pre-process and upload.

        if failed, it puts the image object in `upload_stack`.
        """
        if self.daytime or Config.night_mode:
            # capture the image and set the proper name and path for it
            self.scan()
            # preprocess the image
            self.preprocess()
            # try to upload the image to the server, if failed, save it to storage
            try:
                self.upload_with_timeout(time_stamp=self.timestamp)
                logger.info(f'{self.timestamp}.jpg uploaded!')
            except Exception as e:
                if not upload_stack.full():
                    logger.warning(
                        f'Couldn\'t upload {self.timestamp}.jpg! Queueing for another try!\n{e}')
                    upload_stack.put(self)
                else:
                    logger.info('The upload stack is full! Storing the image...')
                    self.save_as_jpeg()  # write array on the disk as jpg
                    logger.info(f'{self.timestamp}.jpg was stored in temp storage!')
        elif Config.irradiance_at_night:
            self.measure_irradiance()

    def execute_and_store(self):
        """
        Take a picture from sky, pre-processes it and store it.
        """
        if self.daytime or Config.night_mode:
            # capture the image and set the proper name and path for it
            self.scan()
            # preprocess the image
            self.preprocess()
            # write it in storage
            try:
                self.save_as_jpeg()
                logger.info(f'{self.timestamp}.jpg was stored!')
            except Exception as e:
                logger.critical(f'Couldn\'t write {self.timestamp}.jpg on disk!\n{e}')
        elif Config.irradiance_at_night:
            self.measure_irradiance()

    def send_thumbnail(self):
        """
        Send a thumbnail from the recent image to server.
        """
        if self.daytime or Config.night_mode:
            # capture the image and set the proper name and path for it
            self.scan()
            # preprocess the image
            self.preprocess()

            try:
                self.upload_thumbnail(time_stamp=self.timestamp)
                logger.info(f'{self.timestamp}.jpg thumbnail uploaded!')
            except Exception as e:
                logger.error(f'Couldn\'t upload {self.timestamp}.jpg thumbnail!\n{e}')

    @staticmethod
    def check_upload_stack():
        """
        Check the `upload_stack` every 15 seconds.

        Retry uploading the images that were not successfully uploaded to the server.
        If failed, store them in  the temporary storage.
        """
        while not upload_stack.empty():
            obj = upload_stack.get()

            try:
                obj.retry_uploading_image(time_stamp=obj.timestamp)
                logger.info(f'retrying to upload {obj.timestamp}.jpg was successful!')
            except Exception as e:
                logger.warning(f'retrying to upload {obj.timestamp}.jpg failed! Storing in temp storage...\n{e}')
                obj.save_as_jpeg()
                logger.debug(f'{obj.timestamp}.jpg was stored in temp storage!')

            time.sleep(2)

    def check_temp_storage(self):
        """
        Check the temporary storage every 10 seconds.

        Try uploading the stored images. If it failed, wait another 30 seconds.
        """
        # create am empty controller
        c = Controller(
            server=Config.server,
            client_id=Config.client_id,
            auth_key=Config.key,
            storage_path=Config.storage_path,
            time_format=Config.time_format,
            cam_username=None,
            cam_pwd=None,
            cam_address=None
        )
        c.jpeg_quality = Config.jpeg_quality
        if len(os.listdir(_tmp_dir)) != 0:
            for img in glob.iglob(os.path.join(_tmp_dir, '*.jpg')):
                c.set_picture(image=img)
                c.timestamp = os.path.split(img)[-1].split('.')[0]

                try:
                    c.retry_uploading_image(time_stamp=c.timestamp)  # try to re-upload persistently
                    logger.debug(f'{c.timestamp} was uploaded from temp storage to the server.')
                    os.remove(img)
                    logger.debug(f'{c.timestamp} was removed from temp storage.')
                except Exception as e:
                    logger.error(f'retry failed! moving {c.timestamp} to main storage\n{e}')
                    try:
                        shutil.move(img, self.storage_path)
                    except Exception as e:
                        logger.error(f'moving {c.timestamp} to main storage failed!\n{e}')

                time.sleep(2)

    def check_main_storage(self):
        """
        Check the main storage and send the images.
        """
        if has_internet() and len(os.listdir(self.storage_path)) != 0:
            c = Controller(
                server=Config.server,
                client_id=Config.client_id,
                auth_key=Config.key,
                storage_path=Config.storage_path,
                time_format=Config.time_format,
                cam_username=None,
                cam_pwd=None,
                cam_address=None
            )
            c.jpeg_quality = Config.jpeg_quality
            for img in glob.iglob(os.path.join(self.storage_path, '*.jpg')):
                c.set_picture(image=img)
                c.timestamp = os.path.split(img)[-1].split('.')[0]

                try:
                    c.retry_uploading_image(time_stamp=c.timestamp)  # try to re-upload persistently
                    logger.debug(f'{c.timestamp} was uploaded from main storage!')
                    os.remove(img)
                    logger.debug(f'{c.timestamp} was removed from main storage.')
                except Exception as e:
                    logger.error(f'Uploading {c.timestamp} from main storage failed!\n{e}')

    def do_sunrise_operations(self):
        """
        Execute the needed operations after sunrise.

        Once it's sunrise, sets `daytime` attribute to True and sends a sms text reporting the device status.
        """
        if not self.daytime:
            logger.debug('It\'s daytime!')
            self.twl_calc.sync_time()
            self.daytime = True

            if Config.gsm_enabled:
                if not self.messenger.is_power_on():
                    self.messenger.turn_on_modem()

                sms_text = 'Good morning! :)\n' \
                           'SkyScanner just started.\n' \
                           'Available space: {} GB'.format(self.get_available_free_space())

                self.messenger.send_sms(Config.gsm_phone_no, sms_text)

    def do_sunset_operations(self):
        """
        Execute the needed operations after sunset.

        Once it's sunset, sets `daytime` attribute to False and sends a sms text reporting the device status.
        If there's any image stored in `storage_path`, it would compress them and save it in `storage_path`..
        """
        if self.daytime:
            logger.debug('Daytime is over!')
            self.twl_calc.sync_time()
            self.daytime = False
            self.check_main_storage()

            if Config.store_locally:
                self.compress_storage()

            if Config.gsm_enabled:
                if not self.messenger.is_power_on():
                    self.messenger.turn_on_modem()

                sms_text = 'Good evening! :)\n' \
                           'SkyScanner is done for today.\n' \
                           'Available space: {} GB'.format(self.get_available_free_space())

                self.messenger.send_sms(Config.gsm_phone_no, sms_text)

    def watch_time(self):
        """
        Check the time to execute the sunrise/sunset operations.

        It also assigns a new day order to `day_of_year` attribute right after the midnight.
        """
        curr_time = dt.datetime.utcnow()

        if self.sunrise < curr_time.time() < self.sunset:
            self.do_sunrise_operations()
        else:
            self.do_sunset_operations()
            # check if the day has changed
            if curr_time.timetuple().tm_yday != self.day_of_year:
                self.day_of_year = curr_time.timetuple().tm_yday
                try:
                    self.sunrise, self.sunset = self.twl_calc.get_twilight_times_by_day(day_of_year=self.day_of_year)
                except Exception as e:
                    logger.error(f'New sunrise/sunset times could not be assigned!\n{e}')

    def run_offline(self):
        """
        Run the watching, writing and thumbnail-uploading operations recurrently in multiple jobs in offline mode.
        """

        logger.info('Time watcher job started: Recurring every 30 seconds.')
        sched.add_job(self.watch_time, 'cron', second='*/30')

        logger.info(f'Writer job started: Recurring every {Config.cap_interval} seconds')
        sched.add_job(self.execute_and_store, 'cron', second=f'*/{Config.cap_interval}')

        if Config.thumbnail_enabled:
            logger.info(f'Thumbnail uploader job started: Recurring every {Config.thumbnail_interval} minutes.')
            sched.add_job(self.send_thumbnail, 'cron', minute=f'*/{Config.thumbnail_interval}')

        sched.start()

    def run_online(self):
        """
        Run the watching, writing and thumbnail-uploading operations recurrently in multiple jobs in online mode.
        """
        logger.info('Time watcher job started: Recurring every 30 seconds.')
        sched.add_job(self.watch_time, 'cron', second='*/30')

        logger.info(f'Uploader job started: Recurring every {Config.cap_interval} seconds.')
        sched.add_job(self.execute_and_upload, 'cron', second=f'*/{Config.cap_interval}')

        logger.info('Retriever job started: Recurring every 15 seconds.')
        sched.add_job(self.check_upload_stack, 'cron', second='*/15')

        logger.info('Disk checker job started: Recurring every 15 minute.')
        sched.add_job(self.check_temp_storage, 'cron', minute='*/5')

        sched.start()

    def main(self):
        """
        Run the device in offline mode if autonomous mode is True, otherwise in online mode.
        """
        if Config.store_locally:
            self.run_offline()
        else:
            self.run_online()


if __name__ == '__main__':
    app = SkyScanner()
    app.run_online()
