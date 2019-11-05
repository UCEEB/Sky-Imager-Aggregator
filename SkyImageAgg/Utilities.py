import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from influxdb import InfluxDBClient
from pythonjsonlogger import jsonlogger
from os.path import join
import time
import json


class InfluxdbLogHandler(logging.Handler):
    def __init__(self, host, username, pwd, database, measurement, port=8086):
        super().__init__()
        # connect to influxdb server
        self.client = InfluxDBClient(
            host=host,
            port=port,
            username=username,
            password=pwd
        )
        # check if the database already exists
        self.db = database
        db_list = [i['name'] for i in self.client.get_list_database()]
        if not self.db in db_list:
            # if not, make a new database
            self.client.create_database(self.db)
        self.measurment = measurement
        self.tags = ''

    def add_tags(self, **kwargs):
        tag_set = [
            ',{tag_key}={tag_value}'.format(tag_key=k, tag_value=v)
            for k, v in self.kwargs.items()
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

class Utilities:
    @staticmethod
    def set_logger(
            log_dir=None,
            stream=True,
            remote=True,
            suffix='%Y-%m-%d',
            prefix='SIA_logs',
            level=logging.INFO,
            fmt="[%(asctime)s] %(levelname)s %(threadName)s %(name)s %(message)s",
            **kwargs
    ):
        handlers = []

        if log_dir:
            log_file = join(
                log_dir,
                '{}_{}.log'.format(prefix, datetime.utcnow().strftime(suffix))
            )

            file_handler = TimedRotatingFileHandler(
                log_file,
                when='midnight',
                backupCount=20
            )

            file_handler.setFormatter(jsonlogger.JsonFormatter(fmt))
            file_handler.suffix = suffix
            handlers.append(file_handler)

        if stream:
            strm_handler = logging.StreamHandler()
            handlers.append(strm_handler)

        if remote:
            remote_handler = InfluxdbLogHandler(kwargs)
            handlers.append(remote_handler)

        logging.basicConfig(
            handlers=handlers,
            level=level,
            format=fmt,
            datefmt='%Y-%m-%dT%H:%M:%S'
        )

        return logging

    @classmethod
    def retry_on_failure(cls, attempts, delay=3, back_off=1):
        """

        Parameters
        ----------
        attempts
        delay
        back_off

        Returns
        -------

        """

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

    @classmethod
    def retry_on_exception(cls, attempts, delay=3, back_off=1):
        """

        Parameters
        ----------
        attempts
        delay
        back_off

        Returns
        -------

        """

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

    @classmethod
    def loop_infinitely(cls, time_gap=3):
        """
        A decorator to transform functions into a recurrent function executed on a timely basis.

        Parameters
        ----------
        time_gap : `int`
            the time gap between each execution (default is 3)

        Returns
        -------
        `function`
            the recurring function that is decorated
        """

        def deco_retry(f):
            def f_retry(*args, **kwargs):
                while True:
                    kick_off = time.time()
                    if time_gap != 0:
                        f(*args, **kwargs)
                        try:
                            wait = time_gap - (time.time() - kick_off)
                            time.sleep(wait)
                        except ValueError:
                            pass
                    else:
                        f(*args, **kwargs)

            return f_retry

        return deco_retry
