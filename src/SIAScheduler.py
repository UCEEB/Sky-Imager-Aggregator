from astral import Astral, Location
import datetime as dt
import time
from Configuration import Configuration
from SIALogger import Logger
from SIASkyImager import SkyImager
from SIAGsm import SIAGsm
import os.path
import threading

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler


class SIABash():

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

    @staticmethod
    def datetime_from_utc_to_local(utc_datetime):
        now_timestamp = time.time()
        offset = dt.datetime.fromtimestamp(now_timestamp) - dt.datetime.utcfromtimestamp(now_timestamp)
        return utc_datetime + offset

    @staticmethod
    def get_sunrise_and_sunset_date(cam_latitude, cam_longitude, cam_altitude, date=None):
        if not date:
            date = dt.datetime.now(dt.timezone.utc).date()

        astral = Astral()
        astral.solar_depression = 'civil'
        location = Location(('custom', 'region', cam_latitude, cam_longitude, 'UTC', cam_altitude))

        try:
            sun = location.sun(date=date)
        except Exception:
            return dt.datetime.combine(date, dt.time(5, 0, 0, 0, dt.timezone.utc)), \
                   dt.datetime.combine(date, dt.time(20, 0, 0, 0, dt.timezone.utc))

        return sun['sunrise'], sun['sunset']

    def gsm_task(self):
        print('Sync time')
        gsm_port = self.config.GSM_port
        gsm = SIAGsm(self.logger)
        gsm.sync_time(gsm_port)
        print(dt.datetime.utcnow())
        self.offline_mode = True

        yesterday = dt.datetime.utcnow().date() - dt.timedelta(days=1)
        log_name = '{}.log'.format(str(yesterday))
        log_path = os.path.join(self.config.log_path, log_name)

        if os.path.exists(log_path):
            f = open(log_path, "r")
            file_data = f.read()
            f.close()
            gsm.upload_logfile(file_data)

        images_path = os.path.join(self.config.path_storage, str(yesterday))

        if os.path.exists(images_path):
            first_file_path = os.listdir(images_path)[0]
            f = open(first_file_path, "r")
            img = f.read()
            gsm.send_thumbnail_file(img)
            f.close()

        phone_no = self.config.GSM_phone_no
        free_space = self.sky_imager.get_free_storage_space()
        message = 'SkyImg start, time ' + str(dt.datetime.utcnow()) + ', free space ' + free_space
        print(message)
        print('Sending SMS to: '+ phone_no)
        response = gsm.send_SMS(phone_no, message, gsm_port)
        print('SMS response: '+ str(response))
        self.new_day = False
        gsm.GSM_switch_off(gsm_port)

    def init_sun_time(self):

        sun_params = dict(cam_latitude=self.config.camera_latitude,
                          cam_longitude=self.config.camera_longitude,
                          cam_altitude=self.config.camera_altitude
                          )
        self.sunrise, self.sunset = SIABash.get_sunrise_and_sunset_date(**sun_params)

        self.sunrise -= dt.timedelta(minutes=self.config.added_time)
        self.sunset += dt.timedelta(minutes=self.config.added_time)

        self.sunset = SIABash.datetime_from_utc_to_local(self.sunset)
        self.sunrise = SIABash.datetime_from_utc_to_local(self.sunrise)

    def single_start(self):
        self.init_sun_time()

        self.sky_scanner.add_job(self.run_sky_scanner, 'cron', [self.sky_imager, self.offline_mode, self.config],
                                 second='*/' + str(self.config.cap_mod),
                                 start_date=self.sunrise,
                                 end_date=self.sunset, id='sky-scanner')

        if not self.sky_scanner.running:
            self.sky_scanner.start()

    def control_job(self, skyscanner_scheduler):
        jobs = skyscanner_scheduler.get_jobs()
        if len(jobs) == 0:
            print('starting new day')
            self.new_day = True
            self.single_start()

    def run_sky_scanner(self, sky_imager, offline_mode, config):
        if self.new_day:
            print('Setting new logger')
            self.logger_object.set_log_to_file_new_day(self.config.log_path)

        if self.config.autonomous_mode and self.new_day:
            print('GSM task for new day')
            t = threading.Thread(target = self.gsm_task())
            t.start()
            
        print('run_sky_scanner')
        sky_imager.process_image(offline_mode)
        if config.light_sensor:
            sky_imager.get_irradiance_data()

    def run_control_scheduler(self):
        main_scheduler = BlockingScheduler()
        main_scheduler.add_job(self.control_job, 'cron', [self.sky_scanner],
                               minute='*/30')
        main_scheduler.start()

    def run(self):
        if self.config.autonomous_mode and self.new_day:
            self.gsm_task()
        self.single_start()
        self.run_control_scheduler()


bash = SIABash()
bash.run()
