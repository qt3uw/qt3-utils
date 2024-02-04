import ctypes

class WavemeterController
    def __init__(self, dll_path):
        self._mydll = ctypes.cdll.LoadLibrary(dll_path)
        self._mydll.CLGetLambdaReading.restype = ctypes.c_double
        self._dh = self._mydll.CLOpenUSBSerialDevice(4)
        if self._dh == -1:
            raise Exception("Failed to connect to wave meter.")

    def read_wavemeter(self):
        return self._mydll.CLGetLambdaReading(self._dh)

    def close_wavemeter(self) -> None:
        ending = self._mydll.CLCloseDevice(self._dh)
        if ending == -1:
            raise Exception("Failed to properly close connection to wave meter.")
        else:
            device_handle=None

