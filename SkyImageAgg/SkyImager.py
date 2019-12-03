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
from SkyImageAgg.Configuration import Configuration
from SkyImageAgg.Controller import Controller
from SkyImageAgg.GSM import GPRS
from SkyImageAgg.GSM import has_internet
from SkyImageAgg.GSM import Messenger
from SkyImageAgg.Logger import Logger
from SkyImageAgg.Preprocessor import ImageProcessor

_base_dir = dirname(dirname(__file__))

# executors for job schedulers indicating the number of threads availeble for each pool
executors = {
    'default': ThreadPoolExecutor(30),   # max threads: 30
}

# Configuration settings
config = Configuration(config_file=join(_base_dir, 'config.ini'))

# Application logger
logger = Logger(name='SkyScanner')

if config.log_to_console:
    logger.add_stream_handler()

if config.log_path:
    log_file_path = join(config.log_path, logger.name)
    logger.add_timed_rotating_file_handler(log_file=log_file_path)

if config.INFLX_mode:
    logger.add_influx_handler(
        username=config.INFLX_user,
        pwd=config.INFLX_pwd,
        host=config.INFLX_host,
        database=config.INFLX_db,
        measurement=config.INFLX_measurement,
        tags={
            'latitude': config.camera_latitude,
            'longitude': config.camera_longitude,
            'host': os.uname()[1]
        }
    )

# Logger object for streaming the specific short logs to the RPi LCD display (2x16)
if config.lcd_display:
    lcd_logger = Logger(name='LCD')
    lcd_logger.add_display_handler('   SkyScanner   ')
else:
    lcd_logger = logging.getLogger(name='LCD')
    lcd_logger.addHandler(logging.NullHandler())

# Logger object to collect irradiance sensor data and send the to an influxDB server
if config.light_sensor:
    sensor_logger = Logger(name='IrrSensor')
    sensor_logger.add_sensor_handler(
        username=config.INFLX_user,
        pwd=config.INFLX_pwd,
        host=config.INFLX_host,
        database=config.INFLX_db,
        measurement=config.INFLX_measurement,
        tags={
            'latitude': config.camera_latitude,
            'longitude': config.camera_longitude,
            'host': os.uname()[1]
        }
    )

if config.log_path:
    log_file_path = join(config.log_path, sensor_logger.name)
    sensor_logger.add_timed_rotating_file_handler(log_file=log_file_path)

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
    properties. This class calls the Configuration class to initialize an instance using Configuration attributes.
    Next, It collects data by means of the modules in the Collectors package including RpiCam and  other available
    cameras and sensors.  Using  ImageProcessor, it preprocesses  the image data  collected by camera  and  stores
    them locally or uploads it to the server. The class can be run in  two modes, online  and offline. The  online
    mode is run when the device is required to upload the data into a server and the offline mode is used when the
    data need  to be stored locally for data collection purposes.

    Attributes
    ----------
    config : `Configuration`
        an instance of `Configuration` class for calling the configuration variables from config.ini.
    logger : `logging`
        an instance of `logging` to log the events throughout the class.
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
            server=config.server,
            client_id=config.client_id,
            latitude=config.camera_latitude,
            longitude=config.camera_longitude,
            altitude=config.camera_altitude,
            auth_key=config.key,
            storage_path=config.storage_path,
            temp_storage_path=config.temp_storage_path,
            time_format=config.time_format,
            logger=None,
            twilight_coll_in_memory=False,
            twilight_coll_file=join(_base_dir, 'twilight_times.pkl')
        )

        sync_time(config.ntp_server)

        if self.has_location_changed():
            # if device location changed or twilight times have not been collected
            logger.info('Collecting twilight times within a year...')
            self.collect_annual_twilight_times()

        if config.integrated_cam:
            self.cam = RpiCam()
        else:
            self.cam = IPCamera(config.cam_address)
            self.cam.login(config.cam_username, config.cam_pwd)

        if config.light_sensor:
            self.irr_sensor = IrrSensor(
                port=config.MODBUS_port,
                address=config.MODBUS_sensor_address,
                baudrate=config.MODBUS_baudrate,
                bytesize=config.MODBUS_bytesize,
                parity=config.MODBUS_parity,
                stopbits=config.MODBUS_stopbits
            )

        self.set_image_processor(
            raw_input_arr=self.cam.cap_pic(output='array'),  # cap first pic for testing and setup
            mask_path=config.mask_path,
            output_size=config.output_image_size,
            jpeg_quality=config.jpeg_quality
        )

        if config.GSM_module:
            self.messenger = Messenger(logger=logger)
            self.gprs = GPRS(ppp_config_file=config.GSM_ppp_config_file, logger=logger)
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
        cap_time = dt.datetime.utcnow().strftime(config.time_format)
        # set the path to save the image
        output_path = os.path.join(self.temp_storage_path, cap_time)
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
        if self.daytime or config.night_mode:
            # capture the image and set the proper name and path for it
            cap_time, img_path, img_arr, sensor_data = self.scan()
            # preprocess the image
            preproc_img = self.preprocess(img_arr)
            # try to upload the image to the server, if failed, save it to storage
            try:
                self.upload_image(preproc_img, time_stamp=cap_time)
                logger.info('Uploading {}.jpg was successful!'.format(cap_time))
                lcd_display.info(('{}.jpg'.format(cap_time[-11:]), ' uploaded... '))
            except ConnectionError:
                lcd_display.warning(('{}.jpg'.format(cap_time[-11:]), '    failed!!!  '))

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
                    lcd_display.info(('{}.jpg'.format(cap_time[-11:]), '    stored...   '))

    def execute_and_store(self):
        """
        Recurrently takes a picture from sky, pre-processes it and stores it in `storage_path` directory
        during the daytime.
        """
        if self.daytime or config.night_mode:
            # capture the image and set the proper name and path for it
            cap_time, img_path, img_arr = self.scan()
            # preprocess the image
            preproc_img = self.preprocess(img_arr)
            # write it in storage
            try:
                self.save_as_pic(preproc_img, img_path)
                logger.info('{}.jpg was stored!'.format(cap_time))
                lcd_display.info(('{}.jpg'.format(cap_time[-11:]), '    stored...   '))
            except Exception:
                logger.critical('Couldn\'t write {}.jpg on disk!'.format(cap_time), exc_info=1)
                lcd_display.warning(('{}.jpg'.format(cap_time[-11:]), '     failed!!!  '))

    def send_thumbnail(self):
        """
        Recurrently takes a picture from sky, pre-processes it and makes a thumbnail out of the image array.
        Then it tries to upload it during the daytime every hour.
        """
        if self.daytime or config.night_mode:
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
        if not len(os.listdir(self.temp_storage_path)) == 0:
            for img in glob.iglob(os.path.join(self.temp_storage_path, '*.jpg')):
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
            sync_time(config.ntp_server)
            self.daytime = True

            if config.GSM_module:
                if not self.messenger.is_power_on():
                    self.messenger.turn_on_modem()

                sms_text = 'Good morning! :)\n' \
                           'SkyScanner just started.\n' \
                           'Available space: {} GB'.format(self.get_available_free_space())

                self.messenger.send_sms(config.GSM_phone_no, sms_text)

    def do_sunset_operations(self):
        """
        Once it's sunset, sets `daytime` attribute to False and sends a sms text reporting the device status.
        If there's any image stored in `storage_path`, it would compress them and save it in `storage_path`..
        """
        if self.daytime:
            logger.debug('Daytime is over!')
            sync_time(config.ntp_server)
            self.daytime = False
            self.check_main_storage()

            if config.autonomous_mode:
                self.compress_storage()

            if config.GSM_module:
                if not self.messenger.is_power_on():
                    self.messenger.turn_on_modem()

                sms_text = 'Good evening! :)\n' \
                           'SkyScanner is done for today.\n' \
                           'Available space: {} GB'.format(self.get_available_free_space())

                self.messenger.send_sms(config.GSM_phone_no, sms_text)

        elif config.night_mode:
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

        logger.info('Writer job started: Recurring every {} seconds'.format(config.cap_mod))
        self.sched.add_job(self.execute_and_store, 'cron', second='*/{}'.format(config.cap_mod))

        logger.info('Thumbnail uploader job started: Recurring every {} minutes.'.format(
            config.thumbnailing_time_gap
        ))
        self.sched.add_job(self.send_thumbnail, 'cron', minute='*/{}'.format(config.thumbnailing_time_gap))

        self.sched.start()

    def run_online(self):
        """
        Concurrently Runs the watching, writing and thumbnailUploading operations recurrently in multiple jobs
        in online mode.
        """
        logger.info('Time watcher job started: Recurring every 30 seconds.')
        self.sched.add_job(self.watch_time, 'cron', second='*/30')

        logger.info('Uploader job started: Recurring every {} seconds.'.format(config.cap_mod))
        self.sched.add_job(self.execute_and_upload, 'cron', second='*/{}'.format(config.cap_mod))

        logger.info('Retriever job started: Recurring every 15 seconds.')
        self.sched.add_job(self.check_upload_stack, 'cron', second='*/15')

        logger.info('Disk checker job started: Recurring every 15 minute.')
        self.sched.add_job(self.check_temp_storage, 'cron', minute='*/15')

        self.sched.start()

    def main(self):
        """
        Runs the device in offline mode if autonomous mode is True, otherwise in online mode.
        """
        if config.autonomous_mode:
            self.run_offline()
        else:
            self.run_online()


if __name__ == '__main__':
    app = SkyScanner()
    app.main()
