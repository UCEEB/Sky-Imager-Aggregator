import os
import base64
import json
import hmac
import csv
import hashlib
import glob
from datetime import datetime

import requests
import cv2
from timeout_decorator import timeout

from SkyImageAgg.Processor import ImageProcessor
from SkyImageAgg.Collector import GeoVisionCam, RPiCam
from SkyImageAgg.Logger import Logger


class TimeManager:
    def __init__(self):
        self.latitude = None
        self.longitude = None
        self.altitude = None

    def set_location(self, camera_latitude, camera_longitude, camera_altitude):
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

    def collect_annual_twilight_times(self, dir_path):
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

        for date in dates:
            collection[date.timetuple().tm_yday] = self.find_sunrise_and_sunset_time(date=date)

        with open(os.path.join(dir_path, 'annual_twilight_times.pkl'), 'wb') as file:
            pickle.dump(collection, file, protocol=pickle.HIGHEST_PROTOCOL)

        return collection

    @staticmethod
    def get_today_twilight_times(day_no):
        with open(_twilight_coll_, 'rb') as handle:
            col = pickle.load(handle)
        return col[day_no]

    @staticmethod
    def stamp_curr_time(time_format):
        return dt.datetime.utcnow().strftime(time_format)


class Controller(ImageProcessor, RPiCam, GeoVisionCam, Logger, TimeManager):
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
            autonomous_mode=False,
            cam_address=None,
            username=None,
            pwd=None,
            log_dir=None,
            log_stream=True,
            rpi_cam=False
    ):
        super().__init__()
        self.set_logger(log_dir=log_dir, stream=log_stream)
        self.set_location(camera_latitude, camera_longitude, camera_altitude)
        try:
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

    @timeout(7, timeout_exception=TimeoutError, use_signals=False)
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

        return True

    @timeout(7, timeout_exception=TimeoutError)
    def upload_as_bson(self, file):
        data = {
            "status": "ok",
            "id": self.cam_id,
            "time": self._get_file_datetime_as_string(file, self.time_format),
            "coding": "none"
        }

        json_data = json.dumps(data)
        signature = self._encrypt_data(self.key, json_data)
        url = '{}{}'.format(self.server, signature)

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

    def send_thumbnail_file(self, file):
        counter = 0
        while True:
            counter += 1
            self.enable_GPRS()
            try:
                self.upload_as_bson(file)
                self.logger.info('Upload thumbnail to server OK')
                self.disable_ppp()
                return
            except Exception as e:
                self.logger.error('Upload thumbnail to server error: {}'.format(e))
            if counter > 5:
                self.logger.error('Upload thumbnail to server error: too many attempts')
                break
        self.logger.debug('Upload thumbnail to server end')
        self.disable_ppp()

    def upload_logfile(self, log_file):
        self.logger.debug('Start upload log to server')
        counter = 0
        while True:
            counter += 1
            self.enable_GPRS()
            try:
                self.upload_as_bson(log_file)
                self.logger.info('upload log to server OK')

                return
            except Exception as e:
                self.logger.error('upload log to server error : ' + str(e))

            if counter > 5:
                self.logger.error('error upload log to server')
                break

        self.logger.debug('end upload log to server')

    def isStorageEmpty(self):
        if not self._list_files(self.storage_path):
            return True
        else:
            return False

    def get_available_free_space(self):
        info = os.statvfs(self.storage_path)
        return info.f_bsize * info.f_bfree / 1048576

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
