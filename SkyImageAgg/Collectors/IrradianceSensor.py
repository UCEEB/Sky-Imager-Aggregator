import os
import time

import minimalmodbus


class IrrSensor(minimalmodbus.Instrument):
    """
    Class for communicating with the irradiance sensor through Modbus protocol.
    """
    def __init__(self, port, address, baudrate, bytesize, parity, stopbits):
        """
        Construct a sensor object.

        Parameters
        ----------
        port : str
            port that the sensor is connected to.
        address : int
            modbus address
        baudrate : int
            modbus baudrate
        bytesize : int
        parity : str
            modbus pairity
        stopbits : int
            modbus stopbits
        """
        super().__init__(port=port, slaveaddress=address)
        self.serial.baudrate = baudrate
        self.serial.bytesize = bytesize
        self.serial.parity = parity
        self.serial.stopbits = stopbits
        self.serial.rtscts = False
        self.serial.dsrdtr = True
        self.serial.timeout = 0.1

    def open_serial(self):
        """
        checks if the serial port is already open, if not open it.
        """
        if not self.serial.isOpen():
            self.serial.open()

    def get_data(self):
        """
        Get required data from sensor,
        """
        self.open_serial()

        irr = self.read_register(0, 1, 4, False)
        ext_temp = self.read_register(8, 1, 4, True)
        cell_temp = self.read_register(7, 1, 4, True)

        self.serial.close()
        return irr, ext_temp, cell_temp

    @staticmethod
    def restart_USB2Serial():
        """
        Restart the USB port that the modbus is connected to.
        """
        time.sleep(0.5)
        os.system('sudo modprobe -r pl2303')
        time.sleep(0.2)
        os.system('sudo modprobe -r usbserial')
        time.sleep(0.2)
        os.system('sudo modprobe pl2303')
        time.sleep(0.5)
