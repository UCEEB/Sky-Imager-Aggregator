import configparser


class Configuration:
    """

    """

    def __init__(self, config_file):
        self.conf = configparser.ConfigParser()
        self.conf.read(config_file)
        self.cam_address = self.conf.get('SETTING', 'cam_address')
        self.cam_username = self.conf.get('SETTING', 'cam_username')
        self.cam_pwd = self.conf.get('SETTING', 'cam_password')
        self.storage_path = self.conf.get('SETTING', 'storage_path')
        self.ext_storage_path = self.conf.get('SETTING', 'ext_storage_path')
        self.server = self.conf.get('SETTING', 'upload_server')
        self.log_path = self.conf.get('SETTING', 'log_path')
        self.log_to_console = self.conf.getboolean('SETTING', 'log_to_console')
        self.integrated_cam = self.conf.getboolean('SETTING', 'integrated_cam')
        self.camera_latitude = self.conf.getfloat('SETTING', 'camera_latitude')
        self.camera_longitude = self.conf.getfloat('SETTING', 'camera_longitude')
        self.camera_altitude = self.conf.getfloat('SETTING', 'camera_altitude')
        self.time_format = self.conf.get('SETTING', 'filetime_format')
        self.night_mode = self.conf.getboolean('SETTING', 'night_mode')
        self.jpeg_quality = self.conf.getint('SETTING', 'jpeg_quality')
        self.output_image_size = [
            int(i.strip()) for i in self.conf.get('SETTING', 'output_image_size').split(',')
        ]
        self.mask_path = self.conf.get('SETTING', 'mask_path')
        self.cap_mod = self.conf.getint('SETTING', 'cap_mod')
        self.client_id = self.conf.get('SETTING', 'client_id')
        self.key = self.conf.get('SETTING', 'sha256_key')
        self.ntp_server = self.conf.get('SETTING', 'ntp_server')
        self.autonomous_mode = self.conf.getboolean('SETTING', 'autonomous_mode')
        self.light_sensor = self.conf.getboolean('SETTING', 'light_sensor')

        self.GSM_port = self.conf.get('GSM', 'port')
        self.GSM_phone_no = self.conf.get('GSM', 'phone_no')
        self.GSM_send_thumbnail = self.conf.getboolean('GSM', 'send_thumbnail')
        self.GSM_thumbnail_size = self.conf.getint('GSM', 'thumbnail_size')
        self.GSM_thumbnail_upload_server = self.conf.get('GSM', 'thumbnail_upload_server')
        self.thumbnailing_time_gap = self.conf.getint('GSM', 'thumbnail_upload_time_interval')
        self.GSM_time_sync = self.conf.getboolean('GSM', 'time_sync')
        self.GSM_send_log = self.conf.getboolean('GSM', 'send_log')
        self.GSM_log_upload_server = self.conf.get('GSM', 'log_upload_server')
        self.GSM_ppp_config_file = self.conf.get('GSM', 'ppp_config_file')

        self.MODBUS_port = self.conf.get('MODBUS', 'port')
        self.MODBUS_log_temperature = self.conf.getboolean('MODBUS', 'log_temperature')
        self.MODBUS_sensor_address = self.conf.getint('MODBUS', 'sensor_address')
        self.MODBUS_baudrate = self.conf.getint('MODBUS', 'baudrate')
        self.MODBUS_bytesize = self.conf.getint('MODBUS', 'bytesize')
        self.MODBUS_parity = self.conf.get('MODBUS', 'parity')
        self.MODBUS_stopbits = self.conf.getint('MODBUS', 'stopbits')
