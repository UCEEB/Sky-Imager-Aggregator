import os
# Prepare image data
path = '/home/pi/Sky-Imager-Aggregator/STORAGE/'
files = os.listdir(path)
full_path = ["/home/pi/Sky-Imager-Aggregator/STORAGE/{0}".format(x) for x in files]
newest_file = max(full_path, key=os.path.getctime)
print(newest_file)
name = newest_file[39:56]
print(name)

