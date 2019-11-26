import os
import socket
import time
import logging
from logging import NullHandler

import RPi.GPIO as GPIO
import serial

from SkyImageAgg import Utils


class Modem:
    """

    """

    def __init__(self, port='/dev/ttyS0', pin=7, logger=None):
        self.port = port
        self.pin = pin
        self.serial_com = None

        if not logger:
            # Null logger if no logger is defined as parameter
            self._logger = logging.getLogger(__name__).addHandler(NullHandler())
        else:
            self._logger = logger

    def set_pin(self, warnings=False):
        """

        Parameters
        ----------
        warnings
        """
        GPIO.setwarnings(warnings)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)
        time.sleep(3)
        GPIO.output(self.pin, GPIO.HIGH)

    def turn_on_modem(self):
        """

        """
        if not self.is_power_on():
            self._logger.debug("Switching modem on...")
            self.set_pin()
            # give modem some time to login
            time.sleep(10)
        else:
            self._logger.debug("Modem is already powered on...")

    def turn_off_modem(self):
        """

        """
        if self.is_power_on():
            self._logger.debug("Switching modem off...")
            self.set_pin()
            GPIO.cleanup()
            # give modem some time to log out
            time.sleep(5)
        else:
            self._logger.debug("GSM modem is already OFF...")

    def enable_serial_port(self, port, baudrate=115200, timeout=1):
        """

        Parameters
        ----------
        port
        baudrate
        timeout
        """
        if not self.serial_com:
            try:
                self._logger.info('Enabling serial port {} with baudrate {}'.format(port, baudrate))
                self.serial_com = serial.Serial(port, baudrate=baudrate, timeout=timeout)
            except Exception as e:
                self._logger.exception('Serial port error: {}'.format(e))
        else:
            if not self.serial_com.isOpen():
                self.serial_com.open()

    @Utils.timeout(seconds=15, timeout_exception=TimeoutError, use_signals=False)
    def is_power_on(self):
        """

        Returns
        -------

        """
        self._logger.debug('Getting modem state...')
        self.enable_serial_port(self.port)
        time.sleep(.8)
        self.send_command('AT')
        queue = self.serial_com.read(self.serial_com.inWaiting())
        time.sleep(.8)

        if 'OK' in str(queue):
            return True
        else:
            self._logger.warning('Modem is off!')
            return False

    def send_command(self, command):
        """

        Parameters
        ----------
        command
        """
        self.enable_serial_port(self.port)
        time.sleep(.2)
        self.serial_com.write(command.encode() + b'\r\n')
        time.sleep(.2)

    @Utils.retry_on_exception(attempts=3, delay=3)
    def force_switch_on(self):
        """

        """
        self.turn_on_modem()


class Messenger(Modem):
    """

    """
    def __init__(self, port='/dev/ttyS0', pin=7, logger=None):
        super().__init__(port=port, pin=pin, logger=logger)

    def send_sms(self, phone_num, sms_text):
        """

        Parameters
        ----------
        phone_num
        sms_text
        """
        # transmitting AT command
        self.send_command('AT')
        time.sleep(0.2)

        if not self.serial_com.inWaiting() == 0:
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
                self.serial_com.close()
            except Exception as e:
                self._logger.exception(e)

class GPRS(Modem):
    """

    """
    def __init__(self, ppp_config_file, port='/dev/ttyS0', pin=7, logger=None):
        super().__init__(port=port, pin=pin, logger=logger)
        self.ppp_config_file = ppp_config_file

    def has_internet(self, host="8.8.8.8", port=53, timeout=20):
        """

        Parameters
        ----------
        host
        port
        timeout

        Returns
        -------

        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception as e:
            self._logger.error('no internet connection : {}'.format(e))
            return False

    @Utils.timeout(seconds=420, timeout_exception=TimeoutError, use_signals=False)
    def check_internet_connection(self):
        """

        """
        while not self.has_internet():
            time.sleep(5)
        self._logger.info('Internet connection is enabled')

    @Utils.retry_on_exception(attempts=3, delay=120)
    def enable_gprs(self):
        """

        """
        if not self.has_internet():
            try:
                if not self.is_power_on():
                    self.turn_on_modem()
            except TimeoutError:
                self.disable_gprs()
                self.turn_off_modem()  # restart modem
                self.turn_on_modem()
            time.sleep(1)
            os.system(
                'sudo pon {}'.format(os.path.basename(self.ppp_config_file))
            )
            # wait 420 seconds for ppp to start, if not raise TimeoutError
            self.check_internet_connection()
        else:
            self._logger.info('The device is already connected to the internet!')

    def disable_gprs(self):
        """

        """
        self._logger.debug('disabling ppp')
        os.system('sudo killall pppd > null')
        time.sleep(3)

    @staticmethod
    def has_ppp():
        """

        Returns
        -------

        """
        if os.system('ps -A | grep pppd > null') == 0:
            return True
        return False
