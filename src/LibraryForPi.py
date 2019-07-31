## LibraryForPi
# @package   SendStorageV2
# @details   Script sends the images that for some reason were not sent on time.
# @version   3.0
# @author   Jan Havrlant and Barbara Stefanovska
#


import base64
import csv
import hashlib
import hmac
import json
import requests
import os
import cv2
import logging
import socket
import numpy as np
import datetime as dt
from astral import Astral, Location


def apply_mask(image, path_to_mask):
    mask = cv2.imread(path_to_mask) / 255

    return np.multiply(mask, image)


def apply_custom_processing(image, config):
    if len(config.private_lib_name) > 0:
        script_name = config.private_lib_name
        script_name_without_ext = os.path.splitext(script_name)[0]
        custom_script = __import__(script_name_without_ext)
        result = custom_script.process_image(image)
        return result

    return image


def hmac_sha256(message, key):
    return hmac.new(key, bytes(message, 'ascii'), digestmod=hashlib.sha256).hexdigest()


def send_post_request(url, data):
    post_data = {
        'data': data
    }

    return requests.post(url, data=post_data)


def upload_json(image, file_time, config):
    sky_image = base64.b64encode(image).decode('ascii')
    date_string = file_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    id = config.id
    key = config.key
    server = config.server

    data = {
        'status': 'ok',
        'id': id,
        'time': date_string,
        'coding': 'Base64',
        'data': sky_image
    }
    json_data = json.dumps(data)
    signature = hmac_sha256(json_data, key)

    url = server + signature

    response = send_post_request(url, json_data)
    try:
        json_response = json.loads(response.text)
    except Exception as e:
        raise Exception(response)

    if json_response['status'] != 'ok':
        raise Exception(json_response['message'])
    return json_response


def upload_bson(image, file_time, server, config):
    date_string = file_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    id = config.id
    key = config.key

    data = {
        "status": "ok",
        "id": id,
        "time": date_string,
        "coding": "none"
    }
    jsondata = json.dumps(data)
    signature = hmac_sha256(jsondata, key)

    if isinstance(image, str) or isinstance(image, bytes):
        files = [('image', image), ('json', jsondata)]
    else:
        files = [('image', str(image)), ('json', jsondata)]

    response = requests.post(server + signature, files = files)
    try:
        json_response = json.loads(response.text)
    except Exception as e:
        raise Exception(response)

    if json_response['status'] != 'ok':
        raise Exception(json_response['message'])
    return json_response


def get_sunrise_and_sunset_date(camera_latitude, camera_longitude, camera_altitude,
                                date=dt.datetime.now(dt.timezone.utc).date()):
    astral = Astral()
    astral.solar_depression = 'civil'
    location = Location(('custom', 'region', camera_latitude, camera_longitude, 'UTC', camera_altitude))

    try:
        sun = location.sun(date=date)
    except:
        return dt.datetime.combine(date, dt.time(3, 0, 0, 0, dt.timezone.utc)), \
               dt.datetime.combine(date, dt.time(21, 0, 0, 0, dt.timezone.utc))

    return sun['sunrise'], sun['sunset']


def get_path_to_storage(config):
    path = config.path_storage
    if config.autonomous_mode:
        if os.access(config.GSM_path_storage_usb1, os.W_OK):
            path = config.GSM_path_storage_usb1
        elif os.access(config.GSM_path_storage_usb2, os.W_OK):
            path = config.GSM_path_storage_usb2
    return path


def save_to_storage(img, config, name, logger, image_time):
    path = get_path_to_storage(config) + '/' + image_time.strftime("%y-%m-%d")
    if not os.path.exists(path):
        os.makedirs(path)
    if config.autonomous_mode:
        try:
            img.tofile(path + '/' + name)
        except Exception as e:
            logger.error('Saving to local storage error : ' + str(e))
        else:
            logger.info('image ' + path + '/' + name + ' saved to storage')
            return

    try:
        img.tofile(config.path_storage + '/' + name)
    except Exception as e:
        logger.error('save to local storage error : ' + str(e))
    else:
        logger.info('image ' + config.path_storage + '/' + name + ' saved to storage')


def get_freespace_storage(conf):
    path = get_path_to_storage(conf)
    info = os.statvfs(path)
    freespace = info.f_bsize * info.f_bfree / 1048576
    return '%.0f MB' % freespace


def set_logger(log_level):
    logger = logging.getLogger('main_logger')
    console_logger = logging.StreamHandler()
    logger.addHandler(console_logger)  # logging to console
    logger.setLevel(log_level)
    logger.info("Running program...")
    return logger, console_logger


def set_log_to_file(log_path, log_to_console, logger, console_logger):
    try:
        hdlr = logging.FileHandler(log_path + '/' + str(dt.date.today()) + '.log')
        hdlr.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(hdlr)
    except Exception as e:
        logger.error('log file error : ' + str(e))
        return

    if not log_to_console:
        logger.removeHandler(console_logger)  # disable console logging
    return hdlr


def set_log_to_file_new_day(log_path, logger, handler):
    logger.removeHandler(handler)
    try:
        handler = logging.FileHandler(log_path + '/' + str(dt.date.today()) + '.log')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
    except Exception as e:
        logger.error('log file error : ' + str(e))
    return handler


# todo check function
def save_irradiance_csv(conf, time, irradiance, ext_temperature, cell_temperature, logger):
    path = get_path_to_storage(conf)
    try:
        f = open(path + '/' + conf.MODBUS_csv_name, 'a', newline='')
        csvFile = csv.writer(f, delimiter=';', quotechar='\'', quoting=csv.QUOTE_MINIMAL)
        if conf.MODBUS_log_temperature:
            csvFile.writerow([time, irradiance, ext_temperature, cell_temperature])
        else:
            csvFile.writerow([time, irradiance])
        f.close()
    except Exception as e:
        logger.error('csv save to local storage error : ' + str(e))
    else:
        logger.debug('csv row saved in' + path + '/' + conf.MODBUS_csv_name)
        logger.info('irradiance saved ' + str(irradiance))


def test_internet_connection(logger, host="8.8.8.8", port=53, timeout=3):
    """
    Host: 8.8.8.8 (google-public-dns-a.google.com)
    OpenPort: 53/tcp
    Service: domain (DNS/TCP)
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception as e:
        logger.error('no internet connection : ' + str(e))
        return False
