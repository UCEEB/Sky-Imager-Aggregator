# Author: Barbara Stefanovska 
#...
import cv2
import numpy as np
from urllib import request
import base64


class ipCamera(object):

    def __init__(self, url, user=b'LI20411', password=b'Bustehrad2734'):
        self.url = url
        auth_encoded = base64.encodebytes('%s:%s' % (user, password))[:-1]

        self.req = request.Request(self.url)
        self.req.add_header('Authorization', 'Basic %s' % auth_encoded)

    def get_frame(self):
        response = request.urlopen(self.req)
        img_array = np.asarray(bytearray(response.read()), dtype=np.uint8)
        frame = cv2.imdecode(img_array, 1)
        return frame
