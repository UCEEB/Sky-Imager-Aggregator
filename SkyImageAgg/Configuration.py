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
        self.config = configparser.ConfigParser()
        self.config.read(os.path.join(parent_dir, 'config.ini'))

    def set_config(self):
        self.cam_address = self.config.get('SETTING', 'cam_address')
        self.cam_username = self.config.get('SETTING', 'cam_username')
        self.cam_pwd = self.config.get('SETTING', 'cam_password')
        self.storage_path = self.config.get('SETTING', 'storage_path')
        self.ext_storage_path = self.config.get('SETTING', 'ext_storage_path')
        self.server = self.config.get('SETTING', 'upload_server')
        self.log_path = self.config.get('SETTING', 'log_path')
        self.log_to_console = self.config.getboolean('SETTING', 'log_to_console')
        self.integrated_cam = self.config.getboolean('SETTING', 'integrated_cam')
        self.camera_latitude = self.config.getfloat('SETTING', 'camera_latitude')
        self.camera_longitude = self.config.getfloat('SETTING', 'camera_longitude')
        self.camera_altitude = self.config.getfloat('SETTING', 'camera_altitude')
        self.debug_mode = self.config.getboolean('SETTING', 'debug_mode')
        self.time_format = self.config.get('SETTING', 'filetime_format')
        self.image_quality = self.config.getint('SETTING', 'image_quality')
        self.crop_dim = [
            int(i.strip()) for i in self.config.get('SETTING', 'crop').split(',')
        ]
        self.mask_path = self.config.get('SETTING', 'mask_path')
        self.cap_mod = self.config.getint('SETTING', 'cap_mod')
        self.added_time = self.config.getint('SETTING', 'added_time')
        self.use_private_lib = self.config.getboolean('SETTING', 'use_private_lib')
        self.private_lib_name = self.config.get('SETTING', 'private_lib_name')
        self.id = self.config.get('SETTING', 'camera_id')
        self.key = bytes(self.config.get('SETTING', 'sha256_key'), 'ascii')
        self.ntp_server = self.config.get('SETTING', 'ntp_server')
        self.autonomous_mode = self.config.getboolean('SETTING', 'autonomous_mode')
        self.light_sensor = self.config.getboolean('SETTING', 'light_sensor')

        self.GSM_path_storage_usb1 = self.config.get('GSM', 'path_storage_usb1')
        self.GSM_path_storage_usb2 = self.config.get('GSM', 'path_storage_usb2')
        self.GSM_port = self.config.get('GSM', 'port')
        self.GSM_phone_no = self.config.get('GSM', 'phone_no')
        self.GSM_send_thumbnail = self.config.getboolean('GSM', 'send_thumbnail')
        self.GSM_thumbnail_size = self.config.getint('GSM', 'thumbnail_size')
        self.GSM_thumbnail_upload_server = self.config.get('GSM', 'thumbnail_upload_server')
        self.GSM_thumbnail_upload_time_interval = self.config.getint('GSM', 'thumbnail_upload_time_interval')
        self.GSM_time_sync = self.config.getboolean('GSM', 'time_sync')
        self.GSM_send_log = self.config.getboolean('GSM', 'send_log')
        self.GSM_log_upload_server = self.config.get('GSM', 'log_upload_server')
        self.GSM_ppp_config_file = self.config.get('GSM', 'ppp_config_file')


        self.MODBUS_port = self.config.get('MODBUS', 'port')
        self.MODBUS_log_temperature = self.config.getboolean('MODBUS', 'log_temperature')
        self.MODBUS_sensor_address = self.config.getint('MODBUS', 'sensor_address')
        self.MODBUS_baudrate = self.config.getint('MODBUS', 'baudrate')
        self.MODBUS_bytesize = self.config.getint('MODBUS', 'bytesize')
        self.MODBUS_parity = self.config.get('MODBUS', 'parity')
        self.MODBUS_stopbits = self.config.getint('MODBUS', 'stopbits')
        self.MODBUS_csv_name = self.config.get('MODBUS', 'csv_name')
