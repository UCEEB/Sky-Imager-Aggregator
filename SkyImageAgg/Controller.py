import os
import time
import datetime as dt
import base64
import hashlib
import hmac
import json

import requests

from SkyImageAgg.GSM import Messenger, GPRS


class Controller(Messenger, GPRS):
    def __init__(self, server, camera_id, auth_key):
        super().__init__()
        self.cam_id = camera_id
        self.key = auth_key
        self.server = server

    def encrypt_data(self, message):
        return hmac.new(self.key, bytes(message, 'ascii'), digestmod=hashlib.sha256).hexdigest()

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

    @staticmethod
    def send_post_request(url, data):
        post_data = {
            'data': data
        }
        return requests.post(url, data=post_data)

    def upload_file_as_json(self, file, date_string):
        data = {
            'status': 'ok',
            'id': self.cam_id,
            'time': date_string.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            'coding': 'Base64',
            'data': base64.b64encode(file).decode('ascii')
        }

        json_data = json.dumps(data)
        signature = self.encrypt_data(json_data)
        url = '{}{}'.format(self.server, signature)
        response = self.send_post_request(url, json_data)

        try:
            json_response = json.loads(response.text)
        except Exception as e:
            raise Exception(e)

        if json_response['status'] != 'ok':
            raise Exception(json_response['message'])

        return json_response

    def upload_file_as_bson(self, image, date_string):
        data = {
            "status": "ok",
            "id": self.cam_id,
            "time": date_string.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "coding": "none"
        }

        json_data = json.dumps(data)
        signature = self.encrypt_data(json_data)

        if isinstance(image, str) or isinstance(image, bytes):
            files = [('image', image), ('json', json_data)]
        else:
            files = [('image', str(image)), ('json', json_data)]

        response = requests.post(self.server + signature, files=files)

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
                self.upload_file_as_bson(file, dt.datetime.utcnow())
                self.logger.info('Upload thumbnail to server OK')
                self.disable_ppp()
                return
            except Exception as e:
                self.logger.error('Upload thumbnail to server error: ' + str(e))
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
                self.upload_file_as_bson(log_file, dt.datetime.utcnow())
                self.logger.info('upload log to server OK')

                return
            except Exception as e:
                self.logger.error('upload log to server error : ' + str(e))

            if counter > 5:
                self.logger.error('error upload log to server')
                break

        self.logger.debug('end upload log to server')
