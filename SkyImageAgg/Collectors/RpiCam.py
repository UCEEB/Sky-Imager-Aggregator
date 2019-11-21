import time
from io import BytesIO

import cv2
import numpy as np
import picamera
from picamera import PiCamera

from SkyImageAgg.Collectors.Camera import Cam


class RpiCam(Cam):
    """

    """
    def __init__(self):
        super().__init__()
        try:
            self.cam = PiCamera()
        except picamera.exc.PiCameraMMALError as e:
            raise ConnectionError('It seems that the RPi camera is being used by another application!')
        self.cam.resolution = (2592, 1944)
        self.cam.start_preview()
        time.sleep(2)

    def login(self, address, username, pwd):
        """

        Parameters
        ----------
        address
        username
        pwd
        """
        raise NotImplementedError

    # todo check
    def cap_pic(self, output='array'):
        """

        Parameters
        ----------
        output

        Returns
        -------

        """
        if output == 'array':
            output = BytesIO()
            self.cam.capture(output, format='jpeg')
            # "Rewind" the stream to the beginning so we can read its content
            output.seek(0)
            return cv2.imdecode(np.frombuffer(output.read(), np.uint8), -1)
        else:
            self.cam.capture(output)

    def cap_video(self, output):
        """

        Parameters
        ----------
        output
        """
        raise NotImplementedError
