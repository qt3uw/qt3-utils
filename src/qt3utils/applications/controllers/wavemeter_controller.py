import ctypes
import logging

class WavemeterController:
    """
    Class for interfacing with wavemeter hardware
    """
    def __init__(self, dll_path=""):
        self.logger = logging.getLogger(__name__)
        if not dll_path == "":
            self.init_dll(dll_path)
        self.dll_path = dll_path
        self.last_config_dict = {}

    def init_dll(self, dll_path) -> None:
        """
        Set the path to the dll used for interfacing with the wavemeter
        """
        self._mydll = ctypes.cdll.LoadLibrary(dll_path)
        self._mydll.CLGetLambdaReading.restype = ctypes.c_double
        self._dh = self._mydll.CLOpenUSBSerialDevice(4)
        if self._dh == -1:
            raise Exception("Failed to connect to wave meter.")

    def read_wavemeter(self) -> float:
        return self._mydll.CLGetLambdaReading(self._dh)

    def close_wavemeter(self) -> None:
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
        #self.last_config_dict.update(config_dict)

        self.dll_path = config_dict.get('dll_path', self.dll_path)
        self.init_dll(self.dll_path)

