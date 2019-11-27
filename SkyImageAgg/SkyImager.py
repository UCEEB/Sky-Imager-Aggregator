#!/usr/bin/python3
import datetime as dt
import glob
import shutil
import os
import time
from os.path import dirname
from os.path import join
from queue import LifoQueue

from apscheduler.schedulers.blocking import BlockingScheduler

from SkyImageAgg import Utils
from SkyImageAgg.Collectors.GeoVisionCam import GeoVisionCam as IPCamera
from SkyImageAgg.Collectors.IrradianceSensor import IrrSensor
from SkyImageAgg.Collectors.RpiCam import RpiCam
from SkyImageAgg.Configuration import Configuration
from SkyImageAgg.Controller import Controller
from SkyImageAgg.GSM import GPRS
from SkyImageAgg.GSM import Messenger
from SkyImageAgg.Logger import Logger
from SkyImageAgg.Preprocessor import ImageProcessor

_parent_dir = dirname(dirname(__file__))


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
    config = Configuration(config_file=join(_parent_dir, 'config.ini'))
    logger = Logger(name='SkyScanner')

    if config.lcd_display:
        lcd = Logger(name='LCD')
        lcd.add_display_handler(header='   SkyScanner   ')

    def __init__(self):
        """
        Initializes a SkyScanner instance.
        """
        if self.config.log_to_console:
            self.logger.add_stream_handler()

        if self.config.log_path:
            log_file_path = join(self.config.log_path, self.logger.name)
            self.logger.add_timed_rotating_file_handler(log_file=log_file_path)

        if self.config.INFLX_mode:
            self.logger.add_remote_handler(
                username=self.config.INFLX_user,
                pwd=self.config.INFLX_pwd,
                host=self.config.INFLX_host,
                database=self.config.INFLX_db,
                measurement=self.config.INFLX_measurement,
                tags={
                    'latitude': self.config.camera_latitude,
                    'longitude': self.config.camera_longitude,
                    'host': os.uname()[1]
                }
            )

        super().__init__(
            server=self.config.server,
            client_id=self.config.client_id,
            latitude=self.config.camera_latitude,
            longitude=self.config.camera_longitude,
            altitude=self.config.camera_altitude,
            auth_key=self.config.key,
            storage_path=self.config.storage_path,
            temp_storage_path=self.config.temp_storage_path,
            time_format=self.config.time_format,
            logger=self.logger
        )
        sync_time(self.config.ntp_server)

        if self.config.integrated_cam:
            self.cam = RpiCam()
        else:
            self.cam = IPCamera(self.config.cam_address)
            self.cam.login(self.config.cam_username, self.config.cam_pwd)

        if self.config.light_sensor:
            self.irr_sensor = IrrSensor(
                port=self.config.MODBUS_port,
                address=self.config.MODBUS_sensor_address,
                baudrate=self.config.MODBUS_baudrate,
                bytesize=self.config.MODBUS_bytesize,
                parity=self.config.MODBUS_parity,
                stopbits=self.config.MODBUS_stopbits
            )

        self.set_image_processor(
            raw_input_arr=self.cam.cap_pic(output='array'),  # cap first pic for testing and setup
            mask_path=self.config.mask_path,
            output_size=self.config.output_image_size,
            jpeg_quality=self.config.jpeg_quality
        )
        self.messenger = Messenger(logger=self.logger)
        self.gprs = GPRS(ppp_config_file=self.config.GSM_ppp_config_file, logger=self.logger)
        self.upload_stack = LifoQueue(maxsize=20)
        self.day_of_year = dt.datetime.utcnow().timetuple().tm_yday
        self.sunrise, self.sunset = self.get_twilight_times_by_day(day_of_year=self.day_of_year)
        self.daytime = False
        self.sched = BlockingScheduler()

    def scan(self):
        """
        Takes a photo from sky and assigns a name (timestamp) and a path to it.

        Returns
        -------
        `(str, str, numpy.array)`
            a tuple of name (timestamp), path and the corresponding image array.
        """
        # store the current time according to the time format
        cap_time = dt.datetime.utcnow().strftime(self.config.time_format)
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
        if self.daytime or self.config.night_mode:
            # capture the image and set the proper name and path for it
            cap_time, img_path, img_arr = self.scan()
            # preprocess the image
            preproc_img = self.preprocess(img_arr)
            # try to upload the image to the server, if failed, save it to storage
            try:
                self.upload_image(preproc_img, time_stamp=cap_time)
                self.logger.info('Uploading {}.jpg was successful!'.format(cap_time))
                self.lcd.info(('{}.jpg'.format(cap_time[-11:]), ' uploaded... '))
            except Exception:
                self.logger.warning(
                    'Couldn\'t upload {}.jpg! Queueing for another try!'.format(cap_time), exc_info=1
                )
                self.lcd.warning(('{}.jpg'.format(cap_time[-11:]), ' failed! '))
                if not self.upload_stack.full():
                    self.upload_stack.put((cap_time, img_path, preproc_img))
                else:
                    self.logger.info('The upload stack is full! Storing the image...')
                    self.save_as_pic(preproc_img, img_path)
                    self.logger.info('{}.jpg was stored successfully!'.format(cap_time))

    def execute_and_store(self):
        """
        Recurrently takes a picture from sky, pre-processes it and stores it in `storage_path` directory
        during the daytime.
        """
        if self.daytime or self.config.night_mode:
            # capture the image and set the proper name and path for it
            cap_time, img_path, img_arr = self.scan()
            # preprocess the image
            preproc_img = self.preprocess(img_arr)
            # write it in storage
            try:
                self.save_as_pic(preproc_img, img_path)
                self.logger.info('{}.jpg was stored successfully!'.format(cap_time))
            except Exception:
                self.logger.critical('Couldn\'t write {}.jpg on disk!'.format(cap_time), exc_info=1)

    def send_thumbnail(self):
        """
        Recurrently takes a picture from sky, pre-processes it and makes a thumbnail out of the image array.
        Then it tries to upload it during the daytime every hour.
        """
        if self.daytime or self.config.night_mode:
            # capture the image and set the proper name and path for it
            cap_time, img_path, img_arr = self.scan()
            # preprocess the image
            preproc_img = self.preprocess(img_arr)
            # create thumbnail
            thumbnail = self.make_thumbnail(preproc_img)

            try:
                self.upload_thumbnail(thumbnail, time_stamp=cap_time)
                self.logger.info('Uploading {}.jpg thumbnail was successful!'.format(cap_time))
            except Exception:
                self.logger.error('Couldn\'t upload {}.jpg thumbnail! '.format(cap_time), exc_info=1)

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
        Checks the `upload_stack` every 5 seconds to retry uploading the images that were not successfully
        uploaded to the server.
        """
        if not self.upload_stack.empty():
            cap_time, img_path, img_arr = self.upload_stack.get()

            try:
                self.retry_uploading_image(image=img_arr, time_stamp=cap_time)
                self.logger.info('retrying to upload {}.jpg was successful!'.format(cap_time))
            except Exception as e:
                self.logger.warning(
                    'retrying to upload {}.jpg failed! Storing in temporary storage...'.format(cap_time),
                    exc_info=1
                )
                self.save_as_pic(image_arr=img_arr, output_name=img_path)
                self.logger.debug('{}.jpg was successfully stored!'.format(cap_time))

    def check_temp_storage(self):
        """
        Checks the `storage_path` every 10 seconds to try uploading the stored images. If it failed, waits
        another 30 seconds.
        """
        if not os.path.exists(self.storage_path):
            os.mkdir(self.storage_path)  # create the main storage if not exist

        if not os.path.exists(self.temp_storage_path):
            os.mkdir(self.temp_storage_path)  # create the temp storage if not exist

        if len(os.listdir(self.temp_storage_path)) == 0:
            pass

        else:
            for img in glob.iglob(os.path.join(self.temp_storage_path, '*.jpg')):
                timestamp = os.path.split(img)[-1].split('.')[0]

                try:
                    self.logger.debug('retrying to upload {} to the server...'.format(img))
                    self.retry_uploading_image(image=img, time_stamp=timestamp)  # try to re-upload
                    self.logger.debug('{} was successfully uploaded from SD card to the server.'.format(img))
                    os.remove(img)
                    self.logger.debug('{} was removed from disk.'.format(img))
                except Exception as e:
                    self.logger.info('retry failed! moving {} to main storage'.format(img), exc_info=1)
                    shutil.move(img, self.storage_path)


    def do_sunrise_operations(self):
        """
        Once it's sunrise, sets `daytime` attribute to True and sends a sms text reporting the device status.
        """
        if not self.daytime:
            self.logger.debug('It\'s daytime!')
            sync_time(self.config.ntp_server)
            self.daytime = True

            if not self.messenger.is_power_on():
                self.messenger.turn_on_modem()

            sms_text = 'Good morning! :)\n' \
                       'SkyScanner just started.\n' \
                       'Available space: {} GB'.format(self.get_available_free_space())

            self.messenger.send_sms(self.config.GSM_phone_no, sms_text)

    def do_sunset_operations(self):
        """
        Once it's sunset, sets `daytime` attribute to False and sends a sms text reporting the device status.
        If there's any image stored in `storage_path`, it would compress them and save it in `storage_path`..
        """
        if self.daytime:
            self.logger.debug('Daytime is over!')
            sync_time(self.config.ntp_server)
            self.daytime = False

            if self.config.autonomous_mode:
                self.compress_storage()

            if not self.messenger.is_power_on():
                self.messenger.turn_on_modem()

            sms_text = 'Good evening! :)\n' \
                       'SkyScanner is done for today.\n' \
                       'Available space: {} GB'.format(self.get_available_free_space())

            self.messenger.send_sms(self.config.GSM_phone_no, sms_text)

        elif self.config.night_mode:
            self.logger.debug('Device is set on night mode: Scanning night sky...')

        else:
            self.logger.debug('Device is on sleep mode: Waiting for the sunrise...')

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
                    self.logger.error('New sunrise/sunset times could not be assigned!', e)

    def run_offline(self):
        """
        Concurrently Runs the watching, writing and thumbnail-uploading operations recurrently in multiple jobss
         in offline mode. (data collection mode)
        """

        self.logger.info('Time watcher job started: Recurring every 30 seconds.')
        self.sched.add_job(self.watch_time, 'cron', second='*/30')

        self.logger.info('Writer job started: Recurring every {} seconds'.format(self.config.cap_mod))
        self.sched.add_job(self.execute_and_store, 'cron', second='*/{}'.format(self.config.cap_mod))

        self.logger.info('Thumbnail uploader job started: Recurring every {} minutes.'.format(
            self.config.thumbnailing_time_gap
        ))
        self.sched.add_job(self.execute_and_store, 'cron', minute='*/{}'.format(self.config.thumbnailing_time_gap))

        self.sched.start()

    def run_online(self):
        """
        Concurrently Runs the watching, writing and thumbnailUploading operations recurrently in multiple jobs
        in online mode.
        """
        self.logger.info('Time watcher job started: Recurring every 30 seconds.')
        self.sched.add_job(self.watch_time, 'cron', second='*/30')

        self.logger.info('Uploader job started: Recurring every {} seconds.'.format(self.config.cap_mod))
        self.sched.add_job(self.execute_and_upload, 'cron', second='*/{}'.format(self.config.cap_mod))

        self.logger.info('Retriever job started: Recurring every 15 seconds.')
        self.sched.add_job(self.check_upload_stack, 'cron', second='*/15')

        self.logger.info('Disk checker job started: Recurring every 15 minute.')
        self.sched.add_job(self.check_temp_storage, 'cron', minute='*/15')

        self.sched.start()

    def main(self):
        """
        Runs the device in offline mode if autonomous mode is True, otherwise in online mode.
        """
        if self.config.autonomous_mode:
            self.run_offline()
        else:
            self.run_online()


if __name__ == '__main__':
    app = SkyScanner()
    app.main()
