#!/usr/bin/python3
import base64
import csv
import hashlib
import hmac
import json
import requests
import os
import socket
import datetime as dt

import cv2
import numpy as np
from Configuration import Configuration

__author__ = 'Jan Havrlant'
__copyright__ = 'MIT'
__credits__ = ['Jan Havrlant', 'Barbara Stefanovska', 'Kamil Sagalara', 'Azim Mazinani']
__license__ = 'Copyright 2018, UCEEB (Czech Technical University in Prague)'
__version__ = '3.0'
__maintainer__ = 'Azim Mazinani'
__email__ = 'azim.mazinani@cvut.cz'
__status__ = 'Development'
__package__ = ''
__doc__ = 'This file contains SIAUtil class which consists of different helper methods for running the raspberry pi'


class SIAUtil:
    def __init__(self, logger):
        super().__init__()
        self.config = Configuration('config.ini', logger)
        self.logger = logger

    @staticmethod
    def load_image(image):
        return cv2.imread(image)

    def apply_mask(self, image):
        return np.multiply(self.load_image(self.config.mask_path) / 255, image)

    @staticmethod
    def apply_custom_processing(image):
        return image

    @staticmethod
    def encrypt_message(message, key):
        return hmac.new(key, bytes(message, 'ascii'), digestmod=hashlib.sha256).hexdigest()

    @staticmethod
    def send_post_request(url, data):
        post_data = {
            'data': data
        }
        return requests.post(url, data=post_data)

    def upload_json(self, image, file_time):
        sky_image = base64.b64encode(image).decode('ascii')
        date_string = file_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        id = self.config.id
        key = self.config.key
        server = self.config.server

        data = {
            'status': 'ok',
            'id': id,
            'time': date_string,
            'coding': 'Base64',
            'data': sky_image
        }

        json_data = json.dumps(data)
        signature = self.encrypt_message(json_data, key)
        url = server + signature
        response = self.send_post_request(url, json_data)

        try:
            json_response = json.loads(response.text)
        except Exception as e:
            raise Exception(e)

        if json_response['status'] != 'ok':
            raise Exception(json_response['message'])

        return json_response

    def get_path_to_storage(self):
        path = self.config.path_storage
        if self.config.autonomous_mode:
            if os.access(self.config.GSM_path_storage_usb1, os.W_OK):
                path = self.config.GSM_path_storage_usb1
            elif os.access(self.config.GSM_path_storage_usb2, os.W_OK):
                path = self.config.GSM_path_storage_usb2
        return path

    def save_to_storage(self, img, name, image_time):
        path = os.path.join(self.get_path_to_storage(), image_time.strftime("%y-%m-%d"))
        if not os.path.exists(path):
            os.makedirs(path)

        try:
            img.tofile(os.path.join(path, name))
        except Exception as e:
            self.logger.error('Saving to local storage error : ' + str(e))
            pass
        else:
            self.logger.info('image ' + path + '/' + name + ' saved to storage')
            pass


    def get_free_space_storage(self):
        path = self.get_path_to_storage()
        info = os.statvfs(path)
        free_space = info.f_bsize * info.f_bfree / 1048576
        return '{}.0f MB'.format(free_space)

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

    def test_internet_connection(self, host="8.8.8.8", port=53, timeout=3):
        """
        Host: 8.8.8.8 (google-public-dns-a.google.com)
        OpenPort: 53/tcp
        Service: domain (DNS/TCP)
        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception as e:
            self.logger.error('No internet connection: ' + str(e))
            return False
