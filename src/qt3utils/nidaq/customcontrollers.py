import abc
import logging
import nidaqmx
import numpy as np
import time

logger = logging.getLogger(__name__)


class WavelengthControlBase(abc.ABC):

    def __init__(self, device_name: str,
                 write_channel: str = 'ao0',
                 read_channel: str = None,
                 scale_nm_per_volt: float = 8,
                 move_settle_time: float = 0.001,
                 min_position: float = 0.0,
                 max_position: float = 80.0) -> None:
        super().__init__()

        self.device_name = device_name
        self.write_channel = write_channel
        self.read_channel = read_channel
        self.scale_nm_per_volt = scale_nm_per_volt
        self.minimum_allowed_position = min_position
        self.maximum_allowed_position = max_position
        self._settling_time_in_seconds = move_settle_time  # 10 millisecond settle time
        self.last_write_value = None
        self.speed = "fast"

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the data controller.
        """
        self.device_name = config_dict.get('daq_name', self.device_name)
        self.write_channel = config_dict.get('write_channels', self.write_channel)
        self.read_channel = config_dict.get('read_channels', self.read_channel)
        self.scale_nm_per_volt = config_dict.get('scale_nm_per_volt', self.scale_nm_per_volt)
        self.minimum_allowed_position = config_dict.get('min_position', self.minimum_allowed_position)
        self.maximum_allowed_position = config_dict.get('max_position', self.maximum_allowed_position)

    def get_current_wl_point(self) -> float:
        """
        Returns the voltage supplied to the three input analog channels.
        If no input analog channels were provided when objected was created,
        returns [-1,-1,-1]
        """
        output = -1
        if self.read_channel is not None:
            with nidaqmx.Task() as vread, nidaqmx.Task():
                vread.ai_channels.add_ai_voltage_chan(self.device_name + '/' + self.read_channel, min_val=0,
                                                      max_val=10.0)

                output = vread.read()

        return output

    def check_allowed_limits(self, v: float = None) -> None:
        if v is not None:
            self._validate_value(v)

    def _validate_value(self, voltage: float) -> None:
        voltage = float(voltage)
        if type(voltage) not in [type(1.0), type(1)]:
            raise TypeError(f'value {voltage} is not a valid type.')
        if voltage < self.minimum_allowed_position:
            raise ValueError(f'value {voltage} is less than {self.minimum_allowed_position: .3f}.')
        if voltage > self.maximum_allowed_position:
            raise ValueError(f'value {voltage} is greater than {self.maximum_allowed_position: .3f}.')

    @abc.abstractmethod
    def go_to(self, wl_point: float = None) -> None:
        """
        Sets the voltage
        raises ValueError if try to set voltage out of bounds.
        """
        pass

    @property
    def settling_time_in_seconds(self):
        return self._settling_time_in_seconds

    @settling_time_in_seconds.setter
    def settling_time_in_seconds(self, val):
        self._settling_time_in_seconds = val


class VControl(WavelengthControlBase):

    def go_to(self, wl_point: float = None) -> None:
        """
        Sets the voltage
        raises ValueError if try to set voltage out of bounds.
        """
        self.go_to_voltage(wl_point)

    def go_to_voltage(self, v: float = None) -> None:
        """
        !//Sets the voltage
        raises ValueError if try to set position out of bounds.
        """
        debug_string = []
        if v is not None:
            self._validate_value(v)
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(self.device_name + '/' + self.write_channel)
                task.write(self._nm_to_volts(nm=v))
                self.last_write_value = v
            debug_string.append(f'v: {v:.2f}')
        logger.info(f'go to voltage {" ".join(debug_string)}')
        time.sleep(self.settling_time_in_seconds)  # wait to ensure piezo actuator has settled into position.
        logger.debug(f'last write: {self.last_write_value}')

    def _nm_to_volts(self, nm: float) -> float:
        return nm / self.scale_nm_per_volt

    def _volts_to_nm(self, volts: float) -> float:
        return self.scale_nm_per_volt * volts


class VControlWavelength(WavelengthControlBase):

    def go_to(self, wl_point: float = None) -> None:
        """
        Sets the voltage
        raises ValueError if try to set voltage out of bounds.
        """
        if self.speed == "normal" or self.speed == "fast":
            self.go_to_voltage(wl_point)
        else:
            self.go_to_voltage_slowly(wl_point)

    def go_to_voltage(self, v: float = None) -> None:
        """
        !//Sets the voltage
        raises ValueError if try to set position out of bounds.
        """
        debug_string = []
        if v is not None:
            self._validate_value(v)
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(self.device_name + '/' + self.write_channel)
                task.write(v)
                self.last_write_value = v
            debug_string.append(f'v: {v:.2f}')
        logger.info(f'go to voltage {" ".join(debug_string)}')
        if not self.speed == "fast":
            time.sleep(self.settling_time_in_seconds)  # wait to ensure voltage has settled into position.
        logger.debug(f'last write: {self.last_write_value}')

    def go_to_voltage_slowly(self, v: float = None) -> None:
        debug_string = []
        step_size_slow = 0.2
        if v is not None:
            self._validate_value(v)
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(self.device_name + '/' + self.write_channel)
                while abs(v - self.last_write_value) > step_size_slow:
                    current_v = self.last_write_value + step_size_slow * np.sign(v - self.last_write_value)
                    task.write(current_v)
                    self.last_write_value = current_v
                    time.sleep(self.settling_time_in_seconds)
                task.write(v)
                self.last_write_value = v
            debug_string.append(f'v: {v:.2f}')
        logger.info(f'go to voltage {" ".join(debug_string)}')
        time.sleep(self.settling_time_in_seconds)  # wait to ensure piezo actuator has settled into position.
        logger.debug(f'last write: {self.last_write_value}')
