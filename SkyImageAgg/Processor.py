import cv2

# Configuration should not be called in anywhere but main class
# todo check function
from SkyImageAgg.Configuration import Configuration

# This is the main function which is executed in another scripts
# Function accepts image as parameter and returns processed image
# This function declaration can't be changed!!!


# todo check function
def process_image(image):
    print('Some processing...')

    # implement some processing here
    image_after_processing = image

    # returns result of processing as another image in the same format
    return image_after_processing

# some other functions...


# todo check function
class ImageProcessor:
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



