import cv2
import numpy as np
import os

class ImageProcessor:
    """
    This class contains the useful methods required for image acquisition and processing in Raspberry Pi for
    Sky Image Scanner project.
    """

    def __init__(self):
        self.mask = None
        self.crop_size = None
        self.jpeg_quality = None

    def set_image_processor(self, raw_input_arr, mask_path, output_size, jpeg_quality):
        """

        Parameters
        ----------
        raw_input_arr
        jpeg_quality
        output_size
        mask_path
        """
        self.mask = self.get_binary_image(mask_path)
        self.crop_size = self.get_crop_size(raw_input_arr, output_size)
        self.jpeg_quality = jpeg_quality

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

    @staticmethod
    def save_as_pic(image_arr, output_name):
        """

        Parameters
        ----------
        image_arr
        output_name
        """
        cv2.imwrite('{}.jpg'.format(output_name), image_arr)

    @staticmethod
    def get_binary_image(image_path):
        """

        Parameters
        ----------
        image_path

        Returns
        -------

        """
        if not os.path.isfile(image_path):
            raise FileNotFoundError('{} doesn\'t exist!'.format(image_path))
        return np.where(cv2.imread(image_path) == 255, 1, 0)

    def apply_binary_mask(self, image_arr):
        """

        Parameters
        ----------
        image_arr

        Returns
        -------

        """
        return np.multiply(self.mask, image_arr)

    @staticmethod
    def get_crop_size(image_arr, output_size):
        """

        Parameters
        ----------
        image_arr
        output_size
        """
        w = image_arr.shape[1]
        w_delta = int((w - output_size[1]) / 2)
        h = image_arr.shape[0]
        h_delta = int((h - output_size[0]) / 2)

        if h_delta < 0 or w_delta < 0:
            raise ValueError('Crop dimensions cannot be larger that the input image!')

        return h_delta, h_delta + output_size[0], w_delta, w_delta + output_size[1]

    def crop(self, image_arr):
        """

        Parameters
        ----------
        image_arr

        Returns
        -------

        """
        return image_arr[
               self.crop_size[0]:self.crop_size[1],
               self.crop_size[2]:self.crop_size[3]
               ]

    @staticmethod
    def make_array_from_image(image_path):
        """

        Parameters
        ----------
        image_path

        Returns
        -------

        """
        return cv2.imread(image_path)

    def encode_image(self, image_arr):
        """

        Parameters
        ----------
        image_arr

        Returns
        -------

        """
        return cv2.imencode('.jpg', image_arr, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])[1]

    @staticmethod
    def make_thumbnail(image, size=(100, 100)):
        """

        Parameters
        ----------
        image
        size

        Returns
        -------

        """
        return cv2.resize(
            image,
            dsize=(size[0], size[1]),
            interpolation=cv2.INTER_NEAREST
        )
