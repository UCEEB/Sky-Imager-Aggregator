import os
import time

from Configuration import Configuration
import minimalmodbus


class SIAIrradiance:

    def __init__(self, logger):
        self.logger = logger

    def _get_data_from_sensor(self, port, address, baudrate, bytesize, parity, stopbits):
        instrument = minimalmodbus.Instrument(port, address)

        if not instrument.serial.isOpen():
            instrument.serial.open()

        instrument.serial.baudrate = baudrate
        instrument.serial.bytesize = bytesize
        instrument.serial.parity = parity
        instrument.serial.stopbits = stopbits
        instrument.serial.rtscts = False
        instrument.serial.dsrdtr = True
        instrument.serial.timeout = 0.1

        try:
            irradiance = instrument.read_register(0, 1, 4, False)
            ext_temperature = instrument.read_register(8, 1, 4, True)
            cell_temperature = instrument.read_register(7, 1, 4, True)
        except Exception as e:
            instrument.serial.close()
            raise Exception(e)
        instrument.serial.close()
        return irradiance, ext_temperature, cell_temperature

    def get_irradiance_data(self, port, address, baudrate, bytesize, parity, stopbits):
        counter = 0
        while True:
            try:
                irradiance, ext_temperature, cell_temperature = self._get_data_from_sensor(
                    port, address, baudrate, bytesize, parity, stopbits)
            except Exception as e:
                self.logger.debug('Irradiance error: ' + str(e))
                if counter == 3:
                    self.logger.debug('Restarting USBSerial')
                    SIAIrradiance._restart_USB2Serial()
                elif counter > 5:
                    raise Exception(e)
            else:
                self.logger.debug('Irradiance OK')
                return irradiance, ext_temperature, cell_temperature
            counter += 1
            time.sleep(0.1)

    @staticmethod
    def _restart_USB2Serial():
        time.sleep(0.5)
        os.system('sudo modprobe -r pl2303')
        time.sleep(0.2)
        os.system('sudo modprobe -r usbserial')
        time.sleep(0.2)
        os.system('sudo modprobe pl2303')
        time.sleep(0.5)