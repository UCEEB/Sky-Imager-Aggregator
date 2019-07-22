## LibraryForPi
# @package   SendStorageV2
# @details   Script sends the images that for some reason were not sent on time.
# @version   3.0
# @author   Jan Havrlant and Barbara Stefanovska
#

import logging
import os
import datetime as dt
import numpy as np

import LibraryForPi
from ConfigurationClass import ConfigurationObject


def run_storage_controller():
    # create and initialize logger
    logger, console = LibraryForPi.set_logger(logging.DEBUG)
    script_path = os.path.realpath(__file__)
    config_path = os.path.dirname(os.path.realpath(__file__)) + '/config.ini'

    # read configuration file
    config = ConfigurationObject(config_path, logger)

    # create log file
    LibraryForPi.set_log_to_file(config.log_path, config.log_to_console, logger, console)

    # Check if there are any images in the storage
    if os.listdir(config.path_storage):
        logger.info('Storage is not empty')

        files = os.listdir(config.path_storage)

        for file in files:
            image_time = dt.datetime.strptime(file, config.filetime_format)

            image = np.fromfile(config.path_storage + '/' + file, dtype=np.uint8)
            success = True
            try:
                response = LibraryForPi.upload_json(image, image_time, config)
            except Exception as e:
                logger.error(file + ' upload to server error: ' + str(e))
                success = False
                break

            if success:
                logger.info(file + ' upload to server OK')
                try:
                    os.remove(config.path_storage + '/' + file)
                except Exception as e:
                    logger.error(file + ' delete error: ' + str(e))
                    break
    else:
        logger.info('Storage is empty')


if __name__ == '__main__':
    print('Running Storage Controller')
    run_storage_controller()
