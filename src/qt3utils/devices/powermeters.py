import abc
from enum import Enum

from src.qt3utils.devices.devices import MessageBasedDevice, AcquisitionMixin
from src.qt3utils.devices.utils import MessageBasedResourceType


class MessageBasedOpticalPowerMeter(MessageBasedDevice, AcquisitionMixin, abc.ABC):

    DEVICE_PY_ALIAS = 'Message-Based Optical Power Meter'

    def __init__(
            self,
            mediator: MessageBasedResourceType,
            post_communication_delay: float = MessageBasedDevice.DEFAULT_POST_COMMUNICATION_DELAY,
    ):
        super(MessageBasedDevice).__init__(mediator, post_communication_delay)
        super(AcquisitionMixin).__init__()

    def disconnect(self):
        self.stop_time_series_acquisition(force_stop=True)
        super().disconnect()  # Refers to Device-inherited class.


class Newport2835C(MessageBasedOpticalPowerMeter):
    # TODO: check manual chapter 2.4.7 for DC sampling settings!

    DEFAULT_QUERY_DELAY = 10 ** -4  # 0.02 s instead? worked best with dummy testing
    DEFAULT_POST_COMMUNICATION_DELAY = 10 ** -4  # TODO: test and see what works best

    DEVICE_PY_ALIAS = 'Newport 2835-C'
    DEFAULT_IDN_PART = 'NewportCorp,2835-C'

    MINIMUM_ACQ_SLEEP_TIME = 0.002  # s

    CHANNELS = ['A', 'B', '']  # Empty string means both channels.
    CHANNEL_TO_CHANNEL_BASED_COMMAND = {'A': '_A', 'B': '_B', '': ''}

    READ_POWER_BASE_COMMAND = 'R'

    class SamplePrecisionFrequencyLimits:
        MIN_20000_CNT = 0.001  # Hz
        MAX_20000_CNT = 25  # Hz

        # Use when channel connections are not known.
        # See more on device manual, chapter 2.4.7 on DC sampling settings.
        MIN_4096_CNT = 0.001  # Hz
        MAX_4096_CNT = 500  # Hz

        MIN_4096_CNT_SINGLE = 0.001  # Hz
        MAX_4096_CNT_SINGLE = 1000  # Hz

        MIN_4096_CNT_DUAL = 0.001  # Hz
        MAX_4096_CNT_DUAL = 500  # Hz

    class SamplePrecisionStates(Enum):
        HighAccuracy = 20000  # counts
        LowAccuracy = 4096  # counts

    # define sample precision freq and state input standards

    def __new__(cls, *args, **kwargs):  # Default creation via default DEFAULT_IDN_PART
        return cls.from_idn(cls.DEFAULT_IDN_PART, True, *args, **kwargs)

    def __init__(
            self, mediator: MessageBasedResourceType,
            post_communication_delay: float = DEFAULT_POST_COMMUNICATION_DELAY
    ):
        super().__init__(mediator, post_communication_delay)
        self.channel: str = ''

    def setup_acquisition(
            self,
            acquisition_sleep_time: float = None,
            acquisition_slow_sleep_time: float = None,
            channel: list[str] = None,
            units: str = None,
            sample_precision_frequency: float = None,
            sample_precision_accuracy: int = None,
            auto_range: bool = None,
            wavelength: float = None,
    ):
        super().setup_acquisition(acquisition_sleep_time, acquisition_slow_sleep_time)
        if channel is not None:
            if channel not in self.CHANNELS:
                raise ValueError(f'Invalid channel: {channel}')  # TODO: change
            self.channel = channel  # check with available channels "CH?"

    def single_acquisition(self) -> list:
        pass

    def get_channel_based_command(self, command_str: str) -> str:
        return command_str + self.CHANNEL_TO_CHANNEL_BASED_COMMAND[self.channel]

