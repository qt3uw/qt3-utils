import abc

from src.qt3utils.devices.devices import MessageBasedDevice, AcquisitionMixin
from src.qt3utils.devices.utils import MessageBasedResourceType


class MessageBasedOpticalPowerMeter(MessageBasedDevice, AcquisitionMixin, abc.ABC):

    DEVICE_PY_ALIAS = 'Message-Based Optical Power Meter'

    def __init__(self, mediator: MessageBasedResourceType):
        super(MessageBasedDevice).__init__(mediator)
        super(AcquisitionMixin).__init__()

    def disconnect(self):
        self.stop_time_series_acquisition(force_stop=True)
        super().disconnect()  # Refers to Device-inherited class.


class Newport2835C(MessageBasedOpticalPowerMeter):

    DEVICE_PY_ALIAS = 'Newport 2835-C'
    IDN_PART = 'NewportCorp,2835-C'

    def __new__(cls, *args, **kwargs):  # Default creation via default IDN_PART
        return cls.from_idn(cls.IDN_PART, True)

    def __init__(self, mediator: MessageBasedResourceType):
        super().__init__(mediator)

    def setup_acquisition(self, acquisition_sleep_time: float = None, acquisition_slow_sleep_time: float = None):
        pass

    def single_acquisition(self) -> list:
        pass

