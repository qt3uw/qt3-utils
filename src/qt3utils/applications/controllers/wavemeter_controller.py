import abc
import ctypes
import logging


class WavemeterController(abc.ABC):
    """
    Base class for other types of wavemeter controllers to inherit from
    """
    def __init__(self, logger_level):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

    @abc.abstractmethod
    def open(self):
        """
        Override this method to open and initialize wavemeter
        """
        pass

    @abc.abstractmethod
    def read_wavemeter(self):
        """
        Override this method to read the value from the wavemeter
        """
        pass

    @abc.abstractmethod
    def close_wavemeter(self):
        """
        Override this method to close the connection to the wavemeter
        """
        pass

    @abc.abstractmethod
    def configure(self):
        """
        Override this method to configure the wavemeter from a dict set via yaml file
        """
        pass


class WavemeterDllController(WavemeterController):
    """
    Class for interfacing with wavemeter hardware
    """
    def __init__(self, logger_level, dll_path=""):
        super(WavemeterDllController, self).__init__(logger_level)
        if not dll_path == "":
            self.open(dll_path)
        self.dll_path = dll_path
        self.last_config_dict = {}

    def open(self, dll_path) -> None:
        """
        Set the path to the dll used for interfacing with the wavemeter
        """
        self._mydll = ctypes.cdll.LoadLibrary(dll_path)
        self._mydll.CLGetLambdaReading.restype = ctypes.c_double
        self._dh = self._mydll.CLOpenUSBSerialDevice(4)
        if self._dh == -1:
            raise Exception("Failed to connect to wave meter.")

    def read_wavemeter(self) -> float:
        """
        Return the value from the wavemeter via the dll
        """
        return self._mydll.CLGetLambdaReading(self._dh)

    def close_wavemeter(self) -> None:
        """
        Close the connection to the wavemeter via the dll
        """
        ending = self._mydll.CLCloseDevice(self._dh)
        if ending == -1:
            raise Exception("Failed to properly close connection to wave meter.")
        else:
            device_handle=None

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the data controller.
        """
        self.logger.debug("calling configure on the wave meter controller")
        self.dll_path = config_dict.get('dll_path', self.dll_path)
        self.open(self.dll_path)

