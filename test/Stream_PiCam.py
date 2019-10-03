import socket

from io import BytesIO
from time import sleep
from picamera import PiCamera
from PIL import Image
import numpy as np
import cv2

# Run this code on RPi as server and view the stream via VLC as client
# Server and client should be on the same network
# On the client side, after running the code on RPi as server, open VLC,
# Go to Media/Open Network Stream and enter tcp/h264://RPiIPAddress:8000/
def stream():
    with PiCamera(resolution=(1920, 1080), framerate=24) as camera:
        server_socket = socket.socket()
        server_socket.bind(('0.0.0.0', 8003))
        server_socket.listen(0)

        connection = server_socket.accept()[0].makefile('wb')
        try:
            camera.start_recording(connection, format='h264')
            camera.wait_recording(60)
            camera.stop_recording()
        finally:
            connection.close()
            server_socket.close()


def cap_as_object():
    # Create the in-memory stream
    stream = BytesIO()
    camera = PiCamera()
    camera.start_preview()
    sleep(2)
    camera.capture(stream, format='jpeg')
    # "Rewind" the stream to the beginning so we can read its content
    stream.seek(0)
    return cv2.imdecode(np.frombuffer(stream.read(), np.uint8), -1)


if __name__ == '__main__':
    stream()
