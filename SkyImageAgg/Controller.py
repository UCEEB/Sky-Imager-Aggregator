import base64
import datetime as dt
import glob
import hashlib
import hmac
import json
import os
import pickle
import shutil
import zipfile
from datetime import datetime

import numpy as np
import requests
from astral import Astral
from astral import Location
from timeout_decorator import timeout


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

class TwilightCalc:
    """
    A class responsible to manage the twilight times with respect to the geolocation.

    Attributes
    ----------
    latitude : `float`
        location latitude
    longitude : `float`
        location longitude
    altitude : `float`
        location altitude

    Parameters
    ----------
    latitude : `float`
        location latitude
    longitude : `float`
        location longitude
    altitude : `float`
        location altitude
    """

    def __init__(
            self,
            latitude,
            longitude,
            altitude,
            twilight_coll_in_memory=True,
            twilight_coll_file=None
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.twilight_coll = twilight_coll_file

        if twilight_coll_in_memory and twilight_coll_file:
            raise ValueError('store_in_memory and twilight_coll_file parameters cannot be both False or True!')

        if twilight_coll_in_memory:
            # collect the times and store it as an attribute
            self.twilight_coll = self.collect_annual_twilight_times()

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
        coll = {  # storing location coordinates as -1 as its key in the collection
            -1: (self.latitude,
                 self.longitude)
        }

        dates = np.arange(
            # 2020 is chosen as it's a leap year with 366 days
            dt.datetime(2020, 1, 1),
            dt.datetime(2021, 1, 1),
            dt.timedelta(days=1)
        ).astype(dt.datetime).tolist()

        for date in dates:
            coll[date.timetuple().tm_yday] = self.find_sunrise_and_sunset_time(date=date)

        if isinstance(self.twilight_coll, str):
            with open(self.twilight_coll, 'wb') as f:
                pickle.dump(coll, f, protocol=pickle.HIGHEST_PROTOCOL)

        return coll

    def get_twilight_times_by_day(self, day_of_year):
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
        if isinstance(self.twilight_coll, str):
            if not os.path.exists(self.twilight_coll):
                self.collect_annual_twilight_times()

            with open(self.twilight_coll, 'rb') as handle:
                coll = pickle.load(handle)

            return coll[day_of_year]
        else:

            return self.twilight_coll[day_of_year]

    def has_location_changed(self):
        """
        Checks if the given location is different from the stored one in the existing twilight collection.

        Returns
        -------
        True if the location has changed, false otherwise : `boolean`
        """
        try:
            if self.get_twilight_times_by_day(-1) == (self.latitude, self.longitude):
                return False
        except Exception:
            return True


class Controller(TwilightCalc):
    """
    A class responsible for performing IO and network operations. It inherits properties from `TimeManager` and
    `ImageProcessor` to pass their methods and attributes to its children such as `SkyScanner`.

    Attributes
    ----------
    client_id : `int`
    jpeg_quality : `int`
    key : `str`
    server : `str`
    time_format : `str`
    storage_path : `str`
    cam : `Collector.GeoVisionCam` or `Collector.RpiCam`

    Parameters
    ----------
    server : `str`
        the server that receives the photos taken from sky to perform further processing.
    client_id : `int`
        the camera ID assigned by the vendor.
    latitude : `float`
        latitude of the camera.
    longitude : `float`
        longitude of the camera.
    altitude : `float`
        the altitude of the camera.
    jpeg_quality : `int`
        the desired jpeg quality for the taken image.
    mask_path : `str`
        path to mask image.
    auth_key : `str`
        the SHA-256 key provided by the vendor.
    storage_path : `str`
        the path to the storage directory.
    temp_storage_path : `str`
        the path to the temporary storage directory.
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
            client_id,
            *args,
            auth_key,
            storage_path,
            time_format,
            temp_storage_path,
            logger=None,
            **kwargs
    ):
        super(Controller, self).__init__(*args, **kwargs)

        if not logger:
            # Null logger if no logger is defined as parameter
            self._logger = logging.getLogger(__name__).addHandler(NullHandler())
        else:
            self._logger = logger

        self.client_id = client_id
        self.key = bytes(auth_key, 'ascii')
        self.server = server
        self.time_format = time_format
        self.storage_path = storage_path
        self.temp_storage_path = temp_storage_path

    def _make_json_from_image(self, image, time_stamp=datetime.utcnow()):
        """
        Makes a json out of the encoded image and its metadata.

        Parameters
        ----------
        image : `str` or `numpy.array`
            path to the image or a numpy array of the image
        time_stamp : `datetime.time`
            the timestamp of the image (default is current time as `datetime.utcnow`)

        Returns
        -------
        json data : `str`
        """
        if isinstance(image, str):
            # if it's a file path, convert the stored image to a numpy array
            image = self.make_array_from_image(image)

        image = self.encode_image(image_arr=image)
        data = {
            'status': 'ok',
            'id': self.client_id,
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
        signature = _encrypt_data(self.key, json_data)
        try:
            response = _send_post_request('{}{}'.format(self.server, signature), json_data)
            json_response = json.loads(response.text)

            if json_response['status'] != 'ok':
                raise ConnectionError(json_response['message'])

        except Exception as e:
            self._logger.exception(e)
            raise ConnectionError

    @timeout(60, timeout_exception=TimeoutError, use_signals=False)
    def upload_thumbnail(self, thumbnail, time_stamp=datetime.utcnow()):
        """
        Uploads a thumbnail to the server with a timeout limit.

        Parameters
        ----------
        thumbnail : `str` or `numpy.array`
            path to the thumbnail or a numpy array of the thumbnail
        time_stamp : `datetime.time`
            the timestamp of the image (default is current time as `datetime.utcnow`)
        """
        self._upload_to_server(thumbnail, time_stamp=time_stamp)

    @timeout(15, timeout_exception=TimeoutError, use_signals=False)
    def upload_image(self, image, time_stamp=datetime.utcnow()):
        """
        Uploads the image to the server with a timeout limit.

        Parameters
        ----------
        image : `str` or `numpy.array`
            path to the image or a numpy array of the image
        time_stamp : `datetime.time`
            the timestamp of the image (default is current time as `datetime.utcnow`)
        """
        self._upload_to_server(image, time_stamp=time_stamp)

    def get_available_free_space(self):
        """
        Get the available space in the `storage_path`

        Returns
        -------
        available space : `float`
            available space in GB
        """
        free_space = shutil.disk_usage(self.storage_path)[2]
        return round(free_space / 2 ** 30, 1)

    def compress_storage(self):
        """
        Compresses all the jpeg images in `storage_path` and saves them in the same directory.
        """
        curr_time = dt.datetime.utcnow().strftime(self.time_format)
        zip_archive = '{}.zip'.format(curr_time)
        try:
            with zipfile.ZipFile(os.path.join(self.storage_path, zip_archive), 'w') as zf:
                self._logger.debug('Compressing the images in the storage...')
                for file in glob.iglob(os.path.join(self.storage_path, '*.jpg')):
                    zf.write(filename=file)
        except Exception as e:
            self._logger.exception(e)
