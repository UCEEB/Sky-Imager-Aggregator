import os
import socket
import time
import datetime as dt
import base64
import hashlib
import hmac
import json

import requests
import serial
import RPi.GPIO as GPIO
import minimalmodbus

from src.SIALogger import Logger


class Modem(Logger):
    def __init__(self, port='ttyS0', pin=7):
        super().__init__()
        self.port = port
        self.pin = pin

    def set_pin(self, warnings=False):
        GPIO.setwarnings(warnings)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)
        time.sleep(3)
        GPIO.output(self.pin, GPIO.HIGH)

    def switch_on(self):
        if not self.isPowerOn():
            self.logger.debug("Switching modem on...")
            self.set_pin()
            # give modem some time to login
            time.sleep(10)
        else:
            self.logger.debug("Modem is already powered on...")

    def switch_off(self):
        if self.isPowerOn():
            self.logger.debug("Switching modem off...")
            self.set_pin()
            GPIO.cleanup()
            # give modem some time to log out
            time.sleep(10)
        else:
            self.logger.debug("GSM modem is already OFF...")

    def force_switch_on(self, no_of_attempts=5):
        self.logger.debug('GSM switch ON')
        if self.isPowerOn():
            self.logger.info('GSM is already ON and running!')
        # try to restart the modem for 5 (default parameter) times
        counter = 0
        while True:
            self.switch_on()
            time.sleep(6)
            counter += 1
            if self.isPowerOn():
                self.logger.info('GSM is ON and ready to go!')
            if counter > no_of_attempts:
                self.logger.debug('GSM switch error! So many attempts without any success!')

    @staticmethod
    def enable_serial_communication(port, baudrate=115200, timeout=1):
        return serial.Serial(port, baudrate=baudrate, timeout=timeout)

    def isPowerOn(self):
        self.logger.debug('Getting modem state...')

        try:
            ser = self.enable_serial_communication('/dev/{}'.format(self.port))
        except Exception as e:
            self.logger.error('Serial port error: {}'.format(e))
            return False

        w_buff = b"AT\r\n"
        ser.write(w_buff)
        time.sleep(0.5)
        queue = ser.read(ser.inWaiting())
        time.sleep(0.5)

        if ser:
            ser.close()

        if queue.find(b'OK') != -1:
            self.logger.info('Modem is ON')
            return True

        self.logger.debug('Modem is OFF')
        return False

    def isOnline(self, host="8.8.8.8", port=53, timeout=6):
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
            self.logger.error('no internet connection : {}'.format(e))
            return False


class Messenger(Modem):
    def __init__(self):
        super().__init__()

    def

class P2PCon(Modem):
    def __init__(self):
        super().__init__()

    def enable(self):
        if not self.isPowerOn():
            self.logger.error('GSM modem is not switched on')
            return False
        self.disable()
        time.sleep(1)
        self.logger.debug('sudo pppd call')
        os.system('sudo pppd call {}'.format(self.GSM_ppp_config_file))

        self.logger.debug('start ppp')
        if not self.wait_for_start(100):
            self.logger.error('No ppp enabled')
            return False

        os.system('sudo ip route add default dev ppp0 > null')
        time.sleep(1)
        counter = 0
        while True:
            if self.isRunning():
                return True
            else:
                counter += 1
                time.sleep(2)
            if counter > 10:
                break

    def disable(self):
        self.logger.debug('disabling ppp')
        os.system('sudo killall pppd 2 > null')
        time.sleep(1)

    def wait_for_start(self, timeout):
        pipe_path = "/tmp/pppipe"
        if not os.path.exists(pipe_path):
            os.mkfifo(pipe_path)
        pipe_fd = os.open(pipe_path, os.O_RDONLY | os.O_NONBLOCK)
        counter = 0
        with os.fdopen(pipe_fd) as pipe:
            while True:
                counter += 1
                try:
                    message = pipe.read()

                    if message.find('UP') != -1:
                        self.logger.debug('ppp UP')
                        return True
                except Exception as e:
                    self.logger.info('error' + str(e))
                    return False
                time.sleep(0.5)
                self.logger.debug('PPP - waiting for start')
                if counter > timeout:
                    break
        return False

    @staticmethod
    def isRunning():
        if os.system('ps -A|grep pppd > null') == 0:
            return True
        return False


class Internet(Modem):
    def __init__(self):
        super().__init__()



    def enable(self, port):
        if self.isOnline():
            self.logger.debug('Internet connection OK')
            return True
        self.PPP.enable(port)
        time.sleep(5)
        counter = 0

        while True:
            if self.isOnline():
                self.logger.debug('Internet connection OK')
                return True
            else:
                counter += 1
                time.sleep(2)
            if counter == 5:
                self.PPP.disable()
                self.PPP.enable(port)
            if counter == 9:
                self.GSM.switch_off(port)
            if counter > 11:
                break

if __name__ == '__main__':
    net = Internet()
    net.switch_on()
    print(net.isOnline())

class WatchDog(Logger):
    def __init__(self):
        super().__init__()
        self.config = Configuration()
        self.internet = Internet()

    @staticmethod
    def encrypt_data(message, key):
        return hmac.new(key, bytes(message, 'ascii'), digestmod=hashlib.sha256).hexdigest()

    def sync_time(self, port, ppp_config_file):
        if not self.internet.enable(port):
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
        signature = self.encrypt_data(json_data, key)
        url = server + signature
        response = self.send_post_request(url, json_data)

        try:
            json_response = json.loads(response.text)
        except Exception as e:
            raise Exception(e)

        if json_response['status'] != 'ok':
            raise Exception(json_response['message'])

        return json_response

    def upload_bson(self, image, file_time):
        date_string = file_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        id = self.config.id
        key = self.config.key

        data = {
            "status": "ok",
            "id": id,
            "time": date_string,
            "coding": "none"
        }

        json_data = json.dumps(data)
        signature = self.encrypt_data(json_data, key)

        if isinstance(image, str) or isinstance(image, bytes):
            files = [('image', image), ('json', json_data)]
        else:
            files = [('image', str(image)), ('json', json_data)]

        response = requests.post(self.config.server + signature, files=files)

        try:
            json_response = json.loads(response.text)
        except Exception as e:
            raise Exception(e)

        if json_response['status'] != 'ok':
            raise Exception(json_response['message'])

        return json_response

    def send_SMS(self, phone_num, message, port):
        #self.internet.PPP.disable()
        self._GSM_switch_on(port)
        ser = serial.Serial(port, 115200)
        write_buffer = [b"AT\r\n", b"AT+CMGF-1\r\n", b"AT+CMGS=\"" + phone_num.encode() + b"\"\r\n", message.encode()]

        ser.write(write_buffer[0])
        time.sleep(0.2)
        if ser.inWaiting() == 0:
            return "fail"
        data = b""
        try:
            data += ser.read(ser.inWaiting())
            time.sleep(0.1)
            data += ser.read(ser.inWaiting())
            ser.write(write_buffer[1])
            time.sleep(0.1)
            data += ser.read(ser.inWaiting())
            ser.write(write_buffer[2])
            time.sleep(0.2)
            ser.write(write_buffer[3])
            ser.write(b"\x1a\r\n")
            time.sleep(0.2)
            response = ser.read(ser.inWaiting())
        except Exception as e:
            if ser is not None:
                ser.close()
            return "Exception " + str(e)
        return response

    def send_thumbnail_file(self, log):
        self.logger.debug('Uploading log to the server')
        counter = 0
        while True:
            counter += 1
            self._enable_internet(self.config)
            try:
                response = self._upload_bson()
                self.logger.info('Upload thumbnail to server OK')
                self._disable_ppp()
                return
            except Exception as e:
                self.logger.error('Upload thumbnail to server error: ' + str(e))
            if counter > 5:
                self.logger.error('Upload thumbnail to server error: too many attempts')
                break
        self.logger.debug('Upload thumbnail to server end')
        self._disable_ppp()

    def _upload_logfile(self, log):
        self.logger.debug('Start upload log to server')
        counter = 0
        while True:
            counter += 1
            self._enable_internet(self.config.GSM_port)
            try:
                response = self.upload_bson(log, dt.datetime.utcnow(), self.config.GSM_log_upload_server)
                self.logger.info('upload log to server OK')

                return
            except Exception as e:
                self.logger.error('upload log to server error : ' + str(e))

            if counter > 5:
                self.logger.error('error upload log to server')
                break

        self.logger.debug('end upload log to server')

    def _upload_bson(self, image, file_time, server):
        date_string = file_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        id = self.config.id
        key = self.config.key

        data = {
            "status": "ok",
            "id": id,
            "time": date_string,
            "coding": "none"
        }
        jsondata = json.dumps(data)
        signature = self.encrypt_data(jsondata, key)

        if isinstance(image, str) or isinstance(image, bytes):
            files = [('image', image), ('json', jsondata)]
        else:
            files = [('image', str(image)), ('json', jsondata)]

        response = requests.post(server + signature, files=files)
        try:
            json_response = json.loads(response.text)
        except Exception as e:
            raise Exception(response)

        if json_response['status'] != 'ok':
            raise Exception(json_response['message'])
        return json_response
