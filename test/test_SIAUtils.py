from os import listdir, path
import unittest
from unittest import TestCase

import cv2

from src.SIAUtils import SIAUtils

_test_dir = path.dirname(__file__)


def check_io_types(paras=None, output=None):
    print('Args:\n')
    for p in paras:
        print('\t{}: {}\n'.format(p, type(p)))
    print('Returns\n---------\n{}'.format(type(output)))


class TestSIAUtils(TestCase):
    def setUp(self):
        self.utils = SIAUtils()
        self.config = self.utils.config

    def test_size_of_mask(self):
        mask_size = self.utils.load_image(self.config.mask_path).shape
        for image in listdir(path.join(_test_dir, 'dummy')):
            if path.splitext(image)[-1] in ('.jpg', '.png'):
                img_path = path.join(_test_dir, 'dummy', image)
                print(
                    image,
                    '\'s size is: \n',
                    self.utils.load_image(image=img_path).shape[:],
                    '\nwhile the mask size is:\n',
                    mask_size[:]
                )

    def test_apply_mask(self):
        for image in listdir(path.join(_test_dir, 'dummy')):
            if path.splitext(image)[-1] in ('.jpg', '.png'):
                img_path = path.join(_test_dir, 'dummy', image)

                cv2.imwrite(
                    path.join(_test_dir, 'dummy', 'masked.jpg'),
                    self.utils.apply_mask(img_path)
                )

                check_io_types(
                    paras=[img_path], output=self.utils.load_image(img_path)
                )

    def test_apply_custom_processing(self):
        for image in listdir(path.join(_test_dir, 'dummy')):
            if path.splitext(image)[-1] in ('.jpg', '.png'):
                self.utils.apply_custom_processing(
                    path.join(_test_dir, 'dummy', image)
                )

    def test_encrypt_message(self):
        pass

    def test_send_post_request(self):
        pass

    def test_upload_json(self):
        pass

    def test_upload_bson(self):
        pass

    def test_get_sunrise_and_sunset_date(self):
        pass

    def test_get_path_to_storage(self):
        pass

    def test_save_to_storage(self):
        pass

    def test_get_free_space_storage(self):
        pass

    def test_save_irradiance_csv(self):
        pass

    def test_test_internet_connection(self):
        pass


if __name__ == '__main__':
    unittest.main()
