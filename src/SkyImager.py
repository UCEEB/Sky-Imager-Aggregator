## LibraryForPi
# @package   SendStorageV2
# @details   Script sends the images that for some reason were not sent on time.
# @version   3.0
# @author   Jan Havrlant and Barbara Stefanovska
#


import cv2
import logging
import os
import datetime as dt
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

import LibraryForPi
from ConfigurationClass import ConfigurationObject


def process_image(scheduler, config, logger):
    logger.info('Capturing image')
    # initialize camera
    cap = cv2.VideoCapture(config.cap_url)

    if not cap.isOpened():
        logger.error('Camera connection error')
        return

    image_time = dt.datetime.utcnow()

    logger.info('Downloading image from camera')
    ret, frame = cap.read()

    # Resizing in case of wrong dimensons
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
            response = LibraryForPi.upload_json(buffer, image_time, config)
        except Exception as e:
            logger.error('Upload to server error: ' + str(e))
            success = False
    else:
        success = False
    if not success or config.debug_mode:
        filename = image_time.strftime(config.filetime_format)
        LibraryForPi.save_to_storage(buffer, config, filename, logger, image_time)

    if success:
        logger.info('Upload to server OK')

    ls = scheduler.get_jobs()
    if (len(ls)) == 0:
        date = dt.date.today() + dt.timedelta(days=1)
        add_image_job(scheduler, config, logger, date)
        logger.info('Added new job for ' + str(date))
    return


def add_image_job(scheduler, config, logger, date=dt.datetime.now(dt.timezone.utc).date()):
    sunrise, sunset = LibraryForPi.get_sunrise_and_sunset_date(config.camera_latitude,
                                                               config.camera_longitude,
                                                               config.camera_altitude,
                                                               date)
    if dt.datetime.now(dt.timezone.utc) > sunset:
        date = dt.date.today() + dt.timedelta(days=1)
        sunrise, sunset = LibraryForPi.get_sunrise_and_sunset_date(config.camera_latitude,
                                                                   config.camera_longitude,
                                                                   config.camera_altitude,
                                                                   date)
        sunrise -= dt.timedelta(minutes=config.added_time)
        sunset += dt.timedelta(minutes=config.added_time)

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

    # create jobs
    main_scheduler = BlockingScheduler()
    auxiliary_scheduler = BackgroundScheduler()

    auxiliary_scheduler.add_job(control_job, 'cron', [main_scheduler, config, logger], hour='*', minute='30',
                                second='5')
    auxiliary_scheduler.start()

    add_image_job(main_scheduler, config, logger)
    main_scheduler.start()


if __name__ == '__main__':
    print('Starting Camera Controller')
    start()
