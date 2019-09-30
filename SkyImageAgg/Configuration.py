import configparser
import os


__author__ = 'Jan Havrlant'
__copyright__ = 'MIT'
__credits__ = ['Jan Havrlant', 'Barbara Stefanovska']
__license__ = 'Copyright 2018, UCEEB (Czech Technical University in Prague)'
__version__ = '0.1'
__maintainer__ = ''
__email__ = ''
__status__ = 'Development'
__package__ = 'SendStorageV2'

parent_dir = os.path.dirname(os.path.dirname(__file__))


class Configuration:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read(os.path.join(parent_dir, 'config.ini'))

        try:
            self.cam_address = config.get('SETTING', 'cam_address')
            self.cam_username = config.get('SETTING', 'cam_username')
            self.cam_pwd = config.get('SETTING', 'cam_password')
            self.storage_path = config.get('SETTING', 'storage_path')
            self.ext_storage_path = config.get('SETTING', 'ext_storage_path')
            self.server = config.get('SETTING', 'upload_server')
            self.log_path = config.get('SETTING', 'log_path')
            self.log_to_console = config.getboolean('SETTING', 'log_to_console')
            self.integrated_cam = config.getboolean('SETTING', 'integrated_cam')
            self.camera_latitude = config.getfloat('SETTING', 'camera_latitude')
            self.camera_longitude = config.getfloat('SETTING', 'camera_longitude')
            self.camera_altitude = config.getfloat('SETTING', 'camera_altitude')
            self.debug_mode = config.getboolean('SETTING', 'debug_mode')
            self.time_format = config.get('SETTING', 'filetime_format')
            self.image_quality = config.getint('SETTING', 'image_quality')
            self.crop = [
                int(i.strip()) for i in config.get('SETTING', 'crop').split(',')
            ]
            self.mask_path = config.get('SETTING', 'mask_path')
            self.cap_mod = config.getint('SETTING', 'cap_mod')
            self.added_time = config.getint('SETTING', 'added_time')
            self.use_private_lib = config.getboolean('SETTING', 'use_private_lib')
            self.private_lib_name = config.get('SETTING', 'private_lib_name')
            self.id = config.get('SETTING', 'camera_id')
            self.key = bytes(config.get('SETTING', 'sha256_key'), 'ascii')
            self.ntp_server = config.get('SETTING', 'ntp_server')
            self.autonomous_mode = config.getboolean('SETTING', 'autonomous_mode')
            self.light_sensor = config.getboolean('SETTING', 'light_sensor')

            if self.autonomous_mode:
                self.GSM_path_storage_usb1 = config.get('GSM', 'path_storage_usb1')
                self.GSM_path_storage_usb2 = config.get('GSM', 'path_storage_usb2')
                self.GSM_port = config.get('GSM', 'port')
                self.GSM_phone_no = config.get('GSM', 'phone_no')
                self.GSM_send_thumbnail = config.getboolean('GSM', 'send_thumbnail')
                self.GSM_thumbnail_size = config.getint('GSM', 'thumbnail_size')
                self.GSM_thumbnail_upload_server = config.get('GSM', 'thumbnail_upload_server')
                self.GSM_thumbnail_upload_time_interval = config.getint('GSM', 'thumbnail_upload_time_interval')
                self.GSM_time_sync = config.getboolean('GSM', 'time_sync')
                self.GSM_send_log = config.getboolean('GSM', 'send_log')
                self.GSM_log_upload_server = config.get('GSM', 'log_upload_server')
                self.GSM_ppp_config_file = config.get('GSM', 'ppp_config_file')

            if self.light_sensor:
                self.MODBUS_port = config.get('MODBUS', 'port')
                self.MODBUS_log_temperature = config.getboolean('MODBUS', 'log_temperature')
                self.MODBUS_sensor_address = config.getint('MODBUS', 'sensor_address')
                self.MODBUS_baudrate = config.getint('MODBUS', 'baudrate')
                self.MODBUS_bytesize = config.getint('MODBUS', 'bytesize')
                self.MODBUS_parity = config.get('MODBUS', 'parity')
                self.MODBUS_stopbits = config.getint('MODBUS', 'stopbits')
                self.MODBUS_csv_name = config.get('MODBUS', 'csv_name')

        except Exception as e:
            ###########################
            # logger should be added ##
            ###########################
            raise Exception('Configuration file error: {}'.format(e))
