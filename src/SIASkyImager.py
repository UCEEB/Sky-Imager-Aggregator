import cv2
import datetime as dt
from SIAUtils import SIAUtil
from Configuration import Configuration
from SIAIrradiance import SIAIrradiance


class SkyImager:

    def __init__(self, logger, config=None):
        self.logger = logger
        if config is None:
            self.config = Configuration('config.ini', logger)
        else:
            self.config = config
        self.utils = SIAUtil(logger)

    def get_free_storage_space(self):
        return self.utils.get_free_space_storage()

    def process_image(self, offline_mode=True):
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

        if offline_mode or self.config.debug_mode:
            filename = img_time.strftime(self.config.filetime_format)
            self.utils.save_to_storage(buffer, filename, img_time)

        else:
            try:
                response = self.utils.upload_json(buffer, img_time)
            except Exception as e:
                self.logger.error('Upload to server error: ' + str(e))
        return

    def get_irradiance_data(self):
        measurement_time = dt.datetime.utcnow()
        irr_sensor = SIAIrradiance(self.logger)

        params = dict(port=self.config.MODBUS_port,
                      address=self.config.MODBUS_sensor_address,
                      baudrate=self.config.MODBUS_baudrate,
                      bytesize=self.config.MODBUS_bytesize,
                      parity=self.config.MODBUS_parity,
                      stopbits=self.config.MODBUS_stopbits)

        try:
            irradiance, ext_temperature, cell_temperature = irr_sensor.get_irradiance_data(**params)
            self.logger.debug('Irradiance: ' + str(irradiance))
            csv_time = measurement_time.strftime("%y-%m-%d_%H-%M-%S")
            self.utils.save_irradiance_csv(csv_time, irradiance, ext_temperature, cell_temperature)
        except Exception as e:
            self.logger.error('Unable to get data from light sensor: ' + str(e))
