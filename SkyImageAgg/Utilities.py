import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from os.path import join
import time


class Utilities:
    def __init__(self):
        self.name = __name__

    @staticmethod
    def set_logger(
            log_dir=None,
            stream=True,
            file_suffix='%Y-%m-%d',
            file_prefix='SIA_logs',
            level=logging.INFO
    ):
        handlers = []

        if log_dir:
            log_file = join(
                log_dir,
                '{}_{}.log'.format(file_prefix, datetime.utcnow().strftime(file_suffix))
            )

            file_handler = TimedRotatingFileHandler(
                log_file,
                when='midnight',
                backupCount=20
            )

            file_handler.suffix = file_suffix
            handlers.append(file_handler)

        if stream:
            handlers.append(logging.StreamHandler())

        logging.basicConfig(
            handlers=handlers,
            level=level,
            format="[%(asctime)s] %(levelname)s %(threadName)s %(name)s %(message)s",
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
