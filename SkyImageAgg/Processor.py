import cv2


# todo check function
def process_image(image):
    print('Some processing...')

    # implement some processing here
    image_after_processing = image

    # returns result of processing as another image in the same format
    return image_after_processing


# todo check function
class ImageProcessor:
    """This class contains the useful methods required for image acquisition and processing in Raspberry Pi for
    Sky Image Scanner project.
    """
    def __init__(self):
        """
        Parameters
        ----------
        config_path: {None, str}, optional
            if not None(default), path to the desired config file instead of the default one
        """
        pass

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

    def apply_mask(self, image, mask_path, resize=True):
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
                self.load_image(mask_path),
                img.shape[1::-1]
            )
        else:
            mask = self.load_image(mask_path)
        return cv2.bitwise_and(img, mask)

    @staticmethod
    def apply_custom_processing(image):
        return image



