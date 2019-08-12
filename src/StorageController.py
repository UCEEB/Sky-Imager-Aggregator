#!/usr/bin/python3
import logging
import os
import datetime as dt

import numpy as np

import LibraryForPi
from Configuration import Configuration

__author__ = 'Jan Havrlant'
__copyright__ = 'MIT'
__credits__ = ['Jan Havrlant', 'Barbara Stefanovska']
__license__ = 'Copyright 2018, UCEEB (Czech Technical University in Prague)'
__version__ = '3.0'
__maintainer__ = ''
__email__ = ''
__status__ = 'Development'
__package__ = 'SendStorageV2'
__doc__ = 'Script sends the images that for some reason were not sent on time.'

parent_dir = os.path.dirname(os.path.dirname(__file__))


def run_storage_controller():
    # create and initialize logger
    logger, console = LibraryForPi.set_logger(logging.DEBUG)
    config_path = os.path.join(parent_dir, 'config.ini')

    # read configuration file
    config = Configuration(config_path, logger)

    # create log file
    LibraryForPi.set_log_to_file(config.log_path, config.log_to_console, logger, console)

    # Check if there are any images in the storage
    if os.listdir(config.path_storage):
        logger.info('Storage is not empty!')

        # iterate over the images in the storage path
        for file in os.listdir(config.path_storage):
            image_time = dt.datetime.strptime(file, config.filetime_format)
            image = np.fromfile(
                os.path.join(config.path_storage, file),
                dtype=np.uint8
            )

            try:
                LibraryForPi.upload_json(image, image_time, config)
                logger.info('{} was successfully uploaded to server'.format(file))

                try:
                    os.remove(config.path_storage + '/' + file)
                except Exception as e:
                    logger.error('{} could not be deleted due to the following error:\n{}'.format(file, e))

            except Exception as e:
                logger.error('{} could not be uploaded to server due to the following error:\n{}'.format(file, e))

    else:
        logger.info('Storage is empty!')


if __name__ == '__main__':
    print('Running Storage Controller')
    run_storage_controller()
