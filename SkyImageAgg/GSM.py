import os
import socket
import time
import serial
from serial.serialutil import SerialException
import math

from timeout_decorator import timeout
import RPi.GPIO as GPIO

from SkyImageAgg.Logger import Logger


def retry_on_failure(attempts, delay=3, back_off=1):
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            m_tries, m_delay = attempts, delay  # make mutable

            rv = f(*args, **kwargs)  # first attempt
            while m_tries > 0:
                if rv is True:  # Done on success
                    return True

                m_tries -= 1
                time.sleep(m_delay)
                m_delay *= back_off

                rv = f(*args, **kwargs)  # Try again

            return False

        return f_retry  # true decorator -> decorated function

    return deco_retry  # @retry(arg[, ...]) -> true decorator


def retry_on_exception(attempts, delay=3, back_off=1):
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            m_tries, m_delay = attempts, delay
            while m_tries > 1:
                try:
                    return f(*args, **kwargs)
                except Exception:
                    time.sleep(m_delay)
                    m_tries -= 1
                    m_delay *= back_off
            return f(*args, **kwargs)

        return f_retry

    return deco_retry


class Modem(Logger):
    def __init__(self, port='/dev/ttyS0', pin=7, log_path=None, stream=True):
        super().__init__()
        self.set_logger(log_dir=log_path, stream=stream)
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
        if not self.is_power_on():
            self.logger.debug("Switching modem on...")
            self.set_pin()
            # give modem some time to login
            time.sleep(10)
        else:
            self.logger.debug("Modem is already powered on...")

    def switch_off(self):
        if self.is_power_on():
            self.logger.debug("Switching modem off...")
            self.set_pin()
            GPIO.cleanup()
            # give modem some time to log out
            time.sleep(5)
        else:
            self.logger.debug("GSM modem is already OFF...")

    def enable_serial_port(self, port, baudrate=115200, timeout=1):
        if not self.serial_com:
            try:
                self.logger.info(
                    'Enabling serial port {} with baudrate {}'.format(port, baudrate)
                )
                self.serial_com = serial.Serial(port, baudrate=baudrate, timeout=timeout)
            except Exception as e:
                self.logger.exception('Serial port error: {}'.format(e))
        else:
            if not self.serial_com.isOpen():
                self.serial_com.open()

    @timeout(seconds=15, timeout_exception=TimeoutError, use_signals=False)
    def is_power_on(self):
        self.logger.debug('Getting modem state...')
        self.enable_serial_port(self.port)
        time.sleep(.8)
        self.send_command('AT')
        queue = self.serial_com.read(self.serial_com.inWaiting())
        time.sleep(.8)

        if 'OK' in str(queue):
            return True
        else:
            self.logger.warning('Modem is off!')
            return False

    def send_command(self, command):
        self.enable_serial_port(self.port)
        time.sleep(.2)
        self.serial_com.write(command.encode() + b'\r\n')
        time.sleep(.2)

    @retry_on_exception(attempts=3, delay=3)
    def force_switch_on(self):
        self.switch_on()


class Messenger(Modem):
    def __init__(
            self,
            port='/dev/ttyS0',
            pin=7,
            log_path=None,
            log_stream=True
    ):
        super().__init__(
            port=port,
            pin=pin,
            log_path=log_path,
            stream=log_stream
        )

    def send_sms(self, phone_num, sms_text):
        self.enable_serial_port(self.port)
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
                self.logger.exception(e)


class GPRS(Modem):
    def __init__(
            self,
            ppp_config_file,
            port='/dev/ttyS0',
            pin=7,
            log_path=None,
            log_stream=True
    ):
        super().__init__(
            port=port,
            pin=pin,
            log_path=log_path,
            stream=log_stream
        )
        self.ppp_config_file = ppp_config_file

    def has_internet(self, host="8.8.8.8", port=53, timeout=20):
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception as e:
            self.logger.error('no internet connection : {}'.format(e))
            return False

    @timeout(seconds=420, timeout_exception=TimeoutError, use_signals=False)
    def check_internet(self):
        while not self.has_internet():
            time.sleep(5)
        self.logger.info('Internet connection is enabled')

    @retry_on_exception(attempts=3, delay=120)
    def enable_gprs(self):
        if not self.has_internet():
            try:
                if not self.is_power_on():
                    self.switch_on()
            except TimeoutError:
                self.disable_gprs()
                self.switch_off()  # restart modem
                self.switch_on()
            time.sleep(1)
            os.system(
                'sudo pon {}'.format(os.path.basename(self.ppp_config_file))
            )
            # wait 420 seconds for ppp to start, if not raise TimeoutError
            self.check_internet()
        else:
            self.logger.info('There is already an internet connection!')

    def disable_gprs(self):
        self.logger.debug('disabling ppp')
        os.system('sudo killall pppd > null')
        time.sleep(3)

    @staticmethod
    def has_ppp():
        if os.system('ps -A | grep pppd > null') == 0:
            return True
        return False
