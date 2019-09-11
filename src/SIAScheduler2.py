from astral import Astral, Location
import datetime as dt
import time
from Configuration import Configuration
from SIALogger import Logger
from SIASkyImager import SkyImager
from SIAGsm import SIAGsm
import os.path
import threading
import gzip

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler


class SIAScheduler:

    def __init__(self):
        self.logger_object = Logger()
        self.logger = self.logger_object.logger
        self.config = Configuration('config.ini', self.logger)
        self.offline_mode = False
        self.sky_imager = SkyImager(self.logger, self.config)
        self.sunrise = None
        self.sunset = None
        self.new_day = True
        self.sky_scanner = BackgroundScheduler()
        self.time_sync = False
