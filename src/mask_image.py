#...
# Author: Barbara Stefanovska
#...

from cv2 import imread, cvtColor,COLOR_BGR2RGB
import numpy as np
import matplotlib.pyplot as plt
from skimage import img_as_float
from copy import copy

def maskImg(img):
    img = imread("20180604105950_12.jpg")
    #OpenCV loads the images as multi-dimensional NumPy arrays but in reverse order: We need to convert BGR to RGB
    imgRGB = cvtColor(img, COLOR_BGR2RGB)
    #The mask is previously created in matlab
    mask = imread("bwmask.bmp")
    mask= img_as_float(mask) #might not need this

    final = copy(img)
    final[:,:,0] = np.multiply(imgRGB[:,:,0], mask[:,:,0])
    final[:,:,1] = np.multiply(imgRGB[:,:,1], mask[:,:,0])
    final[:,:,2] = np.multiply(imgRGB[:,:,2], mask[:,:,0])

    plt.imshow(final)
    plt.show()

    return final