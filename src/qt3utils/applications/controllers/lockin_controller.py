import numpy as np

import nidaqmx

class Lockin:
    def __init__(self, device_name: str, signal_channel: str, timeout: float) -> None:
        self.device_name = device_name
        self.signal_channel = signal_channel
        self.sample_number = 20
        self.rate = 20.0
        self.timeout = timeout

    def read(self) -> np.ndarray:
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(self.device_name + '/' + self.signal_channel, max_val=10)
            task.timing.cfg_samp_clk_timing(rate=self.rate, samps_per_chan=self.sample_number)
            c = task.read(number_of_samples_per_channel=self.sample_number, timeout=self.timeout)
        return np.array(c)

def configure(self, config_dict: dict) -> None:
    """
    This method is used to configure the data controller.
    """
    self.device_name = config_dict.get('daq_name', self.device_name)
    self.signal_channel = config_dict.get('signal_channels', self.signal_channel)
    self.sample_number = config_dict.get('sample_number', self.sample_number)
    self.rate = config_dict.get('rate', self.rate)
    self.timeout = config_dict.get('timeout', self.timeout)
