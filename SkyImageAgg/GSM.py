import os
import socket
import time
import serial
from serial.serialutil import SerialException
import math

import RPi.GPIO as GPIO

from SkyImageAgg.Logger import Logger


class Modem(Logger):
    def __init__(self, port='/dev/ttyS0', pin=7):
        super().__init__()
        self.port = port
        self.pin = pin
        self.serial_com = None

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

    def enable_serial_port(self, port, baudrate=115200, timeout=1):
        if not self.serial_com:
            try:
                self.logger.info('Enabling serial port {} with baudrate {}'.format(port, baudrate))
                setattr(self, 'serial_com', serial.Serial(port, baudrate=baudrate, timeout=timeout))
            except Exception as e:
                self.logger.debug('Serial port error: {}'.format(e))

    def send_command(self, command):
        if not self.serial_com:
            raise SerialException
        time.sleep(.2)
        self.serial_com.write(command.encode() + b'\r\n')
        time.sleep(.2)

    def isPowerOn(self):
        self.logger.debug('Getting modem state...')

        try:
            self.enable_serial_port(self.port)
        except Exception as e:
            self.logger.debug(e)
            return False

        self.send_command('AT')
        queue = self.serial_com.read(self.serial_com.inWaiting())
        time.sleep(.8)

        if self.serial_com:
            self.serial_com.close()

        if queue.find(b'OK') != -1:
            self.logger.info('Modem is ON')
            return True

        self.logger.debug('Modem is OFF')
        return False

    @staticmethod
    def retry_on_failure(attempts, delay=3, back_off=1):
        if back_off < 1:
            raise ValueError("back_off must be greater than or equal to 1")

        attempts = math.floor(attempts)
        if attempts < 0:
            raise ValueError("tries must be 0 or greater")

        if delay <= 0:
            raise ValueError("delay must be greater than 0")

        def deco_retry(f):
            def f_retry(*args, **kwargs):
                m_tries, m_delay = attempts, delay  # make mutable

                rv = f(*args, **kwargs)  # first attempt
                while m_tries > 0:
                    if rv is True:  # Done on success
                        return True

                    m_tries -= 1  # consume an attempt
                    time.sleep(m_delay)  # wait...
                    m_delay *= back_off  # make future wait longer

                    rv = f(*args, **kwargs)  # Try again

                return False  # Ran out of tries :-(

            return f_retry  # true decorator -> decorated function

        return deco_retry  # @retry(arg[, ...]) -> true decoratorv


class Messenger(Modem):
    def __init__(self):
        super().__init__()

    def submit_text(self, phone_num, sms_text):
        self.enable_serial_port(self.port)
        # transmitting AT command
        self.send_command('AT')
        time.sleep(0.2)

        if self.serial_com.inWaiting() == 0:
            return False

        try:
            # select message format
            self.send_command('AT+CMGF=1')
            # disable the Echo
            self.send_command('ATE0')
            # send a message to a particular number
            self.send_command('AT+CMGS=\"{}\"'.format(phone_num))
            # send text
            self.send_command(sms_text)
            # enable to send sms
            self.serial_com.write(b"\x1a\r\n")  # 0x1a : send   0x1b : Cancel send
            self.serial_com.read(self.serial_com.inWaiting())
        except Exception as e:
            self.logger.debug(e)

            if self.serial_com:
                self.serial_com.close()

            return False

        return True

    def send_sms(self, phone_num, sms_text):
        outbox = True
        while outbox:
            print('Trying to send SMS to {}...'.format(phone_num))
            outbox = self.submit_text(phone_num, sms_text)
            time.sleep(0.3)

        return outbox


class GPRS(Modem):
    def __init__(self, ppp_config_file):
        super().__init__()
        self.ppp_config_file = ppp_config_file

    def enable_GPRS(self):
        if self.hasInternetConnection():
            self.logger.debug('Internet connection OK')

            return True

        self.enable_ppp()
        time.sleep(5)
        counter = 0

        while True:
            print(counter)
            if self.hasInternetConnection():
                self.logger.debug('Internet connection OK')

                return True

            else:
                counter += 1
                time.sleep(2)

            if counter == 5:
                self.disable_ppp()
                self.enable_ppp()

            if counter == 9:
                self.switch_off()

            if counter > 11:
                break

    def hasInternetConnection(self, host="8.8.8.8", port=53, timeout=3):
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception as e:
            self.logger.error('no internet connection : ' + str(e))
            return False

    def enable_ppp(self):
        if not self.isPowerOn():
            self.logger.error('GSM model not switch on')
            return False
        self.disable_ppp()
        time.sleep(1)
        self.logger.debug('sudo pppd call')
        os.system('sudo pppd call ' + self.ppp_config_file)

        self.logger.debug('start ppp')
        if not self.wait_for_ppp_start(100):
            self.logger.error('No ppp enabled')
            return False

        os.system('sudo ip route add default dev ppp0 > null')
        time.sleep(1)
        counter = 0
        while True:
            if self.hasPPP():
                return True
            else:
                counter += 1
                time.sleep(2)
            if counter > 10:
                break

    def wait_for_ppp_start(self, timeout):
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
    def hasPPP():
        if os.system('ps -A|grep pppd > null') == 0:
            return True
        return False

    def disable_ppp(self):
        self.logger.debug('disabling ppp')
        os.system('sudo killall pppd 2 > null')
        time.sleep(1)
