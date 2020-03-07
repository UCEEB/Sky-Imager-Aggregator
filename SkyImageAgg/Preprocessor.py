import cv2
import numpy as np
import os
import datetime as dt

from SkyImageAgg.Collectors.Camera import Cam


def load_image(image, grayscale_mode=True):
    """
    Load image from disk and convert it to an array

    Parameters
    ----------
    image: str
        path to the image.
    grayscale_mode: bool, default True, optional
        if True(default), the function will return a grayscale image (only one channel).

    Returns
    -------
    numpy.array
        the numpy array of the specified image.
    """
    if grayscale_mode:
        return cv2.imread(image, cv2.IMREAD_GRAYSCALE)
    else:
        return cv2.imread(image)


def get_binary_image(image):
    """
    Load an image from disk and convert it into a binary image

    Parameters
    ----------
    image: str
        path to the image.
    Returns
    -------
    numpy.array
        the numpy array of the specified image.
    """
    if not os.path.isfile(image):
        raise FileNotFoundError(f'{image} doesn\'t exist!')
    return np.where(cv2.imread(image) == 255, 1, 0)


class SkyImage:
    """
    Hold the necessary methods to create an object to manipulate the containing image.

    Attributes
    ----------
    cam : Cam
        camera object.
    image : numpy.array
        the image array of the constructing picture if exists.
    mask : numpy.array
        mask array of the image.
    crop_size : tuple of (int, int, int, int)
        corners of the crop frame.
    jpeg_quality : int
        the desired jpeg quality for the captured/loaded image.
    timestamp: str or datetime.datetime
        the timestamp of the image.
    path: str
        the path to the image.
    """

    def __init__(self, camera, image=None):
        """
        Construct the SkyImage object.

        Parameters
        ----------
        camera : Cam or None
            camera object.
        image : numpy.array or str, default None
            the image array or path of the constructing picture if exists.
        """
        if isinstance(camera, Cam):
            self.cam = camera
            self.image = self.cam.cap_pic()
        elif image:
            self.cam = Cam()
            self.set_picture(image)
        else:
            self.cam = None
            self.image = None

        self.mask = None
        self.crop_size = None
        self.jpeg_quality = None
        self.timestamp = None
        self.path = None

    @classmethod
    def setup_by_image(cls, image, mask_path, output_resolution, jpeg_quality):
        """
        Construct the object with only a image and no camera.

        Parameters
        ----------
        image : numpy.array or str, default None
            the image array or path of the constructing picture if exists.
        mask_path : str
            path to the mask.
        output_resolution : tuple of (int, int)
            the number of pixels in x and y of the output image.
        jpeg_quality : int
            the jpeg compression quality.

        Returns
        -------
        SkyImage
            return the `SkyImage` object.
        """
        obj = cls(camera=None, image=image)
        obj.set_mask(mask_path)
        obj.get_crop_size(output_resolution)
        obj.jpeg_quality = jpeg_quality
        return obj

    @classmethod
    def setup_by_camera(cls, camera, mask_path, output_resolution, jpeg_quality):
        """
        Construct the object with only a camera and no image.

        this is useful when you want to construct the object with additional available data.

        Parameters
        ----------
        camera : Cam or None
            camera object.
        mask_path : str
            path to the mask.
        output_resolution : tuple of (int, int)
            the number of pixels in x and y of the output image.
        jpeg_quality : int
            the jpeg compression quality.

        Returns
        -------
        SkyImage
            return the `SkyImage` object.
        """
        obj = cls(camera=camera)
        obj.set_mask(mask_path)
        obj.get_crop_size(output_resolution)
        obj.jpeg_quality = jpeg_quality
        return obj

    @classmethod
    def setup_empty(cls):
        """
        Construct the SkyImage object without any data.

        This is useful when you want to add the data later.

        Returns
        -------
        SkyImage
            return the `SkyImage` object.
        """
        return cls(camera=None, image=None)

    def switch_camera(self, camera):
        """
        Switch camera and assign it to cam attribute.

        Parameters
        ----------
        camera : Cam
            camera object.
        """
        self.cam = camera

    def snap_picture(self):
        """
        Snap a picture and assign it to image attribute.
        """
        self.set_timestamp()
        self.image = self.cam.cap_pic()

    def set_picture(self, image):
        """
        Set a new picture in the object and assign it ti image attribute.

        Parameters
        ----------
        image : numpy.array or str, default None
            the image array or path of the constructing picture if exists.
        """
        if isinstance(image, str):
            self.image = load_image(image, grayscale_mode=False)
        else:
            self.image = image

    def set_crop_size(self, output_resolution):
        """
        Set the crop frame corners based on the given output resolution.

        output_resolution : tuple of (int, int)
            the number of pixels in x and y of the output image.
        """
        self.crop_size = self.get_crop_size(output_resolution)

    def set_mask(self, mask_path):
        """
        Set the mask as a binary array and assign it to mask attribute.

        Parameters
        ----------
        mask_path : str
            path to the mask.
        """
        self.mask = get_binary_image(mask_path)

    def apply_mask(self):
        """
        Apply the stored mask the to containing image.
        """
        self.image = np.multiply(self.mask, self.image)

    def set_timestamp(self, timestamp=None):
        """
        Set the timestamp and assign it to timestamp attribute.

        If there is no timestamp given, uses current UTC time.

        Parameters
        ----------
        timestamp: str or datetime.datetime, default None
            the timestamp of the image.
        """
        if not timestamp:
            self.timestamp = dt.datetime.utcnow()
        else:
            self.timestamp = timestamp

    def set_path(self, path):
        """
        Set the path to the containing image and assign it to the path attribute.

        Parameters
        ----------
        path : str
            path to where the image should be saved.
        """
        self.path = path

    def get_crop_size(self, output_resolution):
        """
        Calculate the crop frame corners based on the desired output resolution.

        Parameters
        ----------
        output_resolution : tuple of (int, int)
            the number of pixels in x and y of the output image.

        Returns
        -------
        tuple of (int, int, int, int)
            Return corners of the crop frame.
        """
        w = self.image.shape[1]
        w_delta = int((w - output_resolution[1]) / 2)
        h = self.image.shape[0]
        h_delta = int((h - output_resolution[0]) / 2)

        if h_delta < 0 or w_delta < 0:
            raise ValueError('Crop dimensions cannot be larger that the input image!')

        return h_delta, h_delta + output_resolution[0], w_delta, w_delta + output_resolution[1]

    def crop(self):
        """
        Crop the containing image and assign it to image attribute.
        """
        self.image = self.image[
                     self.crop_size[0]:self.crop_size[1],
                     self.crop_size[2]:self.crop_size[3]
                     ]

    def encode_to_jpeg(self):
        """
        Return the containing image in jpeg format.

        Returns
        -------
        numpy.array
            the jpeg compressed numpy array of the specified image.
        """
        try:
            return cv2.imencode('.jpg', self.image, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])[1]
        except SystemError:
            raise TypeError('It seems jpeg_quality attr is set to None!')

    def make_thumbnail(self, size=(100, 100)):
        """
        Return the containing image as a thumbnail.

        Parameters
        ----------
        size : tuple of (int, int), default (100, 100)
            pixel resolution of the thumbnail.

        Returns
        -------
        numpy.array
            the numpy array of the specified thumbnail.
        """
        return cv2.resize(
            self.image,
            dsize=(size[0], size[1]),
            interpolation=cv2.INTER_NEAREST
        )

    def save_as_jpeg(self, output_path=None):
        """
        Save image on the disk.

        If you path output as None then it saves it in the directory from path attribute.

        Parameters
        ----------
        output_path : str, default None
            the path where you want to save the image.
        """
        if not output_path:
            output_path = self.path
        cv2.imwrite(f'{output_path}.jpg', self.image, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
