import os
import re
import time
import hashlib
from abc import ABC, abstractmethod

import requests
import cv2
import minimalmodbus
import numpy as np
from picamera import PiCamera
from bs4 import BeautifulSoup


class Camera(ABC):
    @abstractmethod
    def cap_pic(self, output):
        pass

    @abstractmethod
    def cap_video(self, output):
        pass


class RPiCam(Camera):
    def __init__(self):
        self.cam = PiCamera()

    def start_preview(self):
        self.cam.start_preview()

    def stop_preview(self):
        self.cam.stop_preview()

    # todo check
    def cap_pic(self, output):
        self.cam.capture(output)

    def cap_video(self, output):
        pass


class GeoVisionCam(Camera):
    def __init__(self, cam_address, username, pwd):
        self.address = cam_address
        self.username = username
        self.pwd = pwd
        self.user_token = None
        self.pass_token = None
        self.desc_token = None
        self.login()

    @staticmethod
    def _gen_md5(string):
        return hashlib.md5(string.encode('utf-8')).hexdigest()

    def _get_salt_values(self):
        # get html and JS code as text
        page = requests.get('{}/ssi.cgi/Login.htm'.format(self.address))
        html_content = BeautifulSoup(page.content, "html.parser").text
        # parse the salt values (cc1 and cc2)
        salt = re.search(r'cc1=\"(.{4})\".*cc2=\"(.{4})\"', html_content)
        return salt.groups()

    def _get_hashed_credentials(self):
        cc1, cc2 = self._get_salt_values()
        # hash mechanism/formula based on the JS code of camera interface
        umd5 = '{}{}{}'.format(cc1, self.username.lower(), cc2)
        pmd5 = '{}{}{}'.format(cc2, self.pwd.lower(), cc1)
        return self._gen_md5(umd5).upper(), self._gen_md5(pmd5).upper()

    def login(self):
        umd5, pmd5 = self._get_hashed_credentials()
        data = {
            'grp': -1,
            'username': '',
            'password': '',
            'Apply': 'Apply',
            'umd5': umd5,
            'pmd5': pmd5,
            'browser': 1,
            'is_check_OCX_OK': 0
        }
        headers = {
            'User-Agent': 'Mozilla'
        }
        c = requests.post('{}/LoginPC.cgi'.format(self.address), data=data, headers=headers)

        self.user_token, self.pass_token, self.desc_token = re.search(
            r'gUserName\s=\s\"(.*)\";\n.*\s\"(.*)\";\n.*\"(.*)\"',
            c.text).groups()

    # TODO "Exception management"
    def cap_pic(self, output, return_arr=True):
        if self.user_token and self.pass_token and self.desc_token:
            data = {
                'username': self.user_token,
                'password': self.pass_token,
                'data_type': 0,
                'attachment': 1,
                'channel': 1,
                'secret': 1,
                'key': self.desc_token
            }
            r = requests.post('{}/PictureCatch.cgi'.format(self.address), data=data, stream=True)

            if return_arr:
                return cv2.imdecode(np.frombuffer(r.content, np.uint8), -1)

            with open(output, 'wb') as f:
                for chunk in r.iter_content():
                    f.write(chunk)

    def cap_video(self, output):
        raise NotImplementedError


class IrrSensor:
    def __init__(self, port, address, baudrate, bytesize, parity, stopbits):
        self.sensor = minimalmodbus.Instrument(port, address)
        self.sensor.serial.baudrate = baudrate
        self.sensor.serial.bytesize = bytesize
        self.sensor.serial.parity = parity
        self.sensor.serial.stopbits = stopbits
        self.sensor.serial.rtscts = False
        self.sensor.serial.dsrdtr = True
        self.sensor.serial.timeout = 0.1

    def open_serial(self):
        if not self.sensor.serial.isOpen():
            self.sensor.serial.open()

    def get_data(self):
        self.open_serial()
        try:
            irr = self.sensor.read_register(0, 1, 4, False)
            ext_temp = self.sensor.read_register(8, 1, 4, True)
            cell_temp = self.sensor.read_register(7, 1, 4, True)
        except Exception as e:
            self.sensor.serial.close()
            raise Exception(e)
        self.sensor.serial.close()
        return irr, ext_temp, cell_temp

    @staticmethod
    def restart_USB2Serial():
        time.sleep(0.5)
        os.system('sudo modprobe -r pl2303')
        time.sleep(0.2)
        os.system('sudo modprobe -r usbserial')
        time.sleep(0.2)
        os.system('sudo modprobe pl2303')
        time.sleep(0.5)
