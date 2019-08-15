import unittest
from unittest import TestCase
from os import listdir, path

from SIAUtils import SIAUtils


test_dir = path.basename(__file__)


class TestSIAUtils(TestCase):
    def setUp(self):
        self.utils = SIAUtils()

    def test_apply_mask(self):
        for file in listdir('.\\dummy-data'):
            if path.splitext(file)[-1] == '.jpg':
                print(file)
                self.utils.apply_mask(file)

    def test_apply_custom_processing(self):
        pass

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
