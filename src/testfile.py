#...
# Author: Barbara Stefanovska
#...

import datetime
import pandas as pd
import numpy as np
from copy import copy
#import LibrforPi as lp
import os
import multiprocessing
from urllib import request , response
import cv2
from time import sleep
import subprocess
import pause
import matplotlib.pyplot as plt
import LibrforPi as lfp

while (True):
    try:
        print('Testing function pause_time()')
        lfp.pause_time(18,20)

    except OSError:
        print('Nope')
        break


