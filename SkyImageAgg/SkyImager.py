#!/usr/bin/python3
import datetime as dt
import glob
import logging
import os
import shutil
from os.path import dirname
from os.path import join
from queue import LifoQueue

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler

from SkyImageAgg import Utils
from SkyImageAgg.Collectors.GeoVisionCam import GeoVisionCam as IPCamera
from SkyImageAgg.Collectors.IrradianceSensor import IrrSensor
from SkyImageAgg.Collectors.RpiCam import RpiCam
from SkyImageAgg.Configuration import Config
from SkyImageAgg.Controller import Controller
from SkyImageAgg.GSM import GPRS
from SkyImageAgg.GSM import has_internet
from SkyImageAgg.GSM import Messenger
from SkyImageAgg.Logger import Logger
from SkyImageAgg.Preprocessor import ImageProcessor

_base_dir = dirname(dirname(__file__))
_tmp_dir = join(_base_dir, 'temp')

if not os.path.exists(_tmp_dir):
    os.mkdir(_tmp_dir)

# executors for job schedulers
executors = {'default': ThreadPoolExecutor(30)}  # max threads: 30

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

# Logger object for streaming the specific short logs to the RPi LCD display (2x16)
if Config.lcd_display:
    lcd_logger = Logger(name='LCD')
    lcd_logger.add_display_handler('   SkyScanner   ')
else:
    lcd_logger = logging.getLogger(name='LCD')
    lcd_logger.addHandler(logging.NullHandler())

# Logger object to collect irradiance sensor data and send the to an influxDB server
if Config.irr_sensor_enabled:
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


def sync_time(ntp_server):
    """
    Synchronizes device time with UTC.

    Parameters
    ----------
    ntp_server : `str`
        the NTP server address

    Notes
    -----
        You need to install ntpd package on your device.
        see:
        https://raspberrytips.com/time-sync-raspberry-pi/
    """
    os.system('sudo /usr/sbin/ntpd {}'.format(ntp_server))


class SkyScanner(Controller, ImageProcessor):
    """
    Captures pictures from sky and stores them locally or uploads them to a remote server.

    SkyScanner  coordinates different  other classes such as Controller  and  ImageProcessor by  inheriting  their
    properties. This class calls the Config class to initialize an instance using Config attributes.
    Next, It collects data by means of the modules in the Collectors package including RpiCam and  other available
    cameras and sensors.  Using  ImageProcessor, it preprocesses  the image data  collected by camera  and  stores
    them locally or uploads it to the server. The class can be run in  two modes, online  and offline. The  online
    mode is run when the device is required to upload the data into a server and the offline mode is used when the
    data need  to be stored locally for data collection purposes.

    Attributes
    ----------
    cam : `IPCamera` or `RpiCam`
        an instance of `Collectors.Cam` for capturing images.
    irr_sensor : `IrrSensor`
        an instance of `Collectors.IrradianceSensor.IrrSensor` to collect irradiance data.
    messenger : `Messenger`
        an instance of `Messenger` class for sending sms texts.
    gprs : `GPRS`
        an instance of `GPRS` class for connecting the device to internet through GPRS service.
    upload_stack : `LifoQueue`
        a LIFO stack for storing failed uploads to be accessible by uploader job.
    day_of_year : `int`
        the day of year (DOY) is the sequential day number starting with day 1 on January 1st.
    sunrise : `datetime.time`
        sunrise time.
    sunset : `datetime.time`
        sunset time.
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
            latitude=Config.camera_latitude,
            longitude=Config.camera_longitude,
            altitude=Config.camera_altitude,
            auth_key=Config.key,
            storage_path=Config.storage_path,
            time_format=Config.time_format,
            logger=None,
            in_memory=False,
            file=join(_base_dir, 'twilight_times.pkl')
        )

        sync_time(Config.ntp_server)

        if self.has_location_changed():
            # if device location changed or twilight times have not been collected
            logger.info('Collecting twilight times within a year...')
            self.collect_annual_twilight_times()

        if Config.RPi_cam:
            self.cam = RpiCam()
        else:
            self.cam = IPCamera(Config.cam_address)
            self.cam.login(Config.cam_username, Config.cam_pwd)

        if Config.irr_sensor_enabled:
            self.irr_sensor = IrrSensor(
                port=Config.irr_sensor_port,
                address=Config.irr_sensor_address,
                baudrate=Config.irr_sensor_baudrate,
                bytesize=Config.irr_sensor_bytesize,
                parity=Config.irr_sensor_parity,
                stopbits=Config.irr_sensor_stopbits
            )

        self.set_image_processor(
            raw_input_arr=self.cam.cap_pic(output='array'),  # cap first pic for testing and setup
            mask_path=Config.mask_path,
            output_size=Config.image_size,
            jpeg_quality=Config.jpeg_quality
        )

        if Config.gsm_enabled:
            self.messenger = Messenger(logger=logger)
            self.gprs = GPRS(ppp_config_file=Config.gsm_ppp_config_file, logger=logger)
        else:
            self.messenger = None
            self.gprs = None

        self.upload_stack = LifoQueue(maxsize=5)
        self.day_of_year = dt.datetime.utcnow().timetuple().tm_yday
        self.sunrise, self.sunset = self.get_twilight_times_by_day(day_of_year=self.day_of_year)
        self.daytime = False
        self.sched = BlockingScheduler(executors=executors)

    def scan(self):
        """
        Takes a photo from sky and assigns a name (timestamp) and a path to it.

        Returns
        -------
        `(str, str, numpy.array)`
            a tuple of name (timestamp), path and the corresponding image array.
        """
        # store the current time according to the time format
        cap_time = dt.datetime.utcnow().strftime(Config.time_format)
        # set the path to save the image
        output_path = os.path.join(_tmp_dir, cap_time)

        if Config.irr_sensor_enabled:
            # get sensor data (irr, ext_temp, cell_temp)
            try:
                sensor_data = self.irr_sensor.get_data()
                sensor_logger.info(
                    {
                        'timestamp': cap_time,
                        'irradiance': sensor_data[0],  # irradiance (W/m^2)
                        'ext_temp': sensor_data[1],  # external temperature (°C)
                        'cell_temp': sensor_data[2]  # cell temperature (°C)
                    }
                )
            except Exception:
                logger.error('Couldn\'t collect data from irradiance sensor', exc_info=1)

        return cap_time, output_path, self.cam.cap_pic()

    def preprocess(self, image_arr):
        """
        Crops and masks the taken image from sky.

        Parameters
        ----------
        image_arr : `numpy.array`

        Returns
        -------
        `numpy.array`
            proprocessed image array.
        """
        # Crop
        image_arr = self.crop(image_arr)
        # Apply mask
        image_arr = self.apply_binary_mask(image_arr)
        return image_arr

    def execute_and_upload(self):
        """
        Takes a picture from sky, pre-processes it and tries to upload it to the server. if failed, it puts
        the image array and its metadata in `upload_stack`.
        """
        if self.daytime or Config.night_mode:
            # capture the image and set the proper name and path for it
            cap_time, img_path, img_arr = self.scan()
            # preprocess the image
            preproc_img = self.preprocess(img_arr)
            # try to upload the image to the server, if failed, save it to storage
            try:
                self.upload_image(preproc_img, time_stamp=cap_time)
                logger.info('Uploading {}.jpg was successful!'.format(cap_time))
                lcd_logger.info(('{}.jpg'.format(cap_time[-11:]), ' uploaded... '))
            except ConnectionError:
                lcd_logger.warning(('{}.jpg'.format(cap_time[-11:]), '    failed!!!  '))

                if not self.upload_stack.full():
                    logger.warning(
                        'Couldn\'t upload {}.jpg! Queueing for another try!'.format(cap_time),
                        exc_info=1
                    )
                    self.upload_stack.put((cap_time, img_path, preproc_img))
                else:
                    logger.info('The upload stack is full! Storing the image...')
                    self.save_as_pic(preproc_img, img_path)  # write array on the disk as jpg
                    logger.info('{}.jpg was stored in temp storage!'.format(cap_time))
                    lcd_logger.info(('{}.jpg'.format(cap_time[-11:]), '    stored...   '))

    def execute_and_store(self):
        """
        Recurrently takes a picture from sky, pre-processes it and stores it in `storage_path` directory
        during the daytime.
        """
        if self.daytime or Config.night_mode:
            # capture the image and set the proper name and path for it
            cap_time, img_path, img_arr = self.scan()
            # preprocess the image
            preproc_img = self.preprocess(img_arr)
            # write it in storage
            try:
                self.save_as_pic(preproc_img, img_path)
                logger.info('{}.jpg was stored!'.format(cap_time))
                lcd_logger.info(('{}.jpg'.format(cap_time[-11:]), '    stored...   '))
            except Exception:
                logger.critical('Couldn\'t write {}.jpg on disk!'.format(cap_time), exc_info=1)
                lcd_logger.warning(('{}.jpg'.format(cap_time[-11:]), '     failed!!!  '))

    def send_thumbnail(self):
        """
        Recurrently takes a picture from sky, pre-processes it and makes a thumbnail out of the image array.
        Then it tries to upload it during the daytime every hour.
        """
        if self.daytime or Config.night_mode:
            # capture the image and set the proper name and path for it
            cap_time, img_path, img_arr = self.scan()
            # preprocess the image
            preproc_img = self.preprocess(img_arr)
            # create thumbnail
            thumbnail = self.make_thumbnail(preproc_img)

            try:
                self.upload_thumbnail(thumbnail, time_stamp=cap_time)
                logger.info('Uploading {}.jpg thumbnail was successful!'.format(cap_time))
            except Exception:
                logger.error('Couldn\'t upload {}.jpg thumbnail! '.format(cap_time), exc_info=1)

    @Utils.retry_on_failure(attempts=2)
    def retry_uploading_image(self, image, time_stamp):
        """
        Retries to upload a given image for a given number of attempts passed through the decorator.

        Parameters
        ----------
        image : `numpy.array` or `str`
            the image array of a given image or the path to it if written on the disk.
        time_stamp : `datetime`
            the timestamp of the `image`
        """
        self.upload_image(image, time_stamp)

    def check_upload_stack(self):
        """
        Checks the `upload_stack` every 15 seconds to retry uploading the images that were not successfully
        uploaded to the server.
        """
        if not self.upload_stack.empty():
            cap_time, img_path, img_arr = self.upload_stack.get()

            try:
                self.retry_uploading_image(image=img_arr, time_stamp=cap_time)
                logger.info('retrying to upload {}.jpg was successful!'.format(cap_time))
            except Exception as e:
                logger.warning(
                    'retrying to upload {}.jpg failed! Storing in temp storage...'.format(cap_time),
                    exc_info=1
                )
                self.save_as_pic(image_arr=img_arr, output_name=img_path)
                logger.debug('{}.jpg was stored in temp storage!'.format(cap_time))

    def check_temp_storage(self):
        """
        Checks the `storage_path` every 10 seconds to try uploading the stored images. If it failed, waits
        another 30 seconds.
        """
        if not len(os.listdir(_tmp_dir)) == 0:
            for img in glob.iglob(os.path.join(_tmp_dir, '*.jpg')):
                timestamp = os.path.split(img)[-1].split('.')[0]
                try:
                    self.retry_uploading_image(image=img, time_stamp=timestamp)  # try to re-upload
                    logger.debug(
                        '{} was uploaded from temp storage to the server.'.format(img)
                    )
                    os.remove(img)
                    logger.debug('{} was removed from temp storage.'.format(img))
                except Exception as e:
                    logger.info('retry failed! moving {} to main storage'.format(img), exc_info=1)
                    shutil.move(img, self.storage_path)

    def check_main_storage(self):
        if has_internet():
            for img in glob.iglob(os.path.join(self.storage_path, '*.jpg')):
                timestamp = os.path.split(img)[-1].split('.')[0]
                try:
                    self.upload_image(image=img, time_stamp=timestamp)
                    logger.debug(
                        '{} was uploaded!'.format(img)
                    )
                    os.remove(img)
                    logger.debug('{} was removed from main storage.'.format(img))
                except Exception as e:
                    logger.exception('retry failed!'.format(img), exc_info=1)

    def do_sunrise_operations(self):
        """
        Once it's sunrise, sets `daytime` attribute to True and sends a sms text reporting the device status.
        """
        if not self.daytime:
            logger.debug('It\'s daytime!')
            sync_time(Config.ntp_server)
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
        Once it's sunset, sets `daytime` attribute to False and sends a sms text reporting the device status.
        If there's any image stored in `storage_path`, it would compress them and save it in `storage_path`..
        """
        if self.daytime:
            logger.debug('Daytime is over!')
            sync_time(Config.ntp_server)
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

        elif Config.night_mode:
            logger.debug('Device is set on night mode: Scanning night sky...')

        else:
            logger.debug('Device is on sleep mode: Waiting for the sunrise...')

    def watch_time(self):
        """
        Recurrently checks the time to execute the sunrise/sunset operations. It also assigns a new day order
        to `day_of_year` attribute right after the midnight.
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
                    self.sunrise, self.sunset = self.get_twilight_times_by_day(day_of_year=self.day_of_year)
                except Exception as e:
                    logger.error('New sunrise/sunset times could not be assigned!', e)

    def run_offline(self):
        """
        Concurrently Runs the watching, writing and thumbnail-uploading operations recurrently in multiple jobss
         in offline mode. (data collection mode)
        """

        logger.info('Time watcher job started: Recurring every 30 seconds.')
        self.sched.add_job(self.watch_time, 'cron', second='*/30')

        logger.info('Writer job started: Recurring every {} seconds'.format(Config.cap_interval))
        self.sched.add_job(self.execute_and_store, 'cron', second='*/{}'.format(Config.cap_interval))

        logger.info('Thumbnail uploader job started: Recurring every {} minutes.'.format(
            Config.thumbnail_interval
        ))
        self.sched.add_job(self.send_thumbnail, 'cron', minute='*/{}'.format(Config.thumbnail_interval))

        self.sched.start()

    def run_online(self):
        """
        Concurrently Runs the watching, writing and thumbnailUploading operations recurrently in multiple jobs
        in online mode.
        """
        logger.info('Time watcher job started: Recurring every 30 seconds.')
        self.sched.add_job(self.watch_time, 'cron', second='*/30')

        logger.info('Uploader job started: Recurring every {} seconds.'.format(Config.cap_interval))
        self.sched.add_job(self.execute_and_upload, 'cron', second='*/{}'.format(Config.cap_interval))

        logger.info('Retriever job started: Recurring every 15 seconds.')
        self.sched.add_job(self.check_upload_stack, 'cron', second='*/15')

        logger.info('Disk checker job started: Recurring every 15 minute.')
        self.sched.add_job(self.check_temp_storage, 'cron', minute='*/15')

        self.sched.start()

    def main(self):
        """
        Runs the device in offline mode if autonomous mode is True, otherwise in online mode.
        """
        if Config.store_locally:
            self.run_offline()
        else:
            self.run_online()


if __name__ == '__main__':
    app = SkyScanner()
    app.main()
