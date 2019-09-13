import socket
import picamera


# Run this code on RPi as server and view the stream via VLC as client
# Server and client should be on the same network
# On the client side, after running the code on RPi as server, open VLC,
# Go to Media/Open Network Stream and enter tcp/h264://RPiIPAddress:8000/
with picamera.PiCamera() as camera:
    camera.resolution = (640, 480)
    camera.framerate = 24

    server_socket = socket.socket()
    server_socket.bind(('0.0.0.0', 8000))
    server_socket.listen(0)

    connection = server_socket.accept()[0].makefile('wb')
    try:
        camera.start_recording(connection, format='h264')
        camera.wait_recording(60)
        camera.stop_recording()
    finally:
        connection.close()
        server_socket.close()
