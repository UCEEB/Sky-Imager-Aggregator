import os
import time

import minimalmodbus


class IrrSensor:
    """

    """

    def __init__(self, port, address, baudrate, bytesize, parity, stopbits):
        self.sensor = minimalmodbus.Instrument(port, address)
        self.sensor.serial.baudrate = baudrate
        self.sensor.serial.bytesize = bytesize
        self.sensor.serial.parity = parity
        self.sensor.serial.stopbits = stopbits
        self.sensor.serial.rtscts = False
        self.sensor.serial.dsrdtr = True
        self.sensor.serial.timeout = 0.1

    def open_serial(self):
        """

        """
        if not self.sensor.serial.isOpen():
            self.sensor.serial.open()

    def get_data(self):
        """

        Returns
        -------

        """
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
        """

        """
        time.sleep(0.5)
        os.system('sudo modprobe -r pl2303')
        time.sleep(0.2)
        os.system('sudo modprobe -r usbserial')
        time.sleep(0.2)
        os.system('sudo modprobe pl2303')
        time.sleep(0.5)
