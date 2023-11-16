import nidaqmx
import nipiezojenapy
from typing import List
import time
import logging

logger = logging.getLogger(__name__)
class VControl(nipiezojenapy.BaseControl):

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
        self._settling_time_in_seconds = move_settle_time #10 millisecond settle time
        self.last_write_value = None



    def go_to_voltage(self, v: float = None) -> None:
        '''
        !//Sets the x,y,z position in microns.

        //You do not need to specify all three axis values in order
        to move in one direction. For example, you can call: go_to_position(z = 40)

        raises ValueError if try to set position out of bounds.
        '''

        def goto(val):
            self._validate_value(val)
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(self.device_name + '/' + self.write_channel)
                task.write(self._microns_to_volts(val))
                self.last_write_value = val

        debug_string = []
        if v is not None:
            goto(v)
            debug_string.append(f'v: {v:.2f}')

        logger.info(f'go to position {" ".join(debug_string)}')

        time.sleep(self.settling_time_in_seconds) #wait to ensure piezo actuator has settled into position.
        logger.debug(f'last write: {self.last_write_value}')

    def get_current_voltage(self) -> List[float]:
        '''
        Returns the voltage supplied to the three input analog channels.

        If no input analog channels were provided when objected was created,
        returns [-1,-1,-1]
        '''
        output = [-1,-1,-1]
        if self.read_channel is not None:
            with nidaqmx.Task() as vread, nidaqmx.Task():

                vread.ai_channels.add_ai_voltage_chan(self.device_name + '/' + self.read_channel, min_val = 0, max_val = 10.0)

                output = vread.read()

        return output

    def get_current_voltage(self) -> List[float]:
        '''
        Returns the x,y,z position in microns

        If no input analog channels were provided when objected was created,
        returns the last requested position.
        '''

        if self.read_channel is None:
            return self.last_write_value

        else:
            return [self._volts_to_nm(v) for v in self.get_current_voltage()]

    @staticmethod
    def _nm_to_volts(self, nm: float) -> float:
        return nm / self.scale_nm_per_volt

    @staticmethod
    def _volts_to_nm(self, volts: float) -> float:
        return self.scale_nm_per_volt * volts
    @property
    def settling_time_in_seconds (self):
        return self._settling_time_in_seconds
    @settling_time_in_seconds.setter
    def settling_time_in_seconds (self, val):
        self._settling_time_in_seconds = val
