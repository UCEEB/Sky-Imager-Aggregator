#!/usr/bin/python3
import os
import csv
import datetime as dt

import cv2
from astral import Astral, Location

from src.Configuration import Configuration
from src.SIALogger import Logger

__author__ = 'Jan Havrlant'
__copyright__ = 'MIT'
__credits__ = ['Jan Havrlant', 'Barbara Stefanovska', 'Kamil Sagalara', 'Azim Mazinani']
__license__ = 'Copyright 2018, UCEEB (Czech Technical University in Prague)'
__version__ = '3.0'
__maintainer__ = 'Azim Mazinani'
__email__ = 'azim.mazinani@cvut.cz'
__status__ = 'Development'
__package__ = ''
__doc__ = 'This file contains SIAUtil class which consists of different helper methods for running the raspberry pi'


class SIAUtils(Logger):
    """This class contains the useful methods required for image acquisition and processing in Raspberry Pi for
    Sky Image Scanner project.
    """
    def __init__(self, config_path=None):
        """
        Parameters
        ----------
        config_path: {None, str}, optional
            if not None(default), path to the desired config file instead of the default one
        """
        super().__init__()
        if not config_path:
            self.config = Configuration()
        else:
            self.config = Configuration(config_path=config_path)

    @staticmethod
    def load_image(image, grayscale_mode=True):
        """Loads any digital image for further processing.

        Parameters
        ----------
        image: str
            path to the image
        grayscale_mode: bool, optional
            if True(default), the function will return a grayscale image (only one channel)

        Returns
        -------
        numpy.ndarray
            the matrix of the specified image
        """
        if grayscale_mode:
            return cv2.imread(image, cv2.IMREAD_GRAYSCALE)
        else:
            return cv2.imread(image)

    def apply_mask(self, image, resize=True):
        """Applies a mask to the image to exclude the non-sky regions

        Args:
            image: str
                path to the image
            resize: bool, optional
                if True(default), the function will resize the mask to fit the specified image

        Returns
        -------
        numpy.ndarray
            the matrix of the masked image
        """
        img = self.load_image(image)
        if resize:
            mask = cv2.resize(
                self.load_image(self.config.mask_path),
                img.shape[1::-1]
            )
        else:
            mask = self.load_image(self.config.mask_path)
        return cv2.bitwise_and(img, mask)

    @staticmethod
    def apply_custom_processing(image):
        return image

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
            return dt.datetime.combine(date, dt.time(3, 0, 0, 0, dt.timezone.utc)), \
                   dt.datetime.combine(date, dt.time(21, 0, 0, 0, dt.timezone.utc))

        return sun['sunrise'], sun['sunset']

    def get_path_to_storage(self):
        path = self.config.path_storage
        if self.config.autonomous_mode:
            if os.access(self.config.GSM_path_storage_usb1, os.W_OK):
                path = self.config.GSM_path_storage_usb1
            elif os.access(self.config.GSM_path_storage_usb2, os.W_OK):
                path = self.config.GSM_path_storage_usb2
        return path

    def save_to_storage(self, img, name, image_time):
        path = os.path.join(self.get_path_to_storage(), image_time.strftime("%y-%m-%d"))
        if not os.path.exists(path):
            os.makedirs(path)

        if self.config.autonomous_mode:
            try:
                img.tofile(os.path.join(path, name))
            except Exception as e:
                self.logger.error('Saving to local storage error : ' + str(e))
                pass
            else:
                self.logger.info('image ' + path + '/' + name + ' saved to storage')
                pass
        try:
            img.tofile(os.path.join(self.config.path_storage, name))
        except Exception as e:
            self.logger.error('save to local storage error : ' + str(e))
            pass
        else:
            self.logger.info('image ' + self.config.path_storage + '/' + name + ' saved to storage')
            pass

    def get_free_space_storage(self):
        path = self.get_path_to_storage()
        info = os.statvfs(path)
        free_space = info.f_bsize * info.f_bfree / 1048576
        return '{}.0f MB'.format(free_space)

    # todo check function
    def save_irradiance_csv(self, time, irradiance, ext_temperature, cell_temperature):
        path = self.get_path_to_storage()
        try:
            with open(os.path.join(path, self.config.MODBUS_csv_name), 'a', newline='') as handle:
                csv_file = csv.writer(handle, delimiter=';', quotechar='\'', quoting=csv.QUOTE_MINIMAL)

                if self.config.MODBUS_log_temperature:
                    csv_file.writerow([time, irradiance, ext_temperature, cell_temperature])
                else:
                    csv_file.writerow([time, irradiance])

        except Exception as e:
            self.logger.error('csv save to local storage error : ' + str(e))
        else:
            self.logger.debug('csv row saved in' + path + '/' + self.config.MODBUS_csv_name)
            self.logger.info('irradiance saved ' + str(irradiance))


