import hashlib
import hmac
import os
import socket
import time
import json
import datetime as dt
import requests
from Configuration import Configuration

if os.name != 'nt':
    import serial
    import RPi.GPIO as GPIO
    import minimalmodbus


def encrypt_data(message, key):
    return hmac.new(key, bytes(message, 'ascii'), digestmod=hashlib.sha256).hexdigest()


class SIAGsm:

    def __init__(self, logger):
        self.config = Configuration(path_config='config.ini', logger=None)
        self.logger = logger

    # public methods
    def sync_time(self, port):
        if not self._enable_internet(port):
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

    def send_SMS(self, phone_num, message, port):
        self._disable_ppp()
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
        signature = encrypt_data(jsondata, key)

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

    def _enable_internet(self, port):
        if self._test_internet_connection():
            self.logger.debug('Internet connection OK')
            return True
        self._enable_ppp(port)
        time.sleep(5)
        counter = 0

        while True:
            if self._test_internet_connection():
                self.logger.debug('Internet connection OK')
                return True
            else:
                counter += 1
                time.sleep(2)
            if counter == 5:
                self._disable_ppp()
                self._enable_ppp(port)
            if counter == 9:
                self._GSM_switch_off(port)
            if counter > 11:
                break

    def _test_internet_connection(self, host="8.8.8.8", port=53, timeout=3):
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception as e:
            self.logger.error('no internet connection : ' + str(e))
            return False

    def _enable_ppp(self, port):
        if not self._GSM_switch_on(port):
            self.logger.error('GSM model not switch on')
            return False
        self._disable_ppp()
        time.sleep(1)
        self.logger.debug('sudo pppd call')
        os.system('sudo pppd call' + self.config.GSM_ppp_config_file)

        self.logger.debug('start ppp')
        if not self._wait_for_start(100):
            self.logger.error('No ppp enabled')
            return False

        os.system('sudo ip route add default dev ppp0 > null')
        time.sleep(1)
        counter = 0
        while True:
            if self._ppp_is_running():
                return True
            else:
                counter += 1
                time.sleep(2)
            if counter > 10:
                break

    def _wait_for_start(self, timeout):
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
    def _ppp_is_running():
        if os.system('ps -A|grep pppd > null') == 0:
            return True
        return False

    def _disable_ppp(self):
        self.logger.debug('disabling ppp')
        os.system('sudo killall pppd 2 > null')
        time.sleep(1)

    def _GSM_switch_on(self, port):
        self.logger.debug('GSM switch ON')
        if SIAGsm._get_GSM_state(port):
            return True

        counter = 0
        while True:
            self._GSM_switch()
            time.sleep(6)
            counter += 1
            if SIAGsm._get_GSM_state(port):
                return True
            if counter > 3:
                self.logger.debug('GSM switch error')

    def _get_GSM_state(self, port):
        self.logger.debug('Getting modem state')
        self._disable_ppp()
        time.sleep(1)
        try:
            ser = serial.Serial(port, 115200)
        except Exception as e:
            self.logger.error('Serial port error: ' + str(e))
            return False
        w_buff = b"AT\r\n"
        ser.write(w_buff)
        time.sleep(0.5)
        r = ser.read(ser.inWaiting())
        if ser is not None:
            ser.close()
        if r.find(b'OK') != -1:
            self.logger('Modem is ON')
            return True
        self.logger.debug('Modem is OFF ' + str(r))
        return False

    def _GSM_switch_off(self, port):
        self.logger.debug('switch modem OFF')
        if not self._get_GSM_state(port):
            return True
        self._GSM_switch()
        if not self._get_GSM_state(port):
            return True
        else:
            return False

    def _GSM_switch(self):
        pin = 12
        self.logger.debug("switching modem")
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(3)
        GPIO.output(pin, GPIO.HIGH)
