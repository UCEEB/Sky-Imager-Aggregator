from astral import Astral, Location
import datetime as dt
from Configuration import Configuration
from SIALogger import Logger
from SIASkyImager import SkyImager
from SIAGsm import SIAGsm

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler


class SIABash():

    def __init__(self):
        self.logger_object = Logger()
        self.logger = self.logger_object.logger
        self.config = Configuration('config.ini', self.logger)
        self.offline_mode = False

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

    def init(self):

        self.logger_object.set_log_to_file_new_day(self.config.log_path)
        if self.config.autonomous_mode:
            print('Sync time')
            gsm = SIAGsm(self.logger)
            gsm.sync_time(self.config.GSM_port)
            print(dt.datetime.utcnow())
            print(dt.datetime.now())
            self.offline_mode = True

        sun_params = dict(cam_latitude=self.config.camera_latitude,
                          cam_longitude=self.config.camera_longitude,
                          cam_altitude=self.config.camera_altitude
                          )
        sunrise, sunset = self.get_sunrise_and_sunset_date(**sun_params)

        sunrise -= dt.timedelta(minutes=self.config.added_time)
        sunset += dt.timedelta(minutes=self.config.added_time)

        date = dt.datetime.now(dt.timezone.utc).date()

        sky_imager = SkyImager(self.logger, self.config)
        main_scheduler = BlockingScheduler()
        main_scheduler.add_job(SIABash.run_sky_scanner, 'cron', [sky_imager, self.offline_mode, self.config],
                               second='*/' + str(self.config.cap_mod),
                               day_of_week='mon-sun',
                               start_date=sunrise,
                               end_date=sunset, id='sky-scanner')
        main_scheduler.start()

    @staticmethod
    def run_sky_scanner(sky_imager, offline_mode, config):
        
        print('run_sky_scanner')
        sky_imager.process_image(offline_mode)
        #if config.light_sensor:
            #sky_imager.get_irradiance_data()


bash = SIABash()
bash.init()
