import json
from testlib import SALT_SYSTEM, SERVER, http, sha256, hmac_sha256
import base64, datetime
import os

###############################################################################
# Prepare image data
path = '/home/pi/Sky-Imager-Aggregator/src/'
files = os.listdir(path)
full_path = ["/home/pi/Sky-Imager-Aggregator/src/{0}".format(x) for x in files]
newest_file = max(full_path, key=os.path.getctime)
print(newest_file)
if newest_file.endswith('.jpg'):
    with open(newest_file[14:35],"rb") as f:
        skyimage = base64.b64encode(f.read())

#dateString = datetime.datetime.now().strftime("%y-%m-%dT%H:%M:%S+02:00");
name = str(newest_file[14:31])
dateString = name[0:8] + 'T' + name[9:11] + ':' + name[12:14] + ':' + name[15:17] + '+02:00'

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
          
    
print(url)
#print data
print(response)
print('--------------------------------------------------------------------------------')
    
###############################################################################
