import os
import base64
import json
import hmac
import csv
import hashlib
import glob
import shutil
import pickle
import zipfile
import datetime as dt
from datetime import datetime

import requests
import cv2
from timeout_decorator import timeout
import numpy as np
from astral import Astral, Location

from SkyImageAgg.Processor import ImageProcessor
from SkyImageAgg.Collector import GeoVisionCam, RPiCam, IrrSensor
from SkyImageAgg.Logger import Logger

_parent_dir_ = os.path.dirname(os.path.dirname(__file__))


class TimeManager(Logger):
    """
    A class responsible to manage the time resources. `TimeManager` also inherits properties from `Logger` to pass
    a logger object to its child class `Controller`.

    Attributes
    ----------
    latitude : `float`
        the camera latitude
    longitude : `float`
        the camera longitude
    altitude : `float`
        the camera altitude

    Parameters
    ----------
    latitude : `float`
        the camera latitude
    longitude : `float`
        the camera longitude
    altitude : `float`
        the camera altitude
    log_dir: `str`
        the path to the log directory (default is None, storing no logs)
    stream: `boolean`
        True if the logs are to be stream on the console (default is True)
    """
    def __init__(
            self,
            camera_latitude,
            camera_longitude,
            camera_altitude,
            log_dir=None,
            stream=True
    ):
        super().__init__()
        self.set_logger(log_dir=log_dir, stream=stream)
        self.latitude = camera_latitude
        self.longitude = camera_longitude
        self.altitude = camera_altitude

    @staticmethod
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

    def find_sunrise_and_sunset_time(self, date=None):
        """
        Finds the sunrise and sunset time of a given date.

        Parameters
        ----------
        date : `datetime`
            the date (default is None, which will take the current date)

        Returns
        -------
        tuple of twilight times : `(datetime.time, datetime.time)`
            sunrise and sunset times
        """
        if not date:
            date = dt.datetime.now(dt.timezone.utc).date()

        astral = Astral()
        astral.solar_depression = 'civil'
        location = Location((
            'custom',
            'region',
            self.latitude,
            self.longitude,
            'UTC',
            self.altitude
        ))
        sun = location.sun(date=date)

        return sun['sunrise'].time(), sun['sunset'].time()

    def collect_annual_twilight_times(self):
        """
        Collects the annual sunrise/sunset times with respect to the location of the camera.

        Returns
        -------
        annual twilight times : `dict`
            a dictionary with day order as its keys and tuple of twilight times as its values
        """
        collection = {
            'geo_loc': (self.latitude,
                        self.longitude)
        }

        dates = np.arange(
            # 2020 is chosen as it's a leap year with 366 days
            dt.datetime(2020, 1, 1),
            dt.datetime(2021, 1, 1),
            dt.timedelta(days=1)
        ).astype(dt.datetime).tolist()

        self.logger.info('Collecting annual twilight times...')

        for date in dates:
            collection[date.timetuple().tm_yday] = self.find_sunrise_and_sunset_time(date=date)

        with open(os.path.join(_parent_dir_, 'annual_twilight_times.pkl'), 'wb') as file:
            pickle.dump(collection, file, protocol=pickle.HIGHEST_PROTOCOL)

        return collection

    @staticmethod
    def get_twilight_times_by_day(day_of_year):
        """
        Gets the sunrise/sunset times collected previously given the day of the year.

        Parameters
        ----------
        day_of_year : `int`
            The day of year (DOY) is the sequential day number starting with day 1 on January 1st.

        Returns
        -------
        tuple of twilight times : `(datetime.time, datetime.time)`
            sunrise and sunset times
        """
        with open(os.path.join(_parent_dir_, 'annual_twilight_times.pkl'), 'rb') as handle:
            col = pickle.load(handle)
        return col[day_of_year]

    @staticmethod
    def stamp_curr_time(time_format):
        """
        Gets the current time based on the specified format.

        Parameters
        ----------
        time_format : `str`
            the strftime format

        Returns
        -------
        current time : `datetime.time`
            the current time specified in `time_format`
        """
        return dt.datetime.utcnow().strftime(time_format)


class Controller(TimeManager, ImageProcessor):
    """
    A class responsible for performing IO and network operations. It inherits properties from `TimeManager` and
    `ImageProcessor` to pass their methods and attributes to its children such as `SkyScanner`.

    Attributes
    ----------
    cam_id : `int`
    image_quality : `int`
    key : `str`
    server : `str`
    time_format : `str`
    storage_path : `str`
    cam : `Collector.GeoVisionCam` or `Collector.RpiCam`

    Parameters
    ----------
    server : `str`
        the server that receives the photos taken from sky to perform further processing.
    camera_id : `int`
        the camera ID assigned by the vendor.
    camera_latitude : `float`
        latitude of the camera.
    camera_longitude : `float`
        longitude of the camera.
    camera_altitude : `float`
        the altitude of the camera.
    image_quality : `int`
        the desired jpeg quality for the taken image.
    auth_key : `str`
        the SHA-256 key provided by the vendor.
    storage_path : `str`
        the path to the storage directory.
    ext_storage_path : `str`
        the path to the external storage directory.
    time_format : `str`
        the time format.
    autonomous_mode : `boolean`
        True if the device is in offline mode, False otherwise (default is False).
    cam_address : `str`
        IP camera address.
    username : `str`
        IP camera username.
    pwd : `str`
        IP camera password.
    rpi_cam : `boolean`
        True if raspberry pi camera is used (default is False).
    log_dir : `str`
        the path to the directory that the logs are stored.
    log_stream : `boolean`
        True if logs are needed to be streamed to the console, False otherwise (silent).
    irradiance_sensor : `boolean`
        True if the irradiance sensor is attached to the device, False otherwise (default is False).
    sensor_port : `str`
        the port used for connecting the irradiance sensor to the device (default is None).
    sensor_address : `int`
        address of irradiance sensor (default is None).
    sensor_baudrate : `int`
        data transfer rate (default is None).
    sensor_bytesize : `int`
        the byte size of transferring data from sensor (default is None).
    sensor_pairity : `str`
        the sensor pairity (default is None).
    sensor_stopbits : `int`
        the sensor stopbits (default is None).
    """
    def __init__(
            self,
            server,
            camera_id,
            camera_latitude,
            camera_longitude,
            camera_altitude,
            image_quality,
            auth_key,
            storage_path,
            ext_storage_path,
            time_format,
            log_dir=None,
            log_stream=True,
            autonomous_mode=False,
            cam_address=None,
            username=None,
            pwd=None,
            rpi_cam=False,
            irradiance_sensor=False,
            sensor_port=None,
            sensor_address=None,
            sensor_baudrate=None,
            sensor_bytesize=None,
            sensor_parity=None,
            sensor_stopbits=None
    ):
        super().__init__(
            camera_latitude=camera_latitude,
            camera_longitude=camera_longitude,
            camera_altitude=camera_altitude,
            stream=log_stream,
            log_dir=log_dir
        )
        try:
            if not os.path.exists(os.path.join(_parent_dir_, 'annual_twilight_times.pkl')):
                self.collect_annual_twilight_times()

            if irradiance_sensor:
                self.light_sensor = IrrSensor()
                self.set_sensor(
                    port=sensor_port,
                    address=sensor_address,
                    baudrate=sensor_baudrate,
                    bytesize=sensor_bytesize,
                    parity=sensor_parity,
                    stopbits=sensor_stopbits
                )
            self.cam_id = camera_id
            self.image_quality = image_quality
            self.key = bytes(auth_key, 'ascii')
            self.server = server
            self.time_format = time_format
            if autonomous_mode:
                self.storage_path = ext_storage_path
            else:
                self.storage_path = storage_path
            if rpi_cam:
                self.cam = RPiCam()
            else:
                self.cam = GeoVisionCam(cam_address, username, pwd)
        except Exception as e:
            self.logger.exception(e)

    @staticmethod
    def _encrypt_data(key, message):
        """
        Encrypts the given data/message using SHA-256 key.

        Parameters
        ----------
        key : `bytes`
            provided secret key
        message : `str`
            message that is intended to be hashed

        Returns
        -------
        hashed data : `str`
            the encrypted data
        """
        return hmac.new(key, bytes(message, 'ascii'), digestmod=hashlib.sha256).hexdigest()

    @staticmethod
    def _send_post_request(url, data):
        """
        Sends a post request to a given server/url

        Parameters
        ----------
        url : `str`
            server's url
        data : `str`
            data to be sent

        Returns
        -------
        http response : `dict`
        """
        post_data = {
            'data': data
        }
        return requests.post(url, data=post_data)

    @staticmethod
    def _get_file_timestamp(file):
        """
        Gets the latest date that the file was modified.

        Parameters
        ----------
        file : `str`
            path to the file

        Returns
        -------
        modification date : `datetime`
            the date that the file was modified.
        """
        return datetime.fromtimestamp(os.path.getmtime(file))

    def _get_file_datetime_as_string(self, file, datetime_format):
        """
        Gets the file modification date in a given format as a string

        Parameters
        ----------
        file : `str`
            path to the file
        datetime_format : `str`
            date format in strftime

        Returns
        -------
        date : `str`
            modification date as a `str`
        """
        return self._get_file_timestamp(file).strftime(datetime_format)

    def _make_json_from_image(self, image, time_stamp=datetime.utcnow()):
        """
        Makes a json out of the encoded image and its metadata.

        Parameters
        ----------
        image : `str` or `numpy.array`
            path to the image or a numpy array of the image
        time_stamp : `datetime`
            the timestamp of the image (default is current time as `datetime.utcnow`)

        Returns
        -------
        json data : `str`
        """
        if isinstance(image, str):
            # if it's a file path, convert the stored image to a numpy array
            image = self.make_array_from_image(image)

        image = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), self.image_quality])[1]
        data = {
            'status': 'ok',
            'id': self.cam_id,
            'time': time_stamp,
            'coding': 'Base64',
            'data': base64.b64encode(image).decode('ascii')
        }
        return json.dumps(data)

    def _upload_to_server(self, image, time_stamp=datetime.utcnow()):
        """
        Uploads the image to the server.

        Parameters
        ----------
        image : `str` or `numpy.array`
            path to the image or a numpy array of the image
        time_stamp : `datetime`
            the timestamp of the image (default is current time as `datetime.utcnow`)
        """
        json_data = self._make_json_from_image(image, time_stamp)
        signature = self._encrypt_data(self.key, json_data)
        try:
            response = self._send_post_request('{}{}'.format(self.server, signature), json_data)
            json_response = json.loads(response.text)

            if json_response['status'] != 'ok':
                raise ConnectionError(json_response['message'])

        except Exception as e:
            self.logger.exception(e)
            raise ConnectionError

    def upload_as_bson(self, file, server):
        """
        Uploads file as binary json.

        Parameters
        ----------
        file : `str`
            path to the file
        server : `str`
            server address

        Returns
        -------
        http response : `str`
        """
        data = {
            "status": "ok",
            "id": self.cam_id,
            "time": self._get_file_datetime_as_string(file, self.time_format),
            "coding": "none"
        }

        json_data = json.dumps(data)
        signature = self._encrypt_data(self.key, json_data)
        url = '{}{}'.format(server, signature)

        if isinstance(file, str) or isinstance(file, bytes):
            files = [('image', file), ('json', json_data)]
        else:
            files = [('image', str(file)), ('json', json_data)]

        response = requests.post(url=url, files=files)

        try:
            json_response = json.loads(response.text)
        except Exception as e:
            raise Exception(e)

        if json_response['status'] != 'ok':
            raise Exception(json_response['message'])

        return json_response

    @timeout(60, timeout_exception=TimeoutError, use_signals=False)
    def upload_thumbnail(self, thumbnail, time_stamp=datetime.utcnow()):
        """
        Uploads a thumbnail to the server with a timeout limit.

        Parameters
        ----------
        thumbnail : `str` or `numpy.array`
            path to the thumbnail or a numpy array of the thumbnail
        time_stamp : `datetime`
            the timestamp of the image (default is current time as `datetime.utcnow`)
        """
        self._upload_to_server(thumbnail, time_stamp=time_stamp)

    @timeout(6, timeout_exception=TimeoutError, use_signals=False)
    def upload_image(self, image, time_stamp=datetime.utcnow()):
        """
        Uploads the image to the server with a timeout limit.

        Parameters
        ----------
        image : `str` or `numpy.array`
            path to the image or a numpy array of the image
        time_stamp : `datetime`
            the timestamp of the image (default is current time as `datetime.utcnow`)
        """
        self._upload_to_server(image, time_stamp=time_stamp)

    @timeout(60, timeout_exception=TimeoutError, use_signals=False)
    def upload_logfile(self, log_file, server):
        """
        Uploads the logfile to the server with a timeout limit.

        Parameters
        ----------
        log_file : `str`
            path to the logfile
        server : `str`
            server address
        """
        self.logger.debug('Start upload log to server')
        self.upload_as_bson(log_file, server=server)

    def get_available_free_space(self):
        """
        Get the available space in the `storage_path`

        Returns
        -------
        available space : `float`
            available space in GB
        """
        free_space = shutil.disk_usage(self.storage_path)[2]
        return round(free_space / 2**30, 1)

    def compress_storage(self):
        """
        Compresses all the jpeg images in `storage_path` and saves them in the same directory.
        """
        zip_archive = '{}.zip'.format(self.stamp_curr_time(self.time_format))
        try:
            with zipfile.ZipFile(os.path.join(self.storage_path, zip_archive), 'w') as zf:
                self.logger.debug('Compressing the images in the storage...')
                for file in glob.iglob(os.path.join(self.storage_path, '*.jpg')):
                    zf.write(filename=file)
        except Exception as e:
            self.logger.exception(e)

    # todo check function
    def save_irradiance_csv(self, time, irradiance, ext_temperature, cell_temperature):
        """
        Writes the data received from the irradiance sensor onto the disk.

        Parameters
        ----------
        time
        irradiance
        ext_temperature
        cell_temperature
        """
        try:
            with open(os.path.join(path, self.config.MODBUS_csv_name), 'a', newline='') as handle:
                csv_file = csv.writer(handle, delimiter=';', quotechar='\'', quoting=csv.QUOTE_MINIMAL)

                if self.config.MODBUS_log_temperature:
                    csv_file.writerow([time, irradiance, ext_temperature, cell_temperature])
                else:
                    csv_file.writerow([time, irradiance])

        except Exception as e:
            self.logger.error('csv save to local storage error : ' + str(e))
        else:
            self.logger.debug('csv row saved in' + path + '/' + self.config.MODBUS_csv_name)
            self.logger.info('irradiance saved ' + str(irradiance))

