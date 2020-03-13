import configparser
from os.path import dirname
from os.path import join

conf = configparser.ConfigParser()
conf.read(join(dirname(dirname(__file__)), 'config.ini'))


class Config:
    """
    Hold the necessary configuration variables from config.ini file.
    """
    # authentication settings
    client_id = conf.get('Auth', 'client_id')
    key = conf.get('Auth', 'sha256_key')
    server = conf.get('Auth', 'upload_server')

    # camera settings
    cam_address = conf.get('Camera', 'cam_address')
    cam_username = conf.get('Camera', 'cam_username')
    cam_pwd = conf.get('Camera', 'cam_password')

    # Logging settings
    log_path = conf.get('Logging', 'log_path')
    lcd_display = conf.getboolean('Logging', 'lcd_display')
    log_to_console = conf.getboolean('Logging', 'log_to_console')

    # Storage settings
    storage_path = conf.get('Storage', 'storage_path')
    store_locally = conf.getboolean('Storage', 'local_storage')
    time_format = conf.get('Storage', 'filetime_format')

    # Location settings
    camera_latitude = conf.getfloat('Location', 'camera_latitude')
    camera_longitude = conf.getfloat('Location', 'camera_longitude')
    camera_altitude = conf.getfloat('Location', 'camera_altitude')

    # Time settings
    night_mode = conf.getboolean('Time', 'night_mode')
    ntp_server = conf.get('Time', 'ntp_server')
    cap_interval = conf.getint('Time', 'cap_interval')
    daytime_offset = conf.getint('Time', 'daytime_offset')

    # Image settings
    jpeg_quality = conf.getint('Image', 'jpeg_quality')
    image_size = [int(i.strip()) for i in conf.get('Image', 'image_size').split(',')]
    masking_enabled = conf.getboolean('Image', 'masking')
    mask_path = conf.get('Image', 'mask_image')
    cropping_enabled = conf.getboolean('Image', 'cropping')

    # Dashboard settings (InfluxDB connected to Grafana)
    dashboard_enabled = conf.getboolean('Dashboard', 'enabled')
    influxdb_host = conf.get('Dashboard', 'host')
    influxdb_port = conf.getint('Dashboard', 'port')
    influxdb_user = conf.get('Dashboard', 'user')
    influxdb_pwd = conf.get('Dashboard', 'password')
    influxdb_database = conf.get('Dashboard', 'database')
    influxdb_measurement = conf.get('Dashboard', 'measurement')

    # Irradiance sensor settings
    irr_sensor_enabled = conf.getboolean('Irradiance_sensor', 'enabled')
    irr_sensor_store = conf.getboolean('Irradiance_sensor', 'store_locally')
    irradiance_at_night = conf.getboolean('Irradiance_sensor', 'measure_at_night')
    irr_sensor_port = conf.get('Irradiance_sensor', 'port')
    irr_sensor_address = conf.getint('Irradiance_sensor', 'sensor_address')
    irr_sensor_baudrate = conf.getint('Irradiance_sensor', 'baudrate')
    irr_sensor_bytesize = conf.getint('Irradiance_sensor', 'bytesize')
    irr_sensor_parity = conf.get('Irradiance_sensor', 'parity')
    irr_sensor_stopbits = conf.getint('Irradiance_sensor', 'stopbits')

    # GSM settings
    gsm_enabled = conf.getboolean('GSM', 'enabled')
    gsm_port = conf.get('GSM', 'port')
    gsm_phone_no = conf.get('GSM', 'phone_no')
    gsm_ppp_config_file = conf.get('GSM', 'ppp_config_file')

    # Thumbnail settings
    thumbnail_enabled = conf.getboolean('Thumbnail', 'enabled')
    thumbnail_size = conf.getint('Thumbnail', 'thumbnail_size')
    thumbnail_upload_server = conf.get('Thumbnail', 'thumbnail_upload_server')
    thumbnail_interval = conf.getint('Thumbnail', 'thumbnail_interval')
