## LibraryForPi
# @package   SendStorageV2
# @details   Script sends the images that for some reason were not sent on time.
# @version   3.0
# @author   Jan Havrlant and Barbara Stefanovska
#

import configparser


class ConfigurationObject:
    def __init__(self, path_config, logger):

        config = configparser.ConfigParser()

        try:
            self.counter = -1
            config.read(path_config)

            self.cap_url = config.get('SETTING', 'cap_url')
            self.path_storage = config.get('SETTING', 'path_storage')

            self.server = config.get('SETTING', 'upload_server')
            self.log_path = config.get('SETTING', 'log_path')
            self.log_to_console = config.getboolean('SETTING', 'log_to_console')
            self.upload_format = config.get('SETTING', 'upload_format')
            self.camera_latitude = config.getfloat('SETTING', 'camera_latitude')
            self.camera_longitude = config.getfloat('SETTING', 'camera_longitude')
            self.camera_altitude = config.getfloat('SETTING', 'camera_altitude')
            self.debug_mode = config.getboolean('SETTING', 'debug_mode')
            self.filetime_format = config.get('SETTING', 'filetime_format')
            self.image_quality = config.getint('SETTING', 'image_quality')
            self.crop = [int(x) for x in
                         config.get('SETTING', 'crop').split(",")]  # map(int, config.get('SETTING','crop').split(","))
            self.mask_path = config.get('SETTING', 'mask_path')
            self.cap_mod = config.getint('SETTING', 'cap_mod')
            self.added_time = config.getint('SETTING', 'added_time')
            self.use_private_lib = config.getboolean('SETTING','use_private_lib')
            self.private_lib_name = config.get('SETTING','private_lib_name')
            self.id = config.get('SETTING', 'camera_id')
            self.key = bytes(config.get('SETTING', 'sha256_key'), "ascii")

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
            logger.critical('Configuration file error : ' + str(e))
            return