import logging
import datetime as dt
from os.path import join


class Logger:
    def __init__(self):
        self.logger, self.console_logger = self.set_logger()

    @staticmethod
    def set_logger(log_level=logging.DEBUG):
        logger = logging.getLogger('main_logger')
        console_logger = logging.StreamHandler()
        logger.addHandler(console_logger)  # logging to console
        logger.setLevel(log_level)
        logger.info("Setting logger...")

        return logger, console_logger

    def set_log_to_file(self, log_path, log_to_console=True):
        handler = logging.FileHandler(join(log_path, '{}.log'.format(dt.date.today())))
        try:
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            self.logger.addHandler(handler)
        except Exception as e:
            self.logger.error('log file error : {}'.format(e))

        if not log_to_console:
            self.logger.removeHandler(self.console_logger)  # disable console logging

        return handler

    def set_log_to_file_new_day(self, log_path):
        handler = self.set_log_to_file(log_path=log_path)
        self.logger.removeHandler(handler)
        try:
            handler = logging.FileHandler(join(log_path, '{}.log'.format(dt.date.today())))
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            self.logger.addHandler(handler)
        except Exception as e:
            self.logger.error('log file error : {}'.format(e))
        return handler
