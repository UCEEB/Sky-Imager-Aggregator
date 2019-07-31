import os
import time
import queue
import LibraryForPi as lfp
import datetime as dt
import logging
import gzip

if os.name != 'nt':
    import serial
    import RPi.GPIO as GPIO
    import minimalmodbus


# MODBUS section
def _get_data_from_sensor(port, address, baudrate, bytesize, parity, stopbits, logger):
    instrument = minimalmodbus.Instrument(port, address)

    if not instrument.serial.isOpen():
        instrument.serial.open()

    instrument.serial.baudrate = baudrate
    instrument.serial.bytesize = bytesize
    instrument.serial.parity = parity
    instrument.serial.stopbits = stopbits
    instrument.serial.rtscts = False
    instrument.serial.dsrdtr = True
    instrument.serial.timeout = 0.1

    try:
        irradiance = instrument.read_register(0, 1, 4, False)
        ext_temperature = instrument.read_register(8, 1, 4, True)
        cell_temperature = instrument.read_register(7, 1, 4, True)
    except Exception as e:
        instrument.serial.close()
        raise Exception(e)
    instrument.serial.close()
    return irradiance, ext_temperature, cell_temperature


def get_data_irradiance(port, address, baudrate, bytesize, parity, stopbits, logger):
    counter = 0
    while True:
        try:
            logger.debug('Reading irradiance')
            irradiance, ext_temperature, cell_temperature = _get_data_from_sensor(port, address, baudrate,
                                                                                  bytesize, parity, stopbits, logger)
        except Exception as e:
            logger.debug('Irradiance error: ' + str(e))
            if counter == 3:
                logger.debug('Restarting USBSerial')
                _restart_USB2Serial()
            elif counter > 5:
                raise Exception(e)
        else:
            logger.debug('Irradiance OK')
            return irradiance, ext_temperature, cell_temperature
        counter += 1
        time.sleep(0.1)


def _restart_USB2Serial():
    time.sleep(0.5)
    os.system('sudo modprobe -r pl2303')
    time.sleep(0.2)
    os.system('sudo modprobe -r usbserial')
    time.sleep(0.2)
    os.system('sudo modprobe pl2303')
    time.sleep(0.5)


# GSM section
def _upload_thumbnail(logger, config, image, image_time):
    logger.debug('Uploading thumbnail to the server...')
    counter = 0

    while True:
        counter += 1
        _enable_internet(config.GSM_port, logger, config.GSM_ppp_config_file)
        try:
            response = lfp.upload_bson(image, image_time, config.GSM_thumbnail_upload_server, config)
            logger.info('Upload thumbnail to server OK')
            return
        except Exception as e:
            logger.error('Upload thumbnail to server error: ' + str(e))

        if counter > 5:
            logger.error('Upload thumbnail to server error: too many attempts')
            break

    logger.debug('Upload thumbnail to server end')


def _get_GSM_state(port, logger):
    logger.debug('Test modem state')
    _disable_ppp(logger)
    time.sleep(1)
    try:
        ser = serial.Serial(port, 115200)
    except Exception as e:
        logger.error('Serial port error: ' + str(e))
        return False
    W_buff = b"AT\r\n"
    ser.write(W_buff)
    time.sleep(0.5)
    r = ser.read(ser.inWaiting())
    if ser is not None:
        ser.close()
    if r.find(b'OK') != -1:
        logger.debug('Modem is On ')
        return True
    logger.debug('Modem is Off ' + str(r))
    return False


def _GSM_switch(logger):
    pin = 12
    logger.debug("switching modem")
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(3)
    GPIO.output(pin, GPIO.HIGH)


def _GSM_switch_on(port, logger):
    logger.debug('switch modem ON')
    if _get_GSM_state(port, logger):
        return True
    count = 0
    while True:
        _GSM_switch(logger)
        time.sleep(12)
        count = count + 1
        if _get_GSM_state(port, logger):
            return True
        if count > 3:
            logger.error('Error switch modem ON')
            return False


def _GSM_switch_off(port, logger):
    logger.debug('switch modem OFF')
    if not _get_GSM_state(port, logger):
        return True
    _GSM_switch(logger)
    if not _get_GSM_state(port, logger):
        return True
    else:
        return False


def _enable_ppp(port, logger, GSM_ppp_config_file):
    if not _GSM_switch_on(port, logger):
        logger.error('GSM modem not switch on')
        return False
    _disable_ppp(logger)
    time.sleep(1)
    logger.debug('sudo pppd call ')
    os.system('sudo pppd call ' + GSM_ppp_config_file)

    logger.debug('start ppp')
    if not _wait_for_start(logger, 100):
        logger.error('No ppp enabled')
        return False

    os.system('sudo ip route add default dev ppp0 > null')
    time.sleep(1)
    counter = 0
    while True:
        if _ppp_is_running():
            return True
        else:
            counter += 1
            time.sleep(2)
        if counter > 10:
            break

    logger.error('No ppp enabled')
    return False


def _ppp_is_running():
    if os.system('ps -A|grep pppd > null') == 0:
        return True
    return False


def _disable_ppp(logger):
    logger.debug('disabling ppp')
    os.system('sudo killall pppd 2>null')
    time.sleep(1)


def _wait_for_start(logger, timeout):
    pipe_path = "/tmp/pppipe"
    if not os.path.exists(pipe_path):
        os.mkfifo(pipe_path)
    # Open the fifo, we need to open in non-blocking mode or it will stalls until
    # someone opens it for writing
    pipe_fd = os.open(pipe_path, os.O_RDONLY | os.O_NONBLOCK)
    count = 0
    with os.fdopen(pipe_fd) as pipe:
        while True:
            count = count + 1
            try:
                message = pipe.read()

                if message.find('UP') != -1:
                    logger.debug('ppp UP')
                    return True

            except Exception as e:
                logger.info('error' + str(e))
                return False
            time.sleep(0.5)
            logger.debug('wait')
            if count > timeout:
                break
    return False


def _enable_internet(port, logger, GSM_ppp_config_file):
    if lfp.test_internet_connection(logger):
        logger.debug('internet connection OK')
        return True
    _enable_ppp(port, logger, GSM_ppp_config_file)
    time.sleep(5)
    counter = 0

    while True:
        if lfp.test_internet_connection(logger):
            logger.debug('Internet connection OK')
            return True
        else:
            counter += 1
            time.sleep(2)
        if counter == 5:
            _disable_ppp(logger)
            _enable_ppp(port, logger, GSM_ppp_config_file)
        if counter == 9:
            _GSM_switch_off(port, logger)
        if counter > 11:
            break

    logger.error('No internet connection')
    return False


def _sendSMS(phone_num, SMS_text, port, logger):
    _disable_ppp(logger)
    _GSM_switch_on(port, logger)
    ser = serial.Serial(port, 115200)
    write_buffer = [b"AT\r\n", b"AT+CMGF=1\r\n", b"AT+CMGS=\"" + phone_num.encode() + b"\"\r\n", SMS_text.encode()]

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
        ser.write(b"\x1a\r\n")  # 0x1a : send   0x1b : Cancel send
        time.sleep(0.2)
        response = ser.read(ser.inWaiting())
    except Exception as e:
        if ser is not None:
            ser.close()
        return "Exception " + str(e)
    return response


def sync_time(port, logger, GSM_ppp_config_file):
    if not _enable_internet(port, logger, GSM_ppp_config_file):
        return False
    count = 0
    while True:
        logger.debug('Trying to synchronize time')
        if os.system('sudo ntpdate -u tik.cesnet.cz') == 0:
            logger.info('Time sync OK')
            break
        else:
            count = count + 1
            time.sleep(1)
        if count > 10:
            logger.error('Time sync error')
            break


def _upload_logfile(logger, conf, log):
    logger.debug('Uploading log to the server')
    count = 0
    while True:
        count = count + 1
        _enable_internet(conf.GSM_port, logger, conf.GSM_ppp_config_file)
        try:
            # attempt to send an image to the server
            response = lfp.upload_bson(log, dt.datetime.utcnow(), conf.GSM_log_upload_server, conf)
            logger.info('upload log to server OK')

            # disable_internet(logger)
            return
        except Exception as e:
            logger.error('upload log to server error : ' + str(e))

        # disable_internet(logger)
        if count > 5:
            logger.error('error upload log to server')
            break

    logger.debug('end upload log to server')


## queue of requests to GSM modem
gsm_queue = queue.Queue()


##Class store request to send SMS
class C_send_SMS:
    def __init__(self, phone_num, SMS_text, port, logger):
        self.phone_num = phone_num
        self.SMS_text = SMS_text
        self.port = port
        self.logger = logger

    def exec(self):
        re = _sendSMS(self.phone_num, self.SMS_text, self.port, self.logger)
        self.logger.debug('Send SMS return' + re.decode("ascii"))


##Class to store request to upload thumbnail
class C_send_thumbnail:
    def __init__(self, logger, conf, image, image_time):
        self.logger = logger
        self.conf = conf
        self.image = image
        self.image_time = image_time

    def exec(self):
        _upload_thumbnail(self.logger, self.conf, self.image, self.image_time)


##Class to store request to synchronization time
class C_sync_time:
    def __init__(self, port, logger, GSM_ppp_config_file):
        self.port = port
        self.logger = logger
        self.GSM_ppp_config_file = GSM_ppp_config_file

    def exec(self):
        sync_time(self.port, self.logger, self.GSM_ppp_config_file)


##Class to store request to upload log to server
class C_send_log:
    def __init__(self, logger, conf, log):
        self.logger = logger
        self.conf = conf
        self.log = log

    def exec(self):
        _upload_logfile(self.logger, self.conf, self.log)


##Class to store request to switch OFF modem
class C_sleep:
    def __init__(self, logger, port):
        self.logger = logger
        self.port = port

    def exec(self):
        _GSM_switch_off(self.port, self.logger)


##Class derive logging.Handler
# special logger, which store log rows and upload its to server if achieves given value of rows
class TailLogHandler(logging.Handler):

    # @param[in] log_queue number of rows which is uploaded together on server
    def __init__(self, log_queue, logger, conf):
        logging.Handler.__init__(self)
        self.store = ""
        self.count = 0
        self.log_queue = log_queue
        self.logger = logger
        self.conf = conf

    def emit(self, record):
        self.store = self.store + self.format(record) + '\n'
        self.count = self.count + 1
        if self.count >= self.log_queue:
            self.send_to_server()

    ## upload log rows to server
    def send_to_server(self):
        if self.count > 0:
            self.count = 0
            gsm_queue.put(C_send_log(self.logger, self.conf, gzip.compress(str.encode(self.store))))
            self.store = ""


def GSM_worker(logger):
    while True:
        try:
            item = gsm_queue.get()
            logger.debug('Execute command from queue')
            item.exec()
            gsm_queue.task_done()
        except Exception as e:
            logger.error('GSM worker error: '+ str(e))