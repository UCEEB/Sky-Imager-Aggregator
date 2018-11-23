import json
from testlib import SALT_SYSTEM, SERVER, http, sha256, hmac_sha256
import base64, datetime
import os

###############################################################################
# Prepare image data
files = os.listdir('/home/pi/code/')
full_path = ["/home/pi/code/{0}".format(x) for x in files]
newest_file = max(full_path, key=os.path.getctime)

if newest_file.endswith('.jpg'):
    #base = newest_file
    #dateString = os.path.splitext(base)[0]
    skyimage = base64.b64encode(newest_file)
    dateString = datetime.datetime.now().strftime("%y-%m-%dT%H:%M:%S");

###############################################################################
# Set measured data

    id = 72
    key = "cuFo4Fx2PHQduNrE7TeKVFhVXXcyvHLufQZum0RkX8yGSK9naZptuvqz2zaHi1s0"

    data = {
        "status": "ok",
        "id": id,
        "time": dateString,
        "coding": "Base64",
        "data": skyimage
     }


    jsondata = json.dumps(data)
    signature = hmac_sha256(jsondata, key)

    url = "http://" + SERVER + "/api/aers/v1/upload.php?type=pic&signature={}".format(signature)

    response = http(url, jsondata)
          
    
    print (url)
    print data
    print (response)
    print ('--------------------------------------------------------------------------------')
    
###############################################################################