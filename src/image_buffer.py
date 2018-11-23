#...
# Author: Barbara Stefanovska
#...
#This buffer contains a stack
#Which is ment to be used as temporary
#local storage for images (circa 5.1GB)
import Stack
buffer = Stack

def addImage(img):
    buffer.push(img)
