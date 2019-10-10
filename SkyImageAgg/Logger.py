import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from os.path import join


class Logger:
    def __init__(self):
        self.path = None
        self.name = __name__
        self.logger = logging

    def set_logger(self, log_dir=None, stream=True, file_suffix='%Y-%m-%d', level=logging.INFO):
        handlers = []
        if not log_dir and not stream:
            raise ValueError('path and stream cannot be both False!')

        if log_dir:
            log_file = join(log_dir, 'SIA_logs_{}.log'.format(datetime.utcnow().strftime(file_suffix)))
            file_handler = TimedRotatingFileHandler(log_file, when='midnight', backupCount=20)
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

        setattr(self, 'logger', logging)
