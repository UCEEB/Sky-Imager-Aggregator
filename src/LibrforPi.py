# Author: Barbara Stefanovska 
# ...
# This library includes all the functions needed for the RaspberryPi
import cv2
import numpy as np
import datetime
#import skimage
from copy import copy
import os
import shutil
import subprocess
from time import sleep
import http.client as httplib

path_src = '/home/pi/Sky-Imager-Aggregator/src'
path_storage = '/home/pi/Sky-Imager-Aggregator/STORAGE'

def maskImg(img):
    # OpenCV loads the images as multi-dimensional NumPy arrays but in reverse order: We need to convert BGR to RGB
    # The mask is previously created in matlab in the format bmp
    mask_int8 = cv2.imread("/home/pi/Sky-Imager-Aggregator/config/bwmask.bmp")
    #mask = skimage.img_as_float(mask)
    #img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mask = mask_int8/255
    final = copy(img)
    final[:, :, 0] = np.multiply(img[:, :, 0], mask[:, :, 0])
    final[:, :, 1] = np.multiply(img[:, :, 1], mask[:, :, 1])
    final[:, :, 2] = np.multiply(img[:, :, 2], mask[:, :, 2])
    return final


def nameimage():
    # Concatinates todays time and date to create an image name
    time = str(datetime.datetime.now())
    year = time[0:4]
    month = time[5:7]
    day = time[8:10]
    hour = time[11:13]
    minute = time[14:16]
    second = time[17:19]
    imagename = year[2:4]+ '-' + month + '-' + day+ '_' + hour + '-' + minute + '-' + second
    return imagename, int(hour), int(minute)


def suncycle_today2():
    # takes current date and searches for todays' sunrise and sunset time in the timetable
    # the timetable is previusly generated in matlab
##    time = str(datetime.datetime.now())
##    year = time[0:4]
##    day = time[8:10]
##    month = time[5:7]
##
##    month_tmp = int(month)
##    if month_tmp > 9:
##        today = year + ' ' + month + ' ' + day
##    else:
##        today = year + ' ' + month[1] + ' ' + day
##
##    sunriseset = '2019 1 1	5.062500  21.112505'
##    with open("Suncycle_timetable_2019.txt") as timetable:
##        for line in timetable:
##            flag = line.find(today)
##            if flag == 0:
##                sunriseset = copy(line)
##    if month_tmp > 9:
##        sunrise_tmp = sunriseset[11:15]
##        sunset_tmp = sunriseset[21:26]
##    else:
##        sunrise_tmp = sunriseset[10:14]
##        sunset_tmp = sunriseset[20:25]
##
##    sunrise_hour = sunrise_tmp[0]
##    sunrise_hour = int(sunrise_hour)
##
##    sunrise_min = int(int(sunrise_tmp[2:4]) * (6 / 10))
##    sunset_hour = sunset_tmp[0:2]
##    sunset_hour = int(sunset_hour)
##    sunset_min = int(int(sunset_tmp[3:5]) * (6 / 10))
##
##    timetable.close()
    #return sunrise_hour, sunrise_min, sunset_hour, sunset_min
    #TODO debuged to keep it running even inefeciently
    #Repair = make table versatile, not year dependent, eg. 12 values per year }month specific
    return 5, 0, 21, 15

def suncycle_today():
    # takes current date and searches for this months' sunrise and sunset time in the timetable
    # the timetable is previusly generated in matlab
    time = str(datetime.datetime.now())
    month = time[5:7]
    month_tmp = int(month)

    today_line = ' ' + month + 'M'

    sunriseset = '5.0 21.2'
    with open("Suncycle_timetable.txt") as timetable:
        for line in timetable:
            flag = line.find(today_line)
            if flag == 0:
                sunriseset = copy(line)

    sunrise_tmp = sunriseset[0:2]
    sunset_tmp = sunriseset[4:7]

    sunrise_hour = int(sunrise_tmp[0])
    sunrise_hour = int(sunrise_hour)
    sunrise_min = sunrise_hour * 6

    sunset_hour = int(sunset_tmp[0:1])
    sunset_hour = int(sunset_hour)
    sunset_min = sunset_hour * 6

    timetable.close()
    return sunrise_hour, sunrise_min, sunset_hour, sunset_min



def calculate_pause_time():
    sunriset = suncycle_today()
    print("sunriset from calculate pause time: ", sunriset)
    minute_temp = sunriset[3] - sunriset[1]
    hour_temp = 24 - sunriset[2] + sunriset[0]
    if minute_temp < 0:
        hour_temp -= 1
        minute_temp += 60
    sleeptime = (minute_temp*60) + hour_temp*3600 # Make sleeptime in seconds
    print(sleeptime)
    print('System will pause until sunrise for', hour_temp, 'hours and ',minute_temp, 'minutes')
    print('Sunrise is at:',sunriset[0],':',sunriset[1],'am')
    return sleeptime

def pause_time(hour, minute):
    sunriseset = suncycle_today()
    sleeptime = 0
    flag = 1
    if hour == sunriseset[2]:
        if minute >= sunriseset[3]:
            sleeptime = calculate_pause_time()
            print('System paused.')
            print(abs(sleeptime))
            sleep(sleeptime)
            print('Restarting program!')
            print("Sunriseset: ",sunriseset)
            print('Sunrise time: ', sunriseset[0], ':', sunriseset[1])
            print('...................')

    return


def store_image(img):
    flag = 1  # return flag = 0 when image is stored
    # Neeeds to be updated
    image_name ,hr , mnt= nameimage()
    image_name = str(image_name)+'.jpg'
    image = cv2.imwrite(os.path.join(os.path.expanduser('~'),path_storage, image_name), img=img)

    flag = 0

    return flag

def stack_storage():

    files = os.listdir(path_storage)
    full_path = ["/home/pi/code/Sky-Imager-Aggregator/STORAGE/{0}".format(x) for x in files]
    if len([name for name in files]) == 8400:
        oldest_file = min(full_path, key=os.path.getctime)
        os.remove(oldest_file)
        return


def check_storage_content():
    flag = 10
    path_storage
    if os.listdir(path_storage) == []:
        flag = 0
    else:
        flag = 1
    return flag


def empty_storage_content():
    shutil.rmtree(path_storage)
    os.mkdir(path_storage)
    return


def take_photo(imgResp):
    # NOT USED!!! DON'T USE!!!
    imgNp = np.array(bytearray(imgResp.read()), dtype=np.uint8)
    img = cv2.imdecode(imgNp, -1)
    # NOTE: Image might need converting: img = cv2.cvtColor(img, COLOR_BGR2RGB)
    return img


def send_storage_content():

    #subprocess.call(['python pic2.py server']) # pic2.py is a version of pic.py that sends the whole storage
    # Starting from the most recent photo until there are no more photos
    #p = os.popen("python pic2.py server")
    #print(p.read())
    
    return


def time_for_storage(hour,minute):
    sunriseset = suncycle_today()
    if hour == sunriseset[2] :
        if minute >= sunriseset[3]:
            return True    
        else:
            return False
        
        
def delete_image():

    for file in os.listdir(path_src):
        if file.endswith('.jpg'):
            os.remove(file)

    return


def check_connectivity():

    conn = httplib.HTTPConnection("www.google.com", timeout=2)
    try:
        conn.request("HEAD", "/")
        conn.close()
        return True
    except:
        conn.close()
        return False
