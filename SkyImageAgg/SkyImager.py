#!/usr/bin/python3
## LibraryForPi
# @package   SendStorageV2
# @details   Script sends the images that for some reason were not sent on time.
# @version   3.0
# @author   Jan Havrlant and Barbara Stefanovska
#
import threading

import cv2
import logging
import os
import datetime as dt
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

import LibraryForPi
from ConfigurationClass import ConfigurationObject
import Gsm_Modbus


def process_image(scheduler, config, logger):
    if config.autonomous_mode and config.counter == -1:
        if config.GSM_time_sync:
            logger.info('Synchronizing time')
            Gsm_Modbus.gsm_queue.put(Gsm_Modbus.C_sync_time(config.GSM_port, logger, config.GSM_ppp_config_file))
        if config.GSM_phone_no != '':
            SMS_text = 'SkyImg start, df ' + LibraryForPi.get_freespace_storage(
                config) + ', time ' + dt.datetime.utcnow().strftime("%y-%m-%d_%H-%M-%S")
            logger.info('Send SMS: ' + SMS_text)
            Gsm_Modbus.gsm_queue.put(Gsm_Modbus.C_send_SMS(config.GSM_phone_no, SMS_text, config.GSM_port, logger))

    config.counter = 0

    if config.light_sensor:
        get_irradiance_data(config, logger)

    logger.info('Capturing image')
    cap = cv2.VideoCapture(config.cap_url)

    if not cap.isOpened():
        logger.error('Camera connection error')
        return

    image_time = dt.datetime.utcnow()

    logger.info('Downloading image from camera')
    ret, frame = cap.read()

    # Resizing in case of wrong dimensions
    image = frame[config.crop[1]:config.crop[1] + config.crop[3], config.crop[0]:config.crop[0] + config.crop[2]]

    # Masking image
    if len(config.mask_path) > 0:
        logger.info('Applying mask')
        image = LibraryForPi.apply_mask(image, config.mask_path)

        use_private_lib = config.use_private_lib
        if use_private_lib:
            logger.info('Applying custom processing')
            image = LibraryForPi.apply_custom_processing(image, config)

    is_success, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), config.image_quality])

    success = True
    if len(config.server) > 0:
        try:
            response = LibraryForPi.upload_file_as_json(buffer, image_time, config)
        except Exception as e:
            logger.error('Upload to server error: ' + str(e))
            success = False
    else:
        success = False
    if not success or config.debug_mode:
        filename = image_time.strftime(config.filetime_format)
        LibraryForPi.save_to_storage(buffer, config, filename, logger, image_time)
        # Sending thumbnail over GSM
        if config.GSM_send_thumbnail and int(
                image_time.timestamp()) % config.GSM_thumbnail_upload_time_interval < config.cap_mod:
            logger.info("Free space: " + LibraryForPi.get_freespace_storage(config))
            res = cv2.resize(image, dsize=(config.GSM_thumbnail_size, config.GSM_thumbnail_size),
                             interpolation=cv2.INTER_NEAREST)
            is_success, buffer = cv2.imencode(".jpg", res, [int(cv2.IMWRITE_JPEG_QUALITY), config.image_quality])
            Gsm_Modbus.gsm_queue.put(Gsm_Modbus.C_send_thumbnail(logger, config, buffer, image_time))

    if success:
        logger.info('Upload to server OK')

    ls = scheduler.get_jobs()
    if (len(ls)) == 0:
        date = dt.date.today() + dt.timedelta(days=1)
        add_image_job(scheduler, config, logger, date)
        logger.info('Added new job for ' + str(date))
    return


def add_image_job(scheduler, config, logger, date=dt.datetime.now(dt.timezone.utc).date()):
    sunrise, sunset = LibraryForPi.get_sunrise_and_sunset_time(config.camera_latitude,
                                                               config.camera_longitude,
                                                               config.camera_altitude,
                                                               date)
    if dt.datetime.now(dt.timezone.utc) > sunset:
        date = dt.date.today() + dt.timedelta(days=1)
        sunrise, sunset = LibraryForPi.get_sunrise_and_sunset_time(config.camera_latitude,
                                                                   config.camera_longitude,
                                                                   config.camera_altitude,
                                                                   date)
        sunrise -= dt.timedelta(minutes=config.added_time)
        sunset += dt.timedelta(minutes=config.added_time)
        config.counter = -1
        if config.GSM_phone_no != '':
            SMS_text = 'SkyImg end, df ' + LibraryForPi.get_freespace_storage(
                config) + ', time ' + dt.datetime.utcnow().strftime("%y-%m-%d_%H-%M-%S")
            logger.info('Send SMS: ' + SMS_text)
            Gsm_Modbus.gsm_queue.put(Gsm_Modbus.C_send_SMS(config.GSM_phone_no, SMS_text, config.GSM_port, logger))

    scheduler.add_job(process_image, 'cron', [scheduler, config, logger], second='*/' + str(config.cap_mod),
                      start_date=sunrise, end_date=sunset, name=str(date))
    ls = scheduler.get_jobs()
    logger.info('add job ' + get_job_parameter(ls[len(ls) - 1]))


def get_job_parameter(job):
    parameter = 'name ' + job.name + ' start time ' + str(job.trigger.start_date) + ' end time ' + str(
        job.trigger.end_date) + ' ' + str(job.trigger)
    return parameter


def control_job(scheduler, config, logger):
    config.log_file_handler = LibraryForPi.set_log_to_file_new_day(config.log_path, logger,
                                                                   config.log_file_handler)
    ls = scheduler.get_jobs()
    logger.info('run control job ' + str(dt.date.today()))
    if len(ls) == 0:
        add_image_job(scheduler, config, logger)
        logger.error('Some problem, added extra job for: ' + str(dt.date.today()))


def get_irradiance_data(config, logger):
    image_time = dt.datetime.utcnow()
    try:
        irradiance, ext_temperature, cell_temperature = Gsm_Modbus.get_data_irradiance(config.MODBUS_port,
                                                                                       config.MODBUS_sensor_address,
                                                                                       config.MODBUS_baudrate,
                                                                                       config.MODBUS_bytesize,
                                                                                       config.MODBUS_parity,
                                                                                       config.MODBUS_stopbits,
                                                                                       logger
                                                                                       )
        logger.debug('irradiance ' + str(irradiance))
        time_csv = image_time.strftime("%y-%m-%d_%H-%M-%S")
        LibraryForPi.save_irradiance_csv(config, time_csv, irradiance, ext_temperature, cell_temperature, logger)
    except Exception as e:
        logger.error('Unable to get data from light sensor: ' + str(e))


def start():
    # create and initialize logger
    logger, console_logger = LibraryForPi.set_logger(logging.DEBUG)

    # read configuration file
    path_config = os.path.dirname(os.path.realpath(__file__)) + '/config.ini'
    config = ConfigurationObject(path_config, logger)

    # initialize log to file
    config.log_file_handler = LibraryForPi.set_log_to_file(config.log_path,
                                                           config.log_to_console,
                                                           logger,
                                                           console_logger)

    if config.autonomous_mode:
        if config.GSM_time_sync:
            Gsm_Modbus.sync_time(config.GSM_port, logger, config.GSM_ppp_config_file)
        if config.GSM_send_log:
            log_handler = Gsm_Modbus.TailLogHandler(100, logger, config)
            log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            log_handler.setLevel(logging.INFO)
            logger.addHandler(log_handler)
            config.log_internet = log_handler
        config.thread = threading.Thread(target=Gsm_Modbus.GSM_worker, args=[logger])
        config.thread.start()

    # create jobs
    main_scheduler = BlockingScheduler()
    auxiliary_scheduler = BackgroundScheduler()

    auxiliary_scheduler.add_job(control_job, 'cron', [main_scheduler, config, logger], hour='*', minute='30',
                                second='5')
    auxiliary_scheduler.start()

    add_image_job(main_scheduler, config, logger)
    main_scheduler.start()

# todo check function
def run_storage_controller(self):
    # Check if there are any images in the storage
    if self.list_files(self.storage_path):
        self.logger.info('Storage is not empty!')
        # iterate over the images in the storage path

        for image in self.list_files(self.storage_path):
            try:
                self.upload_file_as_json(image)
                self.logger.info('{} was successfully uploaded to server'.format(image))

                try:
                    os.remove(os.path.join(image))

                except Exception as e:
                    self.logger.error('{} could not be deleted due to the following error:\n{}'.format(image, e))

            except Exception as e:

                self.logger.error(
                    '{} could not be uploaded to server due to the following error:\n{}'.format(image, e))

    else:
        self.logger.info('Storage is empty!')

if __name__ == '__main__':
    print('Starting SkyImager')
    start()
