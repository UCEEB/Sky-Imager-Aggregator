import cv2
import datetime as dt
from SIAUtils import SIAUtil
from Configuration import Configuration


class SkyImager:

    def __init__(self, logger, config=None):
        self.logger = logger
        if config is None:
            self.config = Configuration('config.ini', logger)
        else:
            self.config = config
        self.utils = SIAUtil(logger)

    def process_image(self):
        cap = cv2.VideoCapture(self.config.cap_url)

        if not cap.isOpened():
            self.logger.error('Camera connection error')
            return
        img_time = dt.datetime.utcnow()
        self.logger.info('Downloading image from camera')
        ret, frame = cap.read()

        crop0 = self.config.crop[0]
        crop1 = self.config.crop[1]
        crop2 = self.config.crop[2]
        crop3 = self.config.crop[3]

        image = frame[crop1:crop1 + crop3, crop0:crop0 + crop2]

        if len(self.config.mask_path) > 0:
            image = self.utils.apply_mask(image)

            use_private_lib = self.config.use_private_lib
            if use_private_lib:
                self.logger.info('Applying custom processing')
                image = SIAUtil.apply_custom_processing(image)

        is_success, buffer = cv2.imencode('.jpg', image,
                                          [int(cv2.IMWRITE_JPEG_QUALITY), self.config.image_quality])

        success = True
        if len(self.config.server) > 0:
            try:
                response = self.utils.upload_json(buffer, img_time)
            except Exception as e:
                self.logger.error('Upload to server error: ' + str(e))
                success = False
        else:
            success = False

        if not success or self.config.debug_mode:
            filename = img_time.strftime(self.config.filetime_format)
            self.utils.save_to_storage(buffer, filename, img_time)
        return

    def get_irradiance_data(self):
        measurement_time = dt.datetime.utcnow()
        pass
