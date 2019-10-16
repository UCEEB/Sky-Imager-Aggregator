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
        os.system('sudo /usr/sbin/ntpd {}'.format(ntp_server))

    def find_sunrise_and_sunset_time(self, date=None):
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
    def get_twilight_times_by_day(day_no):
        with open(os.path.join(_parent_dir_, 'annual_twilight_times.pkl'), 'rb') as handle:
            col = pickle.load(handle)
        return col[day_no]

    @staticmethod
    def stamp_curr_time(time_format):
        return dt.datetime.utcnow().strftime(time_format)


class Controller(TimeManager, ImageProcessor):
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
            self.key = auth_key
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
        return hmac.new(key, bytes(message, 'ascii'), digestmod=hashlib.sha256).hexdigest()

    @staticmethod
    def _send_post_request(url, data):
        post_data = {
            'data': data
        }
        return requests.post(url, data=post_data)

    @staticmethod
    def _get_file_timestamp(file):
        return datetime.fromtimestamp(os.path.getmtime(file))

    def _get_file_datetime_as_string(self, file, datetime_format):
        return self._get_file_timestamp(file).strftime(datetime_format)

    @staticmethod
    def _list_files(path):
        return glob.iglob(os.path.join(path, '*'))

    def upload_as_json(self, image, time_stamp=datetime.utcnow()):
        if isinstance(image, str):
            image = self.make_array_from_image(image)

        image = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), self.image_quality])[1]

        data = {
            'status': 'ok',
            'id': self.cam_id,
            'time': time_stamp,
            'coding': 'Base64',
            'data': base64.b64encode(image).decode('ascii')
        }

        json_data = json.dumps(data)
        signature = self._encrypt_data(self.key, json_data)
        response = self._send_post_request('{}{}'.format(self.server, signature), json_data)
        try:
            json_response = json.loads(response.text)
        except Exception as e:
            raise ConnectionRefusedError(e)

        if json_response['status'] != 'ok':
            raise ConnectionError(json_response['message'])

    def upload_as_bson(self, file, server):
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
    def upload_thumbnail(self, image, time_stamp=datetime.utcnow()):
        self.upload_as_json(image, time_stamp=time_stamp)

    @timeout(6, timeout_exception=TimeoutError, use_signals=False)
    def upload_image(self, image, time_stamp=datetime.utcnow()):
        self.upload_as_json(image, time_stamp=time_stamp)

    @timeout(60, timeout_exception=TimeoutError, use_signals=False)
    def upload_logfile(self, log_file, server):
        self.logger.debug('Start upload log to server')
        self.upload_as_bson(log_file, server=server)

    def isStorageEmpty(self):
        if not self._list_files(self.storage_path):
            return True
        else:
            return False

    def get_available_free_space(self):
        free_space = shutil.disk_usage(self.storage_path)[2]
        return round(free_space / 2**30, 1)

    def compress_storage(self):
        zip_archive = '{}.zip'.format(self.stamp_curr_time(self.time_format))
        with zipfile.ZipFile(zip_archive, 'w') as zf:
            for file in self._list_files(self.storage_path):
                zf.write(filename=file)

    # todo check function
    def save_irradiance_csv(self, time, irradiance, ext_temperature, cell_temperature):
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

