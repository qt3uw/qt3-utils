import logging
import nidaqmx
import time

logger = logging.getLogger(__name__)

class VControl():
    """
    Class for interfacing with DAQ hardware with the express purpose of
    controlling and/or reading the voltage at the DAQ that sets the wavelength of a laser
    """

    def __init__(self,
                 logger_level,
                 device_name: str = "",
                 write_channel: str = 'ao0',
                 read_channel: str = None,
                 scale_nm_per_volt: float = 8,
                 move_settle_time: float = 0.001,
                 min_voltage: float = 0.0,
                 max_voltage: float = 80.0) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.device_name = device_name
        self.write_channel = write_channel
        self.read_channel = read_channel
        self.scale_nm_per_volt = scale_nm_per_volt
        self.minimum_allowed_voltage = min_voltage
        self.maximum_allowed_voltage = max_voltage
        self._settling_time_in_seconds = move_settle_time  # 10 millisecond settle time
        self.last_write_value = None



    def go_to(self, wl_point: float = None) -> None:
        '''
        Sets the voltage
        raises ValueError if try to set voltage out of bounds.
        '''
        voltage = wl_point
        debug_string = []
        if voltage is not None:
            self._validate_value(voltage)
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(f"{self.device_name}/{self.write_channel}")
                task.write(self._nm_to_volts(nm=voltage))
                self.last_write_value = voltage
            debug_string.append(f'voltage: {voltage:.2f}')
        logger.info(f'go to voltage {" ".join(debug_string)}')
        time.sleep(self.settling_time_in_seconds)  # wait to ensure piezo actuator has settled into voltage.
        logger.debug(f'last write: {self.last_write_value}')

    def get_current_wl_point(self) -> float:
        '''
        Returns the voltage supplied to the three input analog channels.
        If no input analog channels were provided when objected was created,
        returns none
        '''
        output = None
        if self.read_channel is not None:
            with nidaqmx.Task() as vread, nidaqmx.Task():
                vread.ai_channels.add_ai_voltage_chan(f"{self.device_name}/{self.read_channel}")
                output = vread.read()
        return output

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the data controller.
        """
        self.device_name = config_dict.get('daq_name', self.device_name)
        self.write_channel = config_dict.get('write_channels', self.write_channel)
        self.read_channel = config_dict.get('read_channels', self.read_channel)
        self.scale_nm_per_volt = config_dict.get('scale_nm_per_volt', self.scale_nm_per_volt)
        self.minimum_allowed_voltage = config_dict.get('min_voltage', self.minimum_allowed_voltage)
        self.maximum_allowed_voltage = config_dict.get('max_voltage', self.maximum_allowed_voltage)

    def check_allowed_limits(self, voltage: float = None) -> None:
        if voltage is not None: self._validate_value(voltage)

    def _validate_value(self, voltage: float) -> None:
        voltage = float(voltage)
        if not isinstance(voltage, (float, int)):
            raise TypeError(f'value {voltage} is not a valid type.')
        if voltage < self.minimum_allowed_voltage:
            raise ValueError(f'value {voltage} is less than {self.minimum_allowed_voltage: .3f}.')
        if voltage > self.maximum_allowed_voltage:
            raise ValueError(f'value {voltage} is greater than {self.maximum_allowed_voltage: .3f}.')
    def _nm_to_volts(self, nm: float) -> float:
        return nm / self.scale_nm_per_volt

    def _volts_to_nm(self, volts: float) -> float:
        return self.scale_nm_per_volt * volts

    @property
    def settling_time_in_seconds (self):
        return self._settling_time_in_seconds
    @settling_time_in_seconds.setter
    def settling_time_in_seconds (self, value):
        self._settling_time_in_seconds = value
