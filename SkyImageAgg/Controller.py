import os
import time
import base64
import json
import csv

import requests

from SkyImageAgg.GSM import Messenger, GPRS
from SkyImageAgg.Utils import Utils


class Controller(Utils, Messenger, GPRS):
    def __init__(
            self,
            server,
            camera_id,
            auth_key,
            storage_path,
            ext_storage_path,
            time_format,
            autonomous_mode=False
    ):
        super().__init__()
        self.cam_id = camera_id
        self.key = auth_key
        self.server = server
        self.time_format = time_format
        if autonomous_mode:
            self.storage_path = ext_storage_path
        else:
            self.storage_path = storage_path

    def sync_time(self):
        if not self.enable_GPRS():
            return False
        counter = 0
        while True:
            self.logger.debug('Sync time')
            if os.system('sudo ntpdate -u tik.cesnet.cz') == 0:
                self.logger.info('Sync time OK')
                return True
            else:
                counter += 1
                time.sleep(1)
            if counter > 10:
                self.logger.error('Sync time error')
                return False

    def upload_file_as_json(self, file, convert_to_array=True):
        if convert_to_array:
            file = self.make_array_from_image(file)

        data = {
            'status': 'ok',
            'id': self.cam_id,
            'time': self.get_file_datetime_as_string(file, self.time_format),
            'coding': 'Base64',
            'data': base64.b64encode(file).decode('ascii')
        }

        json_data = json.dumps(data)
        signature = self.encrypt_data(self.key, json_data)
        url = '{}{}'.format(self.server, signature)
        response = self.send_post_request(url, json_data)

        try:
            json_response = json.loads(response.text)
        except Exception as e:
            raise Exception(e)

        if json_response['status'] != 'ok':
            raise Exception(json_response['message'])

        return json_response

    def upload_file_as_bson(self, file):
        data = {
            "status": "ok",
            "id": self.cam_id,
            "time": self.get_file_datetime_as_string(file, self.time_format),
            "coding": "none"
        }

        json_data = json.dumps(data)
        signature = self.encrypt_data(self.key, json_data)
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
        self.logger.debug('Uploading log to the server')
        counter = 0
        while True:
            counter += 1
            self.enable_GPRS()
            try:
                self.upload_file_as_bson(file)
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
                self.upload_file_as_bson(log_file)
                self.logger.info('upload log to server OK')

                return
            except Exception as e:
                self.logger.error('upload log to server error : ' + str(e))

            if counter > 5:
                self.logger.error('error upload log to server')
                break

        self.logger.debug('end upload log to server')

    def isStorageEmpty(self):
        if not self.list_files(self.storage_path):
            return True
        else:
            return False

    # SHOULD BE DONE IN MAIN CLASS
    # todo check function
    def save_to_storage(self, img, name, image_time):
        path = os.path.join(self.get_path_to_storage(), image_time.strftime("%y-%m-%d"))
        if not os.path.exists(path):
            os.makedirs(path)

        if self.config.autonomous_mode:
            try:
                img.tofile(os.path.join(path, name))
            except Exception as e:
                self.logger.error('Saving to local storage error : ' + str(e))
                pass
            else:
                self.logger.info('image ' + path + '/' + name + ' saved to storage')
                pass
        try:
            img.tofile(os.path.join(self.config.path_storage, name))
        except Exception as e:
            self.logger.error('save to local storage error : ' + str(e))
            pass
        else:
            self.logger.info('image ' + self.config.path_storage + '/' + name + ' saved to storage')
            pass

    # todo check function
    def save_irradiance_csv(self, time, irradiance, ext_temperature, cell_temperature):
        path = self.get_path_to_storage()
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
