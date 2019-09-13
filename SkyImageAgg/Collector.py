import os
import time

from picamera import PiCamera
import minimalmodbus


class RPiCam:
    def __init__(self):
        self.cam = PiCamera()

    def start_preview(self):
        self.cam.start_preview()

    def stop_preview(self):
        self.cam.stop_preview()

    # todo check
    def cap_pic(self, image):
        self.cam.capture(image)

    def cap_video(self):
        pass


class IrrSensor:
    def __init__(self, port, address, baudrate, bytesize, parity, stopbits):
        self.sensor = minimalmodbus.Instrument(port, address)
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits

    def setup(self):
        self.sensor.serial.baudrate = self.baudrate
        self.sensor.serial.bytesize = self.bytesize
        self.sensor.serial.parity = self.parity
        self.sensor.serial.stopbits = self.stopbits
        self.sensor.serial.rtscts = False
        self.sensor.serial.dsrdtr = True
        self.sensor.serial.timeout = 0.1

    def open_serial(self):
        if not self.sensor.serial.isOpen():
            self.sensor.serial.open()

    def get_data(self):
        self.open_serial()
        try:
            irr = self.sensor.read_register(0, 1, 4, False)
            ext_temp = self.sensor.read_register(8, 1, 4, True)
            cell_temp = self.sensor.read_register(7, 1, 4, True)
        except Exception as e:
            self.sensor.serial.close()
            raise Exception(e)
        self.sensor.serial.close()
        return irr, ext_temp, cell_temp

    @staticmethod
    def restart_USB2Serial():
        time.sleep(0.5)
        os.system('sudo modprobe -r pl2303')
        time.sleep(0.2)
        os.system('sudo modprobe -r usbserial')
        time.sleep(0.2)
        os.system('sudo modprobe pl2303')
        time.sleep(0.5)
