import logging
import time
from datetime import datetime
from logging import Formatter
from logging import StreamHandler
from logging.handlers import TimedRotatingFileHandler

from i2c_lcd import lcd
from influxdb import InfluxDBClient

_format = Formatter(fmt='[%(asctime)s] %(levelname)s %(threadName)s %(name)s %(message)s')

class DisplayLogHandler(logging.Handler):
    def __init__(self, header=''):
        super().__init__()
        self.lcd = lcd()
        self.header = header

    def emit(self, record):
        self.lcd.lcd_clear()
        self.lcd.lcd_display_string(record.msg[0], line=1)
        self.lcd.lcd_display_string(record.msg[1], line=2)
        time.sleep(3)
        self.lcd.lcd_clear()
        self.lcd.lcd_display_string(self.header, line=1)
        self.lcd.lcd_display_string('   Waiting...   ', line=2)

class InfluxdbLogHandler(logging.Handler):
    def __init__(self, host, username, pwd, database, measurement, port=8086):
        super().__init__()
        # connect to influxdb server
        self.client = InfluxDBClient(host=host, port=port, username=username, password=pwd)
        self.db = database
        db_list = [i['name'] for i in self.client.get_list_database()]
        # check if the database already exists
        if not self.db in db_list:
            # if not, make a new database
            self.client.create_database(self.db)

        self.measurment = measurement
        self.tags = ''

    def add_tags(self, **kwargs):
        tag_set = [
            ',{tag_key}={tag_value}'.format(tag_key=k, tag_value=v)
            for k, v in kwargs.items()
        ]
        self.tags = ''.join(tag_set)

    def emit(self, record):
        line = '{measurement}{tags} ' \
               'name="{name}",' \
               'levelname="{levelname}",' \
               'asctime="{asctime}",' \
               'threadName="{threadName}",' \
               'message="{message}"'.format(
            measurement=self.measurment,
            tags=self.tags,
            name=record.name,
            levelname=record.levelname,
            asctime=record.asctime,
            threadName=record.threadName,
            message=record.message
        )
        self.client.write(data=[line], params={'db': self.db}, protocol='line')


class SensorLogHandler(InfluxdbLogHandler):
    def __init__(self, *args, **kwargs):
        super(SensorLogHandler, self).__init__(*args, **kwargs)

    def emit(self, record):
        line = '{measurement}{tags} ' \
               'image="{message}",' \
               'asctime="{asctime}",' \
               'name="{name}",' \
               'irradiance="{irradiance}",' \
               'ext_temperature="{ext_temperature}",' \
               'cell_temperature="{cell_temperature}"'.format(
            measurement=self.measurment,
            tags=self.tags,
            asctime=record.asctime,
            name=record.name,
            message=record.message,
            irradiance=record.irr,
            ext_temperature=record.ext_temp,
            cell_temperature=record.cell_temp
        )
        self.client.write(data=[line], params={'db': self.db}, protocol='line')


class Logger(logging.Logger):
    def __init__(self, name, level='DEBUG', format=_format):
        super().__init__(name, level)
        self.format = format

    def add_handler(self, handler, format):
        handler.setFormatter(self.format)
        self.addHandler(handler)

    def add_influx_handler(self, host, username, pwd, database, measurement, tags=None):
        handler = InfluxdbLogHandler(host, username, pwd, database, measurement)
        if tags:
            handler.add_tags(**tags)
        self.add_handler(handler, self.format)

    def add_stream_handler(self):
        handler = StreamHandler()
        handler.setLevel(10)  # debug level
        self.add_handler(handler, self.format)

    def add_timed_rotating_file_handler(self, log_file):
        log_file = '{}-{}.log'.format(log_file, datetime.utcnow().strftime('%Y-%m-%d'))
        handler = TimedRotatingFileHandler(log_file, when='MIDNIGHT', backupCount=20)
        self.add_handler(handler, self.format)

    def add_display_handler(self, header):
        handler = DisplayLogHandler(header=header)
        handler.setLevel(20)  # INFO level
        self.add_handler(handler, Formatter(fmt='%(message)s'))

    def add_sensor_handler(self, host, username, pwd, database, measurement, tags=None):
        handler = SensorLogHandler(host, username, pwd, database, measurement)
        if tags:
            handler.add_tags(**tags)
        self.add_handler(handler, Formatter(fmt='%(asctime)s %(message)s'))
