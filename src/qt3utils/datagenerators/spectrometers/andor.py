import logging
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Union, Set

import numpy as np

from datagenerators.spectrometers.spectrometer import SpectrometerConfig, SpectrometerDataAcquisition


class AndorAPI:
    """
    A class for interfacing with the Andor API.

    This class can only be instantiated once.
    This is important because we should only allow
    the user to access the Andor API from a single place.
    Allowing the user to access the Andor API from multiple objects
    can result in communication errors with the device.
    The most important problem would be two objects trying to access
    the device at the same time. This is prevented by the use of a
    `threading.RLock`.

    Attributes
    ----------
    logger: logging.Logger
        The logger object related to the Andor API object.
    """

    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        logger_name = self.__class__.__name__
        self.logger = logging.getLogger(logger_name)

        self._ccd_import_succeeded, self._spg_import_succeeded = self._import_libraries()
        self._lock = threading.RLock()

    def __getattribute__(self, item):
        """
        Assures the user is properly notified that calling the object's attribute failed
        because the Andor packages were not properly imported.

        Raises
        ------
        AttributeError
            when either or both pyAndorSDK2 and pyAndorSpectrograph were not properly imported.
        """
        if self._ccd_import_succeeded and self._spg_import_succeeded:
            return super().__getattribute__(item)

        if not self._ccd_import_succeeded and not self._spg_import_succeeded:
            failed_imports = "pyAndorSDK2 and pyAndorSpectrograph"
        elif not self._ccd_import_succeeded:
            failed_imports = "pyAndorSDK2"
        else:
            failed_imports = "pyAndorSpectrograph"

        self.logger.error(f"Importing {failed_imports} was not successful, hence, {item} was not properly defined.")
        raise AttributeError(f'{failed_imports} were not found to properly define {item}.')

    def _import_libraries(self):
        """
        Imports and instantiates the required libraries
        (pyAndorSDK2.atmcd and pyAndorSpectrograph.ATSpectrograph)
        for the Andor Spectrometer.

        Returns
        -------
        bool
            True if the import was successful, False otherwise.
        """
        try:
            from pyAndorSDK2 import atmcd, atmcd_errors, atmcd_capabilities, atmcd_codes
            self._ccd = atmcd()
            self._ccd_error_codes = atmcd_errors.Error_Codes
            self._ccd_capabilities = atmcd_capabilities
            self._ccd_codes = atmcd_codes
        except ImportError:
            self._ccd = None
            self._ccd_error_codes = None
            self._ccd_capabilities = None
            self._ccd_codes = None
            self.logger.error('pyAndorSDK2 is not installed.')

        try:
            from pyAndorSpectrograph import ATSpectrograph
            self._spectrograph = ATSpectrograph()
        except ImportError:
            self._spectrograph = None
            self.logger.error('pyAndorSpectrograph is not installed.')

        return self._ccd is not None, self._spectrograph is not None

    @property
    def lock(self) -> threading.RLock:
        """
        The lock object used to prevent multiple threads from accessing the Andor API.

        Returns
        -------
        threading.RLock
            The lock object used to prevent multiple threads from accessing the Andor API.
        """
        return self._lock

    @property
    def is_locked(self) -> bool:
        """
        Checks if the spectrometer is locked (used by current or other threads).

        Returns
        -------
        bool
            True if the spectrometer is locked, False otherwise.
        """
        return _andor_api.lock._is_owned()

    def log_ccd_response(self, task: str, error_code: int, logger: logging.Logger = None):
        if logger is None:
            logger = self.logger

        if error_code == self.ccd_error_codes.DRV_SUCCESS:
            logger.debug(f"{task} was successful")
        else:
            logger.warning(f"{task} failed with return code {repr(self.ccd_error_codes(error_code))}")

    def log_spg_response(self, task: str, error_code: int, logger: logging.Logger = None):
        if logger is None:
            logger = self.logger

        if error_code == self.spg.ATSPECTROGRAPH_SUCCESS:
            logger.debug(f"{task} was successful")
        else:
            code_description = self.spg.GetFunctionReturnDescription(error_code, 200)
            logger.warning(f"{task} failed with return code {code_description}")

    @property
    def ccd(self):
        """
        The pyAndorSDK2.atmcd.atmcd object for the Andor API.

        Returns
        -------
        pyAndorSDK2.atmcd.atmcd
            The pyAndorSDK2.atmcd.atmcd object for the Andor API.
        """
        return self._ccd

    @property
    def ccd_codes(self):
        """
        The pyAndorSDK2.atmcd_codes module for the Andor API.

        Returns
        -------
        pyAndorSDK2.atmcd_codes
            The pyAndorSDK2.atmcd_codes module for the Andor API.
        """
        return self._ccd_codes

    @property
    def ccd_error_codes(self):
        """
        The pyAndorSDK2.atmcd_errors.Error_Codes() enumerator for the Andor API.

        Returns
        -------
        pyAndorSDK2.atmcd_errors.Error_Codes()
            The pyAndorSDK2.atmcd_errors.Error_Codes enumerator for the Andor API.
        """
        return self._ccd_error_codes

    @property
    def ccd_capabilities(self):
        """
        The pyAndorSDK2.atmcd_capabilities object for the Andor API.

        Returns
        -------
        pyAndorSDK2.atmcd_capabilities
            The pyAndorSDK2.atmcd_capabilities object for the Andor API.
        """
        return self._ccd_capabilities

    @property
    def spectrograph(self):
        """
        The pyAndorSpectrograph.ATSpectrograph object for the Andor API.

        Returns
        -------
        pyAndorSpectrograph.ATSpectrograph
            The pyAndorSpectrograph.ATSpectrograph object for the Andor API.
        """
        return self._spectrograph

    @property
    def spg(self):
        """
        The pyAndorSpectrograph.ATSpectrograph object for the Andor API.

        Returns
        -------
        pyAndorSpectrograph.ATSpectrograph
            The pyAndorSpectrograph.ATSpectrograph object for the Andor API.
        """
        return self._spectrograph

    def is_ccd_initialized(self) -> bool:
        """
        Checks if the CCD is initialized.

        Returns
        -------
        bool
            True if the CCD is initialized, False otherwise.
        """
        with _andor_api.lock:
            status, _, _ = self.ccd.GetDetector()
        return status == self.ccd_error_codes.DRV_SUCCESS

    def is_spg_initialized(self) -> bool:
        """
        Checks if the Spectrograph is initialized.

        Returns
        -------
        bool
            True if the Spectrograph is initialized, False otherwise.
        """
        with _andor_api.lock:
            status, _ = self.spg.GetNumberDevices()
        return status == self.spg.ATSPECTROGRAPH_SUCCESS


_andor_api = AndorAPI()
""" The singleton instantiation of the AndorAPI. """


@dataclass
class GratingInfo:
    device_index: int
    grating_index: int

    lines: float = field(init=False)
    blaze: str = field(init=False)
    home: int = field(init=False)
    offset: int = field(init=False)

    MAX_BLAZE_STRING_LENGTH: int = 50

    def __post_init__(self):
        self._get_info()

    def _get_info(self):
        with _andor_api.lock:
            status, self.lines, self.blaze, self.home, self.offset = _andor_api.spg.GetGratingInfo(
                self.device_index, self.grating_index, self.MAX_BLAZE_STRING_LENGTH)
        _andor_api.log_spg_response(f"Getting grating information for device '{self.device_index}'"
                                    f" and grating '{self.grating_index}'", status)

    def short_description(self) -> str:
        return f"{self.grating_index}: {self.lines:.1f}, {self.blaze}"


@dataclass
class SpectrographInfo:
    device_index: int
    number_of_gratings: int = field(init=False)
    grating_index_list: List[int] = field(init=False)
    grating_info_dictionary: Dict[int, GratingInfo] = field(init=False)

    def __post_init__(self):
        self._get_number_of_gratings()
        self.grating_index_list = list(range(1, self.number_of_gratings + 1))
        self._get_grating_info_dictionary()

    def __getitem__(self, item) -> GratingInfo:
        return self.grating_info_dictionary[item]

    def _get_number_of_gratings(self):
        with _andor_api.lock:
            status, self.number_of_gratings = _andor_api.spg.GetNumberGratings(self.device_index)
        _andor_api.log_spg_response(f"Getting number of gratings for spectrograph device '{self.device_index}'", status)

    def _get_grating_info_dictionary(self):
        self.grating_info_dictionary = {
            grating_index: GratingInfo(self.device_index, grating_index)
            for grating_index in self.grating_index_list
        }


@dataclass
class CCDInfo:
    ccd_index: int

    number_of_pixels_horizontally: int = field(init=False)
    number_of_pixels_vertically: int = field(init=False)
    pixel_width: float = field(init=False)
    pixel_height: float = field(init=False)

    def __post_init__(self):
        self._get_number_of_pixels()
        self._get_pixel_size()

    def _get_pixel_size(self):
        with _andor_api.lock:
            status, self.pixel_width, self.pixel_height = _andor_api.ccd.GetPixelSize()
        _andor_api.log_ccd_response("Getting pixel size", status)

    def _get_number_of_pixels(self):
        with _andor_api.lock:
            status, self.number_of_pixels_horizontally, self.number_of_pixels_vertically = _andor_api.ccd.GetDetector()
        _andor_api.log_ccd_response("Getting number of pixels", status)


class AndorSpectrometerConfig(SpectrometerConfig):
    """
    Configuration class for the Andor Spectrometer.

    This class controls all the spectrometer settings prior to data acquisition.
    For controlling the data acquisition, refer to the `AndorSpectrometerDataAcquisition` class.

    """

    DEVICE_NAME: str = 'Andor Spectrometer'

    def __init__(self, spg_device_index: int = 0):
        super().__init__()
        self._spg_device_index = spg_device_index

        with _andor_api.lock:
            self._spg_number_of_devices = _andor_api.spg.GetNumberDevices()
            self._ccd_number_of_devices = _andor_api.ccd.GetNumberDevices()

        self._spg_device_list = list(range(self._spg_number_of_devices))
        self._ccd_device_list = list(range(self._ccd_number_of_devices))

        self._spg_info: Union[SpectrographInfo, None] = None
        self._ccd_info: Union[CCDInfo, None] = None

    def open(self) -> None:
        """
        Initializes the connection to the CCD and the spectrograph.
        """
        with _andor_api.lock:
            self._open_ccd()
            self._open_spg()

    def _open_ccd(self):
        """
        Initializes the connection to the CCD and turns on the cooler.
        """
        with _andor_api.lock:
            if not _andor_api.is_ccd_initialized():
                status = _andor_api.ccd.Initialize("")
                _andor_api.log_ccd_response('CCD initialization', status)
                status = _andor_api.ccd.CoolerON()
                _andor_api.log_ccd_response('CCD cooler turn-on', status)
            else:
                _andor_api.logger.debug('CCD is already initialized.')

            self._ccd_info = CCDInfo(self.ccd_device_index)

    def _open_spg(self):
        """
        Initializes the connection to the spectrograph.
        """
        with _andor_api.lock:
            if not _andor_api.is_spg_initialized():
                status = _andor_api.spg.Initialize("")
                _andor_api.log_spg_response('Spectrograph initialization', status)
            else:
                _andor_api.logger.debug('Spectrograph is already initialized.')

            self._spg_info = SpectrographInfo(self.spg_device_index)

    def close(self) -> None:
        """
        Terminates connection to the spectrograph and CCD.

        Warnings
        --------
        The CCD cooler has to turn off to terminate the connection to the CCD.
        """
        with _andor_api.lock:
            self._close_spg()
            self._close_ccd()

    def _close_ccd(self):
        """
        Terminates connection to the CCD.

        Warnings
        --------
        The CCD cooler has to turn off to terminate the connection to the CCD.
        """
        with _andor_api.lock:
            if _andor_api.is_ccd_initialized():
                status = _andor_api.ccd.CoolerOFF()
                _andor_api.log_spg_response('CCD cooler turn-off', status)

                status = _andor_api.ccd.ShutDown()
                _andor_api.log_spg_response('CCD shutdown', status)
            else:
                _andor_api.logger.warning('CCD is already closed')

            self._ccd_info = None

    def _close_spg(self):
        """
        Terminates connection to the spectrograph.
        """
        with _andor_api.lock:
            if _andor_api.is_spg_initialized():
                status = _andor_api.spg.Close()
                _andor_api.log_spg_response('Spectrograph shutdown', status)
            else:
                _andor_api.logger.warning('Spectrograph is already shutdown')

            self._spg_info = None

    @property
    def ccd_number_of_devices(self) -> int:
        """ The total number of connected CCDs to the computer. """
        return self._ccd_number_of_devices

    @property
    def ccd_device_list(self) -> List[int]:
        """ An index list of all available CCDs."""
        return self._ccd_device_list

    @property
    def ccd_info(self):
        return self._ccd_info

    @property
    def ccd_device_index(self) -> int:
        """ The index corresponding to the selected CCD device. """
        with _andor_api.lock:
            status, ccd_device_index = _andor_api.ccd.GetCurrentCamera()
        _andor_api.log_ccd_response('Getting current camera', status)
        return ccd_device_index

    @ccd_device_index.setter
    def ccd_device_index(self, value: int):
        """ To change the current CCD, we need to close the connection with the previous CCD first. """
        if value == self.ccd_device_index:
            return

        if value in self.ccd_device_list:
            was_initialized = _andor_api.is_ccd_initialized()
            if was_initialized:
                self._close_ccd()
                _andor_api.ccd.SetCurrentCamera(value)
                self._open_ccd()
        else:
            _andor_api.logger.warning(
                f"CCD device index '{value}' is not in the device index list {self.ccd_device_list}. "
                f"CCD device index remains as is: {self.ccd_device_index}"
            )

    @property
    def spg_number_of_devices(self) -> int:
        """ The total number of connected Spectrometers to the computer. """
        return self._spg_number_of_devices

    @property
    def spg_device_list(self) -> List[int]:
        """ An index list of all available Spectrographs. """
        return self._spg_device_list

    @property
    def spg_info(self):
        return self._spg_info

    @property
    def spg_device_index(self) -> int:
        """ The index corresponding to the selected spectrometer device. """
        return self._spg_device_index

    @spg_device_index.setter
    def spg_device_index(self, value: int):
        if value == self.spg_device_index:
            return

        if value in self.spg_device_list:
            self._spg_device_index = value
        else:
            _andor_api.logger.warning(
                f"Spectrograph device index '{value}' is not in the device index list {self.spg_device_list}. "
                f"Spectrograph device index remains as is: {self.spg_device_index}"
            )

    @property
    def number_of_gratings(self) -> int:
        """
        The number of gratings installed on the current spectrograph device.
        """
        return self.spg_info.number_of_gratings

    @property
    def grating_index_list(self) -> List[int]:
        """
        An index list of all installed gratings on the current spectrograph device.
        """
        return self.spg_info.grating_index_list

    @property
    def grating_list(self) -> List[str]:
        """
        A list of all installed gratings on the current spectrograph device.
        """
        grating_info_values: List[GratingInfo] = list(self.spg_info.grating_info_dictionary.values())

        return [gi.short_description() for gi in grating_info_values]

    @property
    def current_grating(self) -> str:
        """
        Current spectrometer grating.
        """
        with _andor_api.lock:
            status, current_grating = _andor_api.spg.GetGrating(self.spg_device_index)
        _andor_api.log_spg_response("Getting current grating", status)
        return current_grating

    @current_grating.setter
    def current_grating(self, value: int) -> None:
        """
        Set the spectrometer grating.
        """
        with _andor_api.lock:
            status = _andor_api.spg.SetGrating(self.spg_device_index, value)
        _andor_api.log_spg_response("Setting current grating", status)

    @property
    def center_wavelength(self) -> float:
        """
        The grating center wavelength.
        """
        with _andor_api.lock:
            status, center_wavelength = _andor_api.spg.GetWavelength(self.spg_device_index)
        _andor_api.log_spg_response("Getting center wavelength", status)
        return center_wavelength

    @center_wavelength.setter
    def center_wavelength(self, nanometers: float) -> None:
        """
        Sets the grating center wavelength.
        """
        with _andor_api.lock:
            status = _andor_api.spg.SetWavelength(self.spg_device_index, nanometers)
        _andor_api.log_spg_response("Setting center wavelength", status)

    @property
    def starting_wavelength(self) -> float:
        """
        The Step and Glue starting wavelength.
        """
        pass

    @starting_wavelength.setter
    def starting_wavelength(self, lambda_min: float) -> None:
        """
        Sets the Step and Glue starting wavelength.
        """
        pass

    @property
    def ending_wavelength(self) -> float:
        """
        The Step and Glue ending wavelength.
        """
        pass

    @ending_wavelength.setter
    def ending_wavelength(self, lambda_max: float) -> None:
        """
        Sets the Step and Glue ending wavelength.
        """
        pass

    @property
    def get_wavelength_calibration_parameters(self) -> List[float]:
        """
        Returns the wavelength calibration for a single frame.
        """
        with _andor_api.lock:
            status, a, b, c, d = _andor_api.spg.GetPixelCalibrationCoefficients(self.spg_device_index)
        _andor_api.log_spg_response("Getting wavelength calibration parameters", status)
        return [a, b, c, d]

    def get_wavelengths(self) -> np.ndarray:
        """
        Returns the wavelength calibration for a single frame.
        """
        pass

    @property
    def sensor_temperature_set_point(self) -> float:
        """
        The sensor set-point temperature in Celsius.
        """
        with _andor_api.lock:
            status, temperature = _andor_api.ccd.GetTemperature()
        _andor_api.log_ccd_response("Getting CCD temperature", status)
        return temperature

    @sensor_temperature_set_point.setter
    def sensor_temperature_set_point(self, deg_celsius: float) -> None:
        """
        Sets the sensor target temperature in Celsius.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetTemperature(deg_celsius)
        _andor_api.log_ccd_response("Setting CCD temperature", status)

    @property
    def exposure_time(self) -> float:
        """
        Returns the single frame exposure time (in seconds).
        """
        # TODO: check out which method I need to use, or if I can decide which method
        #  to use after querying the active mode.
        # with _andor_api.lock:
        #     status, exposure_time = _andor_sdk.ccd.GetAcquisitionTimings()
        return np.nan

    @exposure_time.setter
    def exposure_time(self, secs: float) -> None:
        """
        Sets the single frame exposure time in seconds.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetExposureTime(secs)
        _andor_api.log_ccd_response("Setting exposure time", status)

    def __del__(self):
        self.close()


class AndorSpectrometerDataAcquisition(SpectrometerDataAcquisition):
    DEVICE_NAME: str = 'Andor Spectrometer'

    ACQUISITION_MODES: Set[str] = {'single', 'kinetic series', 'accumulation'}

    # def setup_acquisition(self, mode):
    #     pass

    def stop_acquisition(self):
        """
        Stop the current acquisition.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.AbortAcquisition()
        _andor_api.log_ccd_response("Aborting acquisition", status)
