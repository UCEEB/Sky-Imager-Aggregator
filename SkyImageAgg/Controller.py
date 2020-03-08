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

from SkyImageAgg.Preprocessor import SkyImage
from SkyImageAgg.Collectors.GeoVisionCam import GeoVisionCam as IPCamera
from SkyImageAgg.Collectors.RpiCam import RpiCam
from SkyImageAgg import Utils


def encrypt_data(key, message):
    """
    Encrypt the given data/message using SHA-256 key.

    Parameters
    ----------
    key : bytes
        secret key.
    message : str
        message that is intended to be hashed.

    Returns
    -------
    str
        the encrypted data
    """
    return hmac.new(key, bytes(message, 'ascii'), digestmod=hashlib.sha256).hexdigest()


def send_post_request(url, data):
    """
    Send a post request to a given server/url.

    Parameters
    ----------
    url : str
        server's url.
    data : str
        data to be sent.

    Returns
    -------
    requests.Response
        http response.
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
    latitude : float
        location latitude.
    longitude : float
        location longitude.
    altitude : float
        location altitude.
    ntp_server : str
        the ntp server that you want to sync time with.
    twilight_coll : str or dict of {int : (datetime.time, datetime.time)}
        collection of times, if file is selected it's the path to the file, else it's a dictionary.
    """

    def __init__(
            self,
            latitude,
            longitude,
            altitude,
            ntp_server,
            in_memory=True,
            file=None
    ):
        """
        Construct a twilight calculator object.

        Parameters
        ----------
        latitude : float
            location latitude.
        longitude : float
            location longitude.
        altitude : float
            location altitude.
        ntp_server : str
            the ntp server that you want to sync time with.
        in_memory : bool, default True
            if you want to keep the calculated times in memory instead of writing them on disk.
        file : str, default None
            path to the pickle file that you to save the times in.
        """
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.ntp_server = ntp_server
        self.twilight_coll = file
        self.sync_time()

        if in_memory and file:
            raise ValueError('in_memory and file parameters cannot be both False or True!')

        if in_memory:
            # collect the times and store it as an attribute
            self.twilight_coll = self.collect_annual_twilight_times()

    def find_sunrise_and_sunset_time(self, date=None):
        """
        Find the sunrise and sunset time of a given date.

        Parameters
        ----------
        date : datetime.datetime, default None
            the date (default is None, which will take the current date).

        Returns
        -------
        tuple of (datetime.time, datetime.time)
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
        Collect the annual sunrise/sunset times with respect to the location of the camera.

        Returns
        -------
        dict of {int : (datetime.time, datetime.time)}
            a dictionary with day order as its keys and tuple of twilight times as its values.
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
        Get the sunrise/sunset times collected previously given the day of the year.

        Parameters
        ----------
        day_of_year : int
            The day of year (DOY) is the sequential day number starting with day 1 on January 1st.

        Returns
        -------
        tuple of (datetime.time, datetime.time)
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
        Check if the given location is different from the stored one in the existing twilight collection.

        Returns
        -------
        bool
            True if the location has changed, false otherwise.
        """
        try:
            if self.get_twilight_times_by_day(-1) == (self.latitude, self.longitude):
                return False
        except Exception:
            return True

    def sync_time(self):
        """
        Synchronize device time with UTC.

        Notes
        -----
            You need to install ntpd package on your device.
            see:
            https://raspberrytips.com/time-sync-raspberry-pi/
        """
        os.system('sudo /usr/sbin/ntpd {}'.format(self.ntp_server))


class Controller(SkyImage):
    """
    A class responsible for performing IO and network operations.

    It inherits properties from `SkyImage` to manipulate the images.

    Attributes
    ----------
    server : str
        the server that receives the photos taken from sky to perform further processing.
    client_id : int
        the camera ID assigned by the vendor.
    auth_key : bytes
        the SHA-256 key provided by the vendor.
    storage_path : str
        the path to the storage directory.
    time_format : str
        the time format.
    cam_username : str
        username for the IP camera.
    cam_pwd : str
        password for the IP camera.
    cam_address : str or None, default 'rpi'
        url to the IP camera login page, if default, RPi camera used if attached.
    """

    def __init__(
            self,
            server,
            client_id,
            auth_key,
            storage_path,
            time_format,
            cam_username,
            cam_pwd,
            cam_address='rpi'
    ):
        """
        Construct a controller object.

        Parameters
        ----------
        server : str
            the server that receives the photos taken from sky to perform further processing.
        client_id : int
            the camera ID assigned by the vendor.
        auth_key : str
            the SHA-256 key provided by the vendor.
        storage_path : str
            the path to the storage directory.
        time_format : str
            the time format.
        cam_username : str or None
            username for the IP camera.
        cam_pwd : str or None
            password for the IP camera.
        cam_address : str or None, default 'rpi'
            url to the IP camera login page, if default, RPi camera used if attached.
        """
        if cam_address == 'rpi':
            cam_obj = RpiCam()
        elif not cam_address:
            cam_obj = None
        else:
            cam_obj = IPCamera(cam_address)
            cam_obj.login(cam_username, cam_pwd)

        super().__init__(camera=cam_obj)

        self.client_id = client_id
        self.key = bytes(auth_key, 'ascii')
        self.server = server
        self.time_format = time_format
        self.storage_path = storage_path

        # create the main storage if doesn't exist
        if not os.path.exists(self.storage_path):
            os.mkdir(self.storage_path)

    def prepare_as_post_req(self, time_stamp=datetime.utcnow()):
        """
        Make a json out of the encoded image and its metadata.

        Parameters
        ----------
        time_stamp : str or datetime.datetime, default datetime.utcnow()
            the timestamp of the image as string or datetime object

        Returns
        -------
        str
            JSON data.
        """
        if isinstance(time_stamp, datetime):
            time_stamp = time_stamp.strftime(self.time_format)

        encoded_image = self.encode_to_jpeg()

        data = {
            'status': 'ok',
            'id': self.client_id,
            'time': time_stamp,
            'coding': 'Base64',
            'data': base64.b64encode(encoded_image).decode('ascii')
        }
        return json.dumps(data)

    def upload(self, time_stamp=datetime.utcnow()):
        """
        Upload the image to the server.

        Parameters
        ----------
        time_stamp : datetime.datetime, default datetime.utcnow()
            the timestamp of the image.
        """
        json_data = self.prepare_as_post_req(time_stamp)
        signature = encrypt_data(self.key, json_data)
        try:
            response = send_post_request(f'{self.server}{signature}', json_data)
            json.loads(response.text)
        except Exception as e:
            raise ConnectionError(e)

    @timeout(20, timeout_exception=TimeoutError, use_signals=False)
    def upload_thumbnail(self, time_stamp=datetime.utcnow()):
        """
        Upload thumbnail to the server with a timeout limit.

        Parameters
        ----------
        time_stamp : datetime.datetime, default datetime.utcnow()
            the timestamp of the image.
        """
        self.upload(self.make_thumbnail(), time_stamp=time_stamp)

    @timeout(15, timeout_exception=TimeoutError, use_signals=False)
    def upload_with_timeout(self, time_stamp=datetime.utcnow()):
        """
        Upload the image to the server with a given timeout limit.

        Parameters
        ----------
        time_stamp : datetime.datetime, default datetime.utcnow()
            the timestamp of the image.
        """
        self.upload(time_stamp=time_stamp)

    @Utils.retry_on_failure(attempts=2)
    def retry_uploading_image(self, time_stamp=datetime.utcnow()):
        """
        Retry to upload a given image for a given number of attempts passed through the decorator.

        Parameters
        ----------
        time_stamp : datetime.datetime, default datetime.utcnow()
            the timestamp of the image.
        """
        self.upload_with_timeout(time_stamp=time_stamp)

    def get_available_free_space(self):
        """
        Get the available space in the `storage_path`

        Returns
        -------
        float
            available space in GB.
        """
        free_space = shutil.disk_usage(self.storage_path)[2]
        return round(free_space / 2 ** 30, 1)

    def compress_storage(self):
        """
        Compress all the jpeg images in `storage_path` and saves them in the same directory.
        """
        curr_time = dt.datetime.utcnow().strftime(self.time_format)
        zip_archive = '{}.zip'.format(curr_time)

        with zipfile.ZipFile(os.path.join(self.storage_path, zip_archive), 'w') as zf:
            for file in glob.iglob(os.path.join(self.storage_path, '*.jpg')):
                zf.write(filename=file)
