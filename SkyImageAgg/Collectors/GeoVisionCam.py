import re
import hashlib

import requests
import cv2
import numpy as np
from bs4 import BeautifulSoup

from SkyImageAgg.Collectors import Camera


class GeoVisionCam(Camera.Cam):
    """

    """
    def __init__(self, cam_address):
        super().__init__()
        self.cam_address = cam_address
        self.user_token = None
        self.pass_token = None
        self.desc_token = None

    @staticmethod
    def _gen_md5(string):
        return hashlib.md5(string.encode('utf-8')).hexdigest()

    def _get_salt_values(self):
        # get html and JS code as text
        page = requests.get('{}/ssi.cgi/Login.htm'.format(self.cam_address))
        html_content = BeautifulSoup(page.content, "html.parser").text
        # parse the salt values from the HTML/JS code of login page(cc1 and cc2)
        salt = re.search(r'cc1=\"(.{4})\".*cc2=\"(.{4})\"', html_content)
        return salt.groups()

    def _get_hashed_credentials(self, username, pwd):
        cc1, cc2 = self._get_salt_values()
        # hash mechanism/formula based on the JS code of camera interface
        umd5 = '{}{}{}'.format(cc1, username.lower(), cc2)
        pmd5 = '{}{}{}'.format(cc2, pwd.lower(), cc1)
        return self._gen_md5(umd5).upper(), self._gen_md5(pmd5).upper()

    def login(self, username, pwd):
        """

        """
        umd5, pmd5 = self._get_hashed_credentials(username, pwd)
        data = {
            'grp': -1,
            'username': '',
            'password': '',
            'Apply': 'Apply',
            'umd5': umd5,
            'pmd5': pmd5,
            'browser': 1,
            'is_check_OCX_OK': 0
        }
        headers = {
            'User-Agent': 'Mozilla'
        }
        c = requests.post('{}/LoginPC.cgi'.format(self.cam_address), data=data, headers=headers)

        self.user_token, self.pass_token, self.desc_token = re.search(
            r'gUserName\s=\s\"(.*)\";\n.*\s\"(.*)\";\n.*\"(.*)\"',
            c.text).groups()

    def cap_pic(self, output='array'):
        """

        Parameters
        ----------
        output

        Returns
        -------

        """
        if self.user_token and self.pass_token and self.desc_token:
            data = {
                'username': self.user_token,
                'password': self.pass_token,
                'data_type': 0,
                'attachment': 1,
                'channel': 1,
                'secret': 1,
                'key': self.desc_token
            }
            r = requests.post('{}/PictureCatch.cgi'.format(self.cam_address), data=data, stream=True)

            if output.lower() == 'array':
                return cv2.imdecode(np.frombuffer(r.content, np.uint8), -1)
            # write the image in the disk
            with open(output, 'wb') as f:
                for chunk in r.iter_content():
                    f.write(chunk)
        else:
            raise Exception('Authentication failed! Wrong username or password!')

    def cap_video(self, output):
        """

        Parameters
        ----------
        output
        """
        raise NotImplementedError
