import nidaqmx
import time
import logging

logger = logging.getLogger(__name__)
class VControl():

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
        !//Sets the voltage
        raises ValueError if try to set position out of bounds.
        '''
        debug_string = []
        if v is not None:
            self._validate_value(v)
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(self.device_name + '/' + self.write_channel)
                task.write(self._nm_to_volts(nm=v))
                self.last_write_value = v
            debug_string.append(f'v: {v:.2f}')
        logger.info(f'go to voltage {" ".join(debug_string)}')
        time.sleep(self.settling_time_in_seconds) #wait to ensure piezo actuator has settled into position.
        logger.debug(f'last write: {self.last_write_value}')

    def get_current_voltage(self) -> float:
        '''
        Returns the voltage supplied to the three input analog channels.

        If no input analog channels were provided when objected was created,
        returns [-1,-1,-1]
        '''
        output = -1
        if self.read_channel is not None:
            with nidaqmx.Task() as vread, nidaqmx.Task():

                vread.ai_channels.add_ai_voltage_chan(self.device_name + '/' + self.read_channel, min_val=0, max_val=10.0)

                output = vread.read()

        return output

    def _nm_to_volts(self, nm: float) -> float:
        return nm / self.scale_nm_per_volt

    def _volts_to_nm(self, volts: float) -> float:
        return self.scale_nm_per_volt * volts
    @property
    def settling_time_in_seconds (self):
        return self._settling_time_in_seconds
    @settling_time_in_seconds.setter
    def settling_time_in_seconds (self, val):
        self._settling_time_in_seconds = val
