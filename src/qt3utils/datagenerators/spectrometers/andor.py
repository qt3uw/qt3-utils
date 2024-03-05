import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import List, Dict, Union, Set, Callable, Any, Tuple, Literal

import numpy as np

from qt3utils.datagenerators.spectrometers.spectrometer import SpectrometerConfig, SpectrometerDataAcquisition


def prevent_none_set(func: Callable[[Any, Any], None]) -> Union[Callable[[Any, Any], None], None]:
    """
    A decorator that prevents the wrapped method from running if the input argument is None.

    This decorator targets property setters that take a single input argument.
    It will allow the user to configure the spectrometer via a yaml file without
    resetting any properties they want to keep unchanged during controller
    initialization.

    Parameters
    ----------
    func: Callable[[Any, Any], None]
        The property setter to be decorated.
        The first argument is self, the second is new value.

    Returns
    -------
    Union[Callable[[Any, Any], None], None]
        None if the given argument was None, the original method otherwise.
    """

    def wrapper(self, value):
        if value is None:
            return
        try:
            if np.isnan(value):
                return
        except TypeError:
            pass
        return func(self, value)
    return wrapper


class AndorAPI(object):
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
        logger_name = self.__class__.__name__
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        self.logger = logger

        self._ccd_import_succeeded, self._spg_import_succeeded = self._import_libraries()
        self._lock = threading.RLock()

    def __getattribute__(self, item: str):
        """
        Assures the user is properly notified that calling the object's attribute failed
        because the Andor packages were not properly imported.

        Raises
        ------
        AttributeError
            when either or both pyAndorSDK2 and pyAndorSpectrograph were not properly imported.
        """
        if item.startswith('_'):
            return super().__getattribute__(item)

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
            logger.warning(f"{task} failed with return code '{repr(self.ccd_error_codes(error_code))[1:-1]}'")

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
        pyAndorSDK2.atmcd_errors.Error_Codes
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
    """
    A dataclass to hold information for a single grating.
    The information this class holds are the ones that should
    not be changed after the proper installation of the grating.

    The grating can be found with a spectrograph `device_index`
    and a `grating_index`.
    Some intrinsic characteristics of the grating Andor stores
    are the number of `lines` in grooves/mm, and the `blaze`
    wavelength, usually derived by the groove angle.

    When a user installs a grating on a turret, they must calibrate
    the relevant position of the grating on the turret.
    By setting the `home` and `offset` parameters, the spectrograph
    can calculate how to position the grating when trying to go to a
    specific central wavelength.
    """
    device_index: int
    grating_index: int

    lines: float = field(init=False)
    blaze: str = field(init=False)
    home: int = field(init=False)
    offset: int = field(init=False)

    MAX_BLAZE_STRING_LENGTH: int = field(init=False, default=50, repr=False, compare=False)

    def __post_init__(self):
        self._get_info()

    def _get_info(self):
        """
        Retrieves the grating information via the Andor API.
        Stores the information in the corresponding dataclass fields.
        """
        with _andor_api.lock:
            status, self.lines, self.blaze, self.home, self.offset = _andor_api.spg.GetGratingInfo(
                self.device_index, self.grating_index, self.MAX_BLAZE_STRING_LENGTH)
        _andor_api.log_spg_response(f"Getting grating information for device '{self.device_index}'"
                                    f" and grating '{self.grating_index}'", status)

    @property
    def short_description(self) -> str:
        """
        A short description of the grating.
        Includes the grating index, number of grooves and the blaze wavelength.
        """
        return f"{self.grating_index}: {self.lines:.1f}, {self.blaze}"


@dataclass
class SpectrographInfo:
    """
    A dataclass to hold information for a specific spectrograph
    (since multiple may be connected to a single computer at once).
    The information this class holds are the ones that should
    not be changed after the proper installation of the grating
    turret and the rest of the spectrometer components.

    The spectrometer can be found with a give `device_index`, which
    is the handle integer Andor API gives to the spectrograph.
    This class holds information regarding gratings.
    """
    device_index: int
    number_of_gratings: int = field(init=False)
    grating_index_list: List[int] = field(init=False)
    grating_info_dictionary: Dict[int, GratingInfo] = field(init=False)

    def __post_init__(self):
        self._get_number_of_gratings()
        self.grating_index_list = list(range(1, self.number_of_gratings + 1))
        self._get_grating_info_dictionary()

    def _get_number_of_gratings(self):
        """
        Retrieves the number of gratings installed
        in the spectrometer turret via the Andor API.
        """
        with _andor_api.lock:
            status, self.number_of_gratings = _andor_api.spg.GetNumberGratings(self.device_index)
        _andor_api.log_spg_response(f"Getting number of gratings for "
                                    f"spectrograph device '{self.device_index}'", status)

    def _get_grating_info_dictionary(self):
        """
        Retrieves information regarding all the
        installed gratings via the Andor API.
        """
        self.grating_info_dictionary = {
            grating_index: GratingInfo(self.device_index, grating_index)
            for grating_index in self.grating_index_list
        }


@dataclass
class CCDInfo:
    """
    A dataclass to hold information for a specific CCD
    (since multiple may be connected to a single computer at once).
    The information this class holds are the ones that should
    not be changed after the proper installation of the CCD
    and the rest of the spectrometer components.

    The CCD can be found with a given `device_index`, which
    is the handle integer Andor API gives to the CCD.
    This class holds information regarding the CCD's pixel
    size and number.
    """
    ccd_index: int

    number_of_pixels_horizontally: int = field(init=False)
    number_of_pixels_vertically: int = field(init=False)
    pixel_width: float = field(init=False)
    pixel_height: float = field(init=False)

    number_of_vertical_shift_speeds: int = field(init=False)
    available_vertical_shift_speeds: List[float] = field(init=False)
    fastest_recommended_vertical_shift_speed: Tuple[int, float] = field(init=False)

    number_of_ad_channels: int = field(init=False)
    number_of_output_amplifiers: int = field(init=False)
    number_of_horizontal_shift_speeds: Dict[Tuple[int, int], int] = field(init=False)  # (A/D Ch, Amp): no_hss
    available_horizontal_shift_speeds: Dict[Tuple[int, int], List[float]] = field(init=False)  # (A/D, Amp): [hss1, ...]

    number_of_pre_amp_gains: int = field(init=False)
    available_pre_amp_gains: List[float] = field(init=False)

    MAX_PRE_AMP_GAIN_STRING_LENGTH: int = field(init=False, default=10, repr=False, compare=False)

    def __post_init__(self):
        self._get_number_of_pixels()
        self._get_pixel_size()
        self._get_vertical_shift_speed_info()
        self._get_horizontal_shift_speed_info()
        self._get_pre_amp_info()

    def _get_pixel_size(self):
        """
        Retrieves the width and height of each pixel on
        the CCD via the Andor API.
        """
        with _andor_api.lock:
            status, self.pixel_width, self.pixel_height = _andor_api.ccd.GetPixelSize()
        _andor_api.log_ccd_response("Getting pixel size", status)

    def _get_number_of_pixels(self):
        """
        Retrieving the number of pixels in the horizontal
        and vertical axis of the CCD via the Andor API.
        """
        with _andor_api.lock:
            status, self.number_of_pixels_horizontally, self.number_of_pixels_vertically = _andor_api.ccd.GetDetector()
        _andor_api.log_ccd_response("Getting number of pixels", status)

    def _get_vertical_shift_speed_info(self):
        """
        Retrieves information regarding the vertical
        shift speeds (total number and values)
        available on the CCD via the Andor API.
        """
        with _andor_api.lock:
            status, self.number_of_vertical_shift_speeds = _andor_api.ccd.GetNumberVSSpeeds()
            _andor_api.log_ccd_response("Getting number of vertical shift speeds", status)

            self.available_vertical_shift_speeds = [
                np.round(_andor_api.ccd.GetVSSpeed(i)[1], 1)
                for i in range(self.number_of_vertical_shift_speeds)
            ]

            status, *self.fastest_recommended_vertical_shift_speed = _andor_api.ccd.GetFastestRecommendedVSSpeed()
            _andor_api.log_ccd_response("Getting fastest recommended vertical shift speed", status)

    def _get_horizontal_shift_speed_info(self):
        """
        Retrieves information regarding the horizontal
        shift speeds (number of A/D Channels, output
        amplifiers, and horizontal speeds, and values)
        available on the CCD via the Andor API.
        """
        with _andor_api.lock:
            status, self.number_of_ad_channels = _andor_api.ccd.GetNumberADChannels()
            _andor_api.log_ccd_response("Getting number of AD channels", status)

            status, self.number_of_output_amplifiers = _andor_api.ccd.GetNumberAmp()
            _andor_api.log_ccd_response("Getting number of amplifiers", status)

            self.number_of_horizontal_shift_speeds = {}
            self.available_horizontal_shift_speeds = {}
            for ch in range(self.number_of_ad_channels):
                for amp in range(self.number_of_output_amplifiers):
                    number_of_hss = _andor_api.ccd.GetNumberHSSpeeds(ch, amp)[1]
                    self.number_of_horizontal_shift_speeds[(ch, amp)] = number_of_hss
                    self.available_horizontal_shift_speeds[(ch, amp)] = [
                        _andor_api.ccd.GetHSSpeed(ch, amp, hss_idx)[1]
                        for hss_idx in range(number_of_hss)
                    ]

    def _get_pre_amp_info(self):
        """
        Retrieves information regarding the pre-amplification
        gains (total number and values)
        available on the CCD via the Andor API.
        """
        with _andor_api.lock:
            status, self.number_of_pre_amp_gains = _andor_api.ccd.GetNumberPreAmpGains()
            _andor_api.log_ccd_response("Getting number of pre-amplification gains", status)

            self.available_pre_amp_gains = [
                _andor_api.ccd.GetPreAmpGain(i)[1]
                for i in range(self.number_of_pre_amp_gains)
            ]


class ImmutableClass:
    """
    A class whose attributes cannot be changed once defined.
    """

    def __setattr__(self, key, value):
        """
        This method is called whenever an attribute is set.
        It raises an `AttributeError` to prevent the user from
        changing the attributes of this class.
        This is to prevent the user from changing the parameters
        of the single track read mode outside the spectrometer
        configuration class.
        """
        if hasattr(self, key):
            raise AttributeError(f"{self.__class__.__name__!r} objects are immutable.")
        super().__setattr__(key, value)


@dataclass
class SingleTrackReadModeParameters(ImmutableClass):
    """
    A dataclass to hold parameters for the single track read mode.
    """
    track_center_row: int
    track_height: int


class AndorSpectrometerConfig(SpectrometerConfig):
    """
    Configuration class for the Andor Spectrometer.

    This class controls all the spectrometer settings
    prior to data acquisition.
    For controlling the data acquisition, refer to the
    `AndorSpectrometerDataAcquisition` class.

    Notes
    -----
    Curiously, while the spectrograph device number
    does not need to be set prior to the spectrograph
    initialization, the CCD device number does.
    Hence, the spectrograph device can be changed without
    reinitializing the devices (you can access all of them
    at once) but the CCD does.

    Since you usually have one spectrograph and one CCD
    that go together, this class follows the CCD
    initialization logic.
    This means we only manipulate a single spectrograph
    at any given time, determined via the `spg_device_index`
    attribute.
    """

    DEVICE_NAME: str = 'Andor Spectrometer'

    class SpectrographFlipperMirrorPort(enum.IntEnum):
        DIRECT = _andor_api.spg.DIRECT
        SIDE = _andor_api.spg.SIDE

    class ReadMode(enum.IntEnum):
        FVB = 0
        MULTI_TRACK = 1
        RANDOM_TRACK = 2
        SINGLE_TRACK = 3
        IMAGE = 4

    AcquisitionMode = _andor_api.ccd_codes.Acquisition_Mode
    TriggerMode = _andor_api.ccd_codes.Trigger_Mode

    SUPPORTED_READ_MODES: Tuple[str, ...] = (ReadMode.FVB.name, ReadMode.SINGLE_TRACK.name)
    """
    These modes represent all the read modes this class supports right now. 
    If you want to limit the supported modes in your application, change 
    the tuple of supported modes before initializing the CCD.
    """
    SUPPORTED_ACQUISITION_MODES: Tuple[str, ...] = (
        AcquisitionMode.SINGLE_SCAN.name,
        AcquisitionMode.ACCUMULATE.name,
        AcquisitionMode.KINETICS.name,
        AcquisitionMode.RUN_TILL_ABORT.name
    )
    """
    These modes represent all the acquisition modes this class supports right now. 
    If you want to limit the supported modes in your application, change 
    the tuple of supported modes before initializing the CCD.
    """
    SUPPORTED_TRIGGER_MODES: Tuple[str, ...] = (TriggerMode.INTERNAL.name, TriggerMode.EXTERNAL.name)
    """
    These modes represent all the trigger modes this class supports right now. 
    If you want to limit the supported modes in your application, change 
    the tuple of supported modes before initializing the CCD.
    """

    DEFAULT_READ_MODE: str = ReadMode.FVB.name
    """
    There is no getter for read mode in the Andor API, so we choose full vertical
    binning (FVB) as the default value. Feel free to change the default value prior
    to initialization, or the actual read mode value after initialization.
    """
    DEFAULT_ACQUISITION_MODE: str = AcquisitionMode.SINGLE_SCAN.name
    """
    There is no getter for acquisition mode in the Andor API, so we choose single
    scan as the default value. Feel free to change the default value prior to
    initialization, or the actual acquisition mode value after initialization.
    """
    DEFAULT_TRIGGER_MODE: str = TriggerMode.INTERNAL.name
    """
    There is no getter for trigger mode in the Andor API, so we choose internal
    as the default value. Feel free to change the default value prior to 
    initialization, or the actual trigger mode value after initialization.
    """

    DEFAULT_SINGLE_TRACK_READ_MODE_PARAMETERS = SingleTrackReadModeParameters(128, 256)
    """
    There is no getter for single track read mode parameters in the Andor API,
    so we choose the default value. Feel free to change the default value
    prior to initialization, or the actual single track read mode parameters
    value after initialization.
    """

    DEFAULT_NUMBER_OF_ACCUMULATIONS: int = 2
    """
    There is no getter for number of accumulations in the Andor API, 
    so to initialize the spectrometer configuration we use a default value. 
    """
    DEFAULT_NUMBER_OF_KINETICS: int = 1
    """
    There is no getter for number of kinetics in the Andor API,
    so to initialize the spectrometer configuration we use a default value.
    """
    DEFAULT_COOLER_PERSISTENCE_MODE: bool = True
    """
    There is no getter for cooler mode in the Andor API, so to initialize
    the spectrometer configuration we use a default value.
    """
    DEFAULT_SET_TEMPERATURE: int = -70
    """
    Some times the CCD does not remember the target temperature that was set with
    the Andor Solis software. We use this value to ensure the temperature stays
    low when we first initialize the CCD when the user has not set a preferred 
    temperature yet.
    """
    DEFAULT_SPG_DEVICE_INDEX: int = 0
    """
    The default spectrograph device index is 0.
    If you have more than one spectrograph connected to the computer,
    you can either change the default value to the index of the spectrograph,
    or change the `spg_device_index` attribute after initialization of the 
    AndorSpectrometerConfig object.
    """
    DEFAULT_VERTICAL_SHIFT_SPEED_INDEX: int = -1
    """
    If the default vertical shift speed index is -1, then the vertical shift will
    be set to the fastest recommended speed by the software. 
    If you want to change the vertical shift speed, change the default value
    to the index of the vertical shift speed you want.
    Alternatively, change it after the CCD is initialized.
    """
    DEFAULT_PRE_AMP_GAIN_INDEX: int = 0
    """
    The default pre-amplification gain index is 0, which is the lowest possible vaue.
    If you want to change the pre-amplification gain, change the default value
    to the index of the pre-amplification gain you want.
    Alternatively, change it after the CCD is initialized.
    """
    DEFAULT_AD_CHANNEL: int = 0
    """
    The default A/D channel is first available channel.
    Some CCDs support multiples.
    """
    DEFAULT_OUTPUT_AMPLIFIER: int = 0
    """
    The default output amplifier is first available amplifier.
    Some CCDs support multiples.
    """
    DEFAULT_HORIZONTAL_SHIFT_SPEED_INDEX: int = -1
    """
    The default horizontal shift speed index is -1, which is the lowest possible value.
    """
    DEFAULT_HORIZONTAL_BIN_SIZE: int = 1
    """
    The default horizontal bin size is 1 (no change in output data length if 1).
    """
    DEFAULT_KEEP_CLEAN_ON_EXTERNAL_TRIGGER: bool = True
    """
    Keeps cleaning CCD while it's waiting for an external trigger.
    """

    def __init__(self):
        super().__init__()

        # We can get the number of available cameras prior to initializing the CCD, but not for the spectrograph.
        self._spg_number_of_devices: int = 0
        with _andor_api.lock:
            status, self._ccd_number_of_devices = _andor_api.ccd.GetAvailableCameras()
        _andor_api.log_ccd_response("Getting number of CCD devices", status)

        self._spg_info: Union[SpectrographInfo, None] = None
        self._ccd_info: Union[CCDInfo, None] = None

        # Setting all the internal-use attributes for attributes that
        # do not have a Getter method implemented in the Andor API

        self._spg_device_index: int = self.DEFAULT_SPG_DEVICE_INDEX

        self._pixel_offset: float = 0.
        self._wavelength_offset: float = 0.

        self._read_mode: str = self.DEFAULT_READ_MODE
        self._acquisition_mode: str = self.DEFAULT_ACQUISITION_MODE
        self._trigger_mode: str = self.DEFAULT_TRIGGER_MODE

        self._number_of_accumulations: int = self.DEFAULT_NUMBER_OF_ACCUMULATIONS
        self._number_of_kinetics: int = self.DEFAULT_NUMBER_OF_KINETICS
        self._remove_cosmic_rays: Union[bool, None] = None

        self._horizontal_bin_size: int = self.DEFAULT_HORIZONTAL_BIN_SIZE
        self._keep_clean_on_external_trigger: bool = self.DEFAULT_KEEP_CLEAN_ON_EXTERNAL_TRIGGER
        self._single_track_read_mode_parameters = self.DEFAULT_SINGLE_TRACK_READ_MODE_PARAMETERS

        self._vertical_shift_speed_index: int = self.DEFAULT_VERTICAL_SHIFT_SPEED_INDEX
        self._pre_amp_gain_index: int = self.DEFAULT_PRE_AMP_GAIN_INDEX
        self._ad_channel: int = self.DEFAULT_AD_CHANNEL
        self._output_amplifier: int = self.DEFAULT_OUTPUT_AMPLIFIER
        self._horizontal_shift_speed_index: int = self.DEFAULT_HORIZONTAL_SHIFT_SPEED_INDEX

        self._cooler_persistence_mode: bool = self.DEFAULT_COOLER_PERSISTENCE_MODE

    def open(self) -> None:
        """
        Initializes the connection to the CCD and the spectrograph.

        This method will automatically set the sensor target temperature to `DEFAULT_SET_TEMPERATURE`.
        If that needs to change for a specific CCD initialization, make sure to change it after the CCD is on.

        >>> spectrometer_config = AndorSpectrometerConfig()
        >>> spectrometer_config.open()
        >>> spectrometer_config.sensor_temperature_set_point = -65  # In degC

        If you want to change the default temperature for all initializations, do so before opening the devices:

        >>> spectrometer_config = AndorSpectrometerConfig()
        >>> spectrometer_config.DEFAULT_SET_TEMPERATURE = -65  # in degC
        """
        with _andor_api.lock:
            self._open_ccd()
            self._open_spg()

        self.horizontal_image_flip = self.input_port != self.output_port

    def _open_ccd(self):
        """
        Initializes the connection to the CCD and turns on the cooler.

        This method will automatically set the sensor target temperature to `DEFAULT_SET_TEMPERATURE`.
        If that needs to change for a specific CCD initialization, make sure to change it after the CCD is on.

        >>> spectrometer_config = AndorSpectrometerConfig()
        >>> spectrometer_config.open()
        >>> spectrometer_config.sensor_temperature_set_point = -65  # In degC

        If you want to change the default temperature for all initializations, do so before opening the devices:

        >>> spectrometer_config = AndorSpectrometerConfig()
        >>> spectrometer_config.DEFAULT_SET_TEMPERATURE = -65  # in degC
        """
        with _andor_api.lock:
            if not _andor_api.is_ccd_initialized():
                status = _andor_api.ccd.Initialize("")
                _andor_api.log_ccd_response('CCD initialization', status)
                status = _andor_api.ccd.CoolerON()
                _andor_api.log_ccd_response('CCD cooler turn-on', status)
                self.sensor_temperature_set_point = self.DEFAULT_SET_TEMPERATURE
                self.cooler_persistence_mode = self._cooler_persistence_mode
            else:
                _andor_api.logger.debug('CCD is already initialized.')

            self._ccd_info = CCDInfo(self.ccd_device_index)

    def _open_spg(self):
        """
        Initializes the connection to the spectrograph.

        Must be called after the CCD is initialized, so that
        we retrieve and set all the relevant information for the
        spectrograph.
        """
        with _andor_api.lock:
            if not _andor_api.is_spg_initialized():
                status = _andor_api.spg.Initialize("")
                _andor_api.log_spg_response('Spectrograph initialization', status)

                status, self._spg_number_of_devices = _andor_api.spg.GetNumberDevices()
                _andor_api.log_spg_response('Getting number of spectrograph devices', status)

                status = _andor_api.spg.SetPixelWidth(self.spg_device_index, self.ccd_info.pixel_width)
                _andor_api.log_spg_response('Setting spectrograph pixel width', status)

                status = _andor_api.spg.SetNumberPixels(
                    self.spg_device_index, self.ccd_info.number_of_pixels_horizontally)
                _andor_api.log_spg_response('Setting spectrograph number of pixels', status)
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

        Notes
        -----
        The CCD SDK ShutDown method has a bug if the AndorSDK is older
        than AndorSDKSetup-2.104.30084.0. In that case, to
        properly close the CCD, you need to use ShuDown once,
        InitializeDevice and then ShutDown again.
        The InitializeDevice method is not the same as Initialize,
        and it does not actually initialize the device...

        In the case you have an older AndorSDK version installed,
        Change the definition of the_close_ccd method to:

        >>> with _andor_api.lock:
        ...     if _andor_api.is_ccd_initialized():
        ...         status1 = _andor_api.ccd.ShutDown()
        ...         status2 = _andor_api.ccd.InitializeDevice('')
        ...         status3 = _andor_api.ccd.ShutDown()
        ...         for i, status in enumerate([status1, status2, status3]):
        ...             _andor_api.log_ccd_response(f'CCD shutdown (step {i + 1})', status)
        ...     else:
        ...         _andor_api.logger.warning('CCD is already closed')
        """
        with _andor_api.lock:
            if _andor_api.is_ccd_initialized():
                status = _andor_api.ccd.ShutDown()
                _andor_api.log_ccd_response(f'CCD shutdown', status)
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
        return list(range(self._ccd_number_of_devices))

    @property
    def ccd_info(self):
        """ Returns the dataclass object holding the invariable information of the CCD. """
        return self._ccd_info

    @property
    def ccd_device_index(self) -> int:
        """ The index corresponding to the selected CCD device. """
        with _andor_api.lock:
            status, ccd_device_index = _andor_api.ccd.GetCurrentCamera()
        _andor_api.log_ccd_response('Getting current camera', status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS and self.ccd_number_of_devices > 0:
            return ccd_device_index

        return -1

    @ccd_device_index.setter
    @prevent_none_set
    def ccd_device_index(self, value: int):
        """ To change the current CCD, we need to close the connection with the previous CCD first. """
        if value == self.ccd_device_index:
            return

        if value in self.ccd_device_list:
            was_initialized = _andor_api.is_ccd_initialized()
            if was_initialized:
                self._close_ccd()
                _andor_api.ccd.SetCurrentCamera(_andor_api.ccd.GetCameraHandle(value)[1])
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
        return list(range(self._spg_number_of_devices))

    @property
    def spg_info(self):
        """ Returns the dataclass object holding the invariable information of the Spectrograph. """
        return self._spg_info

    @property
    def spg_device_index(self) -> int:
        """ The index corresponding to the selected spectrometer device. """
        return self._spg_device_index if self._spg_number_of_devices > 0 else -1

    @spg_device_index.setter
    @prevent_none_set
    def spg_device_index(self, value: int):
        if value == self.spg_device_index:
            return

        if not _andor_api.is_spg_initialized():
            self._spg_device_index = value
            self.logger.debug(f'Spectrograph device index set to {value} while the device was not initialized.'
                              'This may result in trying to access a spectrograph that does not exist.')
            return

        if value in self.spg_device_list:
            self._spg_device_index = value

            status = _andor_api.spg.SetPixelWidth(self.spg_device_index, self.ccd_info.pixel_width)
            _andor_api.log_spg_response('Setting spectrograph pixel width', status)

            status = _andor_api.spg.SetNumberPixels(
                self.spg_device_index, self.ccd_info.number_of_pixels_horizontally)
            _andor_api.log_spg_response('Setting spectrograph number of pixels', status)

            self._spg_info = SpectrographInfo(self.spg_device_index)
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

        return [gi.short_description for gi in grating_info_values]

    @property
    def current_grating_index(self) -> int:
        """
        Current spectrometer-grating index.
        """
        with _andor_api.lock:
            status, current_grating = _andor_api.spg.GetGrating(self.spg_device_index)
        _andor_api.log_spg_response("Getting current grating index", status)
        return current_grating

    @current_grating_index.setter
    @prevent_none_set
    def current_grating_index(self, value: int) -> None:
        """
        Set the spectrometer grating index.
        """
        if value == self.current_grating:
            return

        with _andor_api.lock:
            status = _andor_api.spg.SetGrating(self.spg_device_index, value)
        _andor_api.log_spg_response("Setting current grating", status)

    @property
    def current_grating(self) -> str:
        """
        Current spectrometer grating.
        """
        current_grating_index = self.current_grating_index
        grating_list = self.grating_list

        return grating_list[current_grating_index - 1] if len(grating_list) > 0 else "None"

    @current_grating.setter
    @prevent_none_set
    def current_grating(self, value: str) -> None:
        """
        Set the spectrometer grating.
        """
        if value == self.current_grating:
            return

        grating_list = self.grating_list
        if value not in grating_list:
            _andor_api.logger.warning(
                f"Grating '{value}' is not in the grating list {grating_list}. "
                f"Grating remains as is: {self.current_grating}"
            )
            return

        grating_index = grating_list.index(value) + 1
        with _andor_api.lock:
            status = _andor_api.spg.SetGrating(self.spg_device_index, grating_index)
        _andor_api.log_spg_response("Setting current grating", status)

    @property
    def input_port(self) -> str:
        """
        Get the input port (input flipper mirror).
        """
        with _andor_api.lock:
            status, input_flipper_mirror = _andor_api.spg.GetFlipperMirror(
                self.spg_device_index, _andor_api.spg.INPUT_FLIPPER)
        _andor_api.log_spg_response("Getting input port", status)
        return self.SpectrographFlipperMirrorPort(input_flipper_mirror).name

    @input_port.setter
    @prevent_none_set
    def input_port(self, name: str) -> None:
        """
        Set the input port (input flipper mirror).
        Also, automatically adjusts CCD horizontal flip state.
        """
        if name == self.input_port:
            return
        setter_value: int = self.SpectrographFlipperMirrorPort[name].value
        with _andor_api.lock:
            status = _andor_api.spg.SetFlipperMirror(
                self.spg_device_index, _andor_api.spg.INPUT_FLIPPER, setter_value)
        _andor_api.log_spg_response("Setting input port", status)

        self.horizontal_image_flip = setter_value != self.output_port

    @property
    def output_port(self) -> str:
        """
        Get the output port (output flipper mirror).
        """
        with _andor_api.lock:
            status, output_flipper_mirror = _andor_api.spg.GetFlipperMirror(
                self.spg_device_index, _andor_api.spg.OUTPUT_FLIPPER)
        _andor_api.log_spg_response("Getting output port", status)
        return self.SpectrographFlipperMirrorPort(output_flipper_mirror).name

    @output_port.setter
    @prevent_none_set
    def output_port(self, name: str) -> None:
        """
        Set the output port (output flipper mirror).
        Also, automatically adjusts CCD horizontal flip state.
        """
        if name == self.output_port:
            return

        setter_value: int = self.SpectrographFlipperMirrorPort[name].value
        with _andor_api.lock:
            status = _andor_api.spg.SetFlipperMirror(
                self.spg_device_index, _andor_api.spg.OUTPUT_FLIPPER, setter_value)
        _andor_api.log_spg_response("Setting output port", status)

        self.horizontal_image_flip = setter_value != self.input_port

    @property
    def horizontal_image_flip(self) -> bool:
        """
        The horizontal image flip.
        """
        with _andor_api.lock:
            status, horizontal_image_flip, _ = _andor_api.ccd.GetImageFlip()
        _andor_api.log_ccd_response("Getting image flip", status)
        return bool(horizontal_image_flip)

    @horizontal_image_flip.setter
    @prevent_none_set
    def horizontal_image_flip(self, value: bool) -> None:
        """
        Set the horizontal image flip.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetImageFlip(int(value), int(self.vertical_image_flip))
        _andor_api.log_ccd_response("Setting image flip", status)

    @property
    def vertical_image_flip(self) -> bool:
        """
        The vertical image flip.
        """
        with _andor_api.lock:
            status, _, vertical_image_flip = _andor_api.ccd.GetImageFlip()
        _andor_api.log_ccd_response("Getting vertical image flip", status)
        return bool(vertical_image_flip)

    @vertical_image_flip.setter
    @prevent_none_set
    def vertical_image_flip(self, value: bool) -> None:
        """
        Set the vertical image flip.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetImageFlip(int(self.horizontal_image_flip), int(value))
        _andor_api.log_ccd_response("Setting vertical image flip", status)

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
    @prevent_none_set
    def center_wavelength(self, nanometers: float) -> None:
        """
        Sets the grating center wavelength.
        """
        if nanometers == self.center_wavelength:
            return

        with _andor_api.lock:
            status = _andor_api.spg.SetWavelength(self.spg_device_index, nanometers)
        _andor_api.log_spg_response("Setting center wavelength", status)

    @property
    def starting_wavelength(self) -> float:
        """
        The Step and Glue starting wavelength.
        """
        return np.nan

    @starting_wavelength.setter
    @prevent_none_set
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
        return np.nan

    @ending_wavelength.setter
    @prevent_none_set
    def ending_wavelength(self, lambda_max: float) -> None:
        """
        Sets the Step and Glue ending wavelength.
        """
        pass

    @property
    def pixel_offset(self) -> float:
        """
        The pixel offset used in the Andor Solis software.
        It is *subtracted* from the pixel numbers.

        This pixel offset is used in the `get_wavelengths` and
        `processed_wavelength_calibration_coefficients` methods.
        """
        return self._pixel_offset

    @pixel_offset.setter
    @prevent_none_set
    def pixel_offset(self, value: float):
        """
        Sets the pixel offset used in the Andor Solis software.
        It is *subtracted* from the pixel numbers.

        This pixel offset is used in the `get_wavelengths` and
        `processed_wavelength_calibration_coefficients` methods.
        """
        self._pixel_offset = value

    @property
    def wavelength_offset(self) -> float:
        """
        Returns the user-defined wavelength offset.
        It is *added* to the calibrated wavelengths.

        This wavelength offset is used in the `get_wavelengths` and
        `processed_wavelength_calibration_coefficients` methods.
        """
        return self._wavelength_offset

    @wavelength_offset.setter
    @prevent_none_set
    def wavelength_offset(self, value: float):
        """
        Sets the user-defined wavelength offset.
        It is *added* to the calibrated wavelengths.

        This wavelength offset is used in the `get_wavelengths` and
        `processed_wavelength_calibration_coefficients` methods.
        """
        self._wavelength_offset = value

    @property
    def raw_wavelength_calibration_coefficients(self) -> Tuple[float, float, float, float]:
        """
        Returns the four wavelength calibration coefficients for a single frame.

        To calculate the wavelength for each pixel, use the equation

        $$ \lambda = \sum_{k=0}^3 c_k p^k . $$

        In code:

        >>> coefficients = ...
        ... number_of_pixels = ...
        ... pixels = np.linspace(1, number_of_pixels, number_of_pixels)
        ... wavelengths = pixels * 0
        ... for i, coefficient in enumerate(coefficients):
        ...     wavelengths += pixels ** i * coefficient

        However, the Andor Solis software provides the ability to add a
        pixel offset, a parameter that is not accessible via the Andor API.
        When taking data with Andor Solis, the saved sif file will
        modify the coefficients if the pixel offset is not 0!!
        We do not know exactly how Andor Solis modifies the coefficients,
        or how it adds the pixel offset.
        Albeit not exact, working through the calibration equations assuming
        the pixel offset is just *subtracted* from the pixel numbers, we can get a
        good approximation of the final coefficients and calibrated wavelengths.
        This approximately yields calibrated wavelengths with
        Δλ < Δp * 4e-5 nm from what Andor Solis coefficients give!
        Here is how we estimate the new coefficients:

        >>> coefficients = ...
        ... pixel_offset = ...  # negative of the value given in Andor Solis or the implementation of this class.
        ... a, b, c, d = coefficients
        ... d_new = d
        ... c_new = c + 3 * d * pixel_offset
        ... b_new = b + 2 * c * pixel_offset + 3 * d * pixel_offset ** 2
        ... a_new = a + b * pixel_offset + c * pixel_offset ** 2 + d * pixel_offset ** 3
        ... new_coefficients = [a_new, b_new, c_new, d_new]

        Then, you can use the first code snipet to get an array of
        wavelengths for each pixel.
        """
        with _andor_api.lock:
            status, a, b, c, d = _andor_api.spg.GetPixelCalibrationCoefficients(self.spg_device_index)
        _andor_api.log_spg_response("Getting wavelength calibration parameters", status)
        return a, b, c, d

    @property
    def processed_wavelength_calibration_coefficients(self) -> Tuple[float, float, float, float]:
        """
        Returns the four wavelength calibration coefficients for a single frame.

        These coefficients take into account the pixel and wavelength offsets.
        See `raw_wavelength_calibration_coefficients` for more information.

        """
        coefficients = self.raw_wavelength_calibration_coefficients
        pixel_offset = - self.pixel_offset  # negative of the value given in Andor Solis or in this class.
        a, b, c, d = coefficients
        d_new = d
        c_new = c + 3 * d * pixel_offset
        b_new = b + 2 * c * pixel_offset + 3 * d * pixel_offset ** 2
        a_new = a + b * pixel_offset + c * pixel_offset ** 2 + d * pixel_offset ** 3 + self.wavelength_offset
        return a_new, b_new, c_new, d_new

    @property
    def pixels(self):
        number_of_pixels = self.ccd_info.number_of_pixels_horizontally
        return np.linspace(1, number_of_pixels, number_of_pixels)

    def get_wavelengths(self) -> np.ndarray:
        """
        Returns the wavelength calibration for a single frame.

        This is the equivalent of:

        $$ \lambda = \Delta \lambda + \sum_{k=0}^3 c_k \left(p - \Delta p\right)^k $$

        """
        coefficients = self.processed_wavelength_calibration_coefficients
        pixels = self.pixels
        wavelengths = pixels * 0

        for i, coefficient in enumerate(coefficients):
            wavelengths += pixels ** i * coefficient

        return wavelengths

    @property
    def cooler(self) -> bool:

        """
        Returns True if the CCD is currently being cooled.
        """
        with _andor_api.lock:
            status, cooler_status = _andor_api.ccd.IsCoolerOn()
        _andor_api.log_ccd_response("Getting CCD cooler state", status)
        return bool(cooler_status)

    @cooler.setter
    @prevent_none_set
    def cooler(self, value: bool):
        """
        Turns the CCD cooler on or off.
        If the cooler is on, it will turn off when the CCD
        shuts down.
        """
        set_cooler_state: Callable[[], int] = _andor_api.ccd.CoolerON if value else _andor_api.ccd.CoolerOFF
        with _andor_api.lock:
            status = set_cooler_state()
        _andor_api.log_ccd_response("Setting CCD cooler state", status)

    @property
    def cooler_persistence_mode(self) -> bool:
        """
        The cooler persistence mode.

        If the cooler persistence mode is on, it means that
        the CCD cooler will not turn off when the CCD
        shuts down.
        """
        return self._cooler_persistence_mode

    @cooler_persistence_mode.setter
    @prevent_none_set
    def cooler_persistence_mode(self, value: bool) -> None:
        with _andor_api.lock:
            status = _andor_api.ccd.SetCoolerMode(int(value))
        _andor_api.log_ccd_response("Setting cooler persistence mode", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._cooler_persistence_mode = value

    @property
    def sensor_temperature(self) -> float:
        """
        The current sensor temperature in Celsius.
        """
        with _andor_api.lock:
            # We could have used `_andor_api.ccd.GetTemperature()`, but that returns an integer
            status, temperature, _, _, _ = _andor_api.ccd.GetTemperatureStatus()
        _andor_api.log_ccd_response("Getting CCD current temperature", status)
        return temperature

    @property
    def sensor_temperature_set_point(self) -> int:
        """
        The sensor set-point temperature in Celsius.
        """
        with _andor_api.lock:
            status, _, temperature, _, _ = _andor_api.ccd.GetTemperatureStatus()
        _andor_api.log_ccd_response("Getting CCD target temperature", status)
        return temperature

    @sensor_temperature_set_point.setter
    @prevent_none_set
    def sensor_temperature_set_point(self, deg_celsius: int) -> None:
        """
        Sets the sensor target temperature in Celsius.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetTemperature(int(deg_celsius))
        _andor_api.log_ccd_response("Setting CCD temperature", status)

    @property
    def exposure_time(self) -> float:
        """
        Returns the single frame exposure time (in seconds).
        """
        with _andor_api.lock:
            status, exposure_time, _, _ = _andor_api.ccd.GetAcquisitionTimings()
        _andor_api.log_ccd_response("Getting exposure time", status)
        return exposure_time

    @exposure_time.setter
    @prevent_none_set
    def exposure_time(self, secs: float) -> None:
        """
        Sets the single frame exposure time in seconds.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetExposureTime(secs)
        _andor_api.log_ccd_response("Setting exposure time", status)

    @property
    def accumulation_cycle_time(self) -> float:
        """
        Returns the accumulation cycle time (in seconds).
        """
        with _andor_api.lock:
            status, _, accumulation_cycle_time, _ = _andor_api.ccd.GetAcquisitionTimings()
        _andor_api.log_ccd_response("Getting accumulation cycle time", status)
        return accumulation_cycle_time

    @accumulation_cycle_time.setter
    @prevent_none_set
    def accumulation_cycle_time(self, secs: float) -> None:
        """
        Sets the accumulation cycle time in seconds.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetAccumulationCycleTime(secs)
        _andor_api.log_ccd_response("Setting accumulation cycle time", status)

    @property
    def number_of_accumulations(self) -> int:
        """
        Returns the number of accumulations (only used in accumulation or kinetic series mode).
        """
        return self._number_of_accumulations

    @number_of_accumulations.setter
    @prevent_none_set
    def number_of_accumulations(self, value: int):
        """
        Sets the number of accumulations (only used in accumulation or kinetic series mode).
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetNumberAccumulations(value)
        _andor_api.log_ccd_response("Setting number of accumulations", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._number_of_accumulations = value

    @property
    def kinetic_cycle_time(self) -> float:
        """
        Returns the kinetic cycle time (in seconds).
        """
        with _andor_api.lock:
            status, _, _, kinetic_cycle_time = _andor_api.ccd.GetAcquisitionTimings()
        _andor_api.log_ccd_response("Getting kinetic cycle time", status)
        return kinetic_cycle_time

    @kinetic_cycle_time.setter
    @prevent_none_set
    def kinetic_cycle_time(self, secs: float) -> None:
        """
        Sets the kinetic cycle time in seconds.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetKineticCycleTime(secs)
        _andor_api.log_ccd_response("Setting kinetic cycle time", status)

    @property
    def number_of_kinetics(self) -> int:
        """
        Returns the number of kinetic cycles (only used in kinetic series mode).
        """
        return self._number_of_kinetics

    @number_of_kinetics.setter
    @prevent_none_set
    def number_of_kinetics(self, value: int):
        """
        Sets the number of kinetic cycles (only used in kinetic series mode).
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetNumberKinetics(value)
        _andor_api.log_ccd_response("Setting number of kinetic cycles", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._number_of_kinetics = value

    @property
    def remove_cosmic_rays(self) -> bool:
        """
        Returns whether the CCD is configured to remove cosmic rays in accumulation mode.

        Since the Andor API does not like keeping the cosmic ray filter enabled while
        on Sinlge Scan or Run Till Abort modes, we keep the user preferred value in a
        local variable that we return.
        """
        if self._remove_cosmic_rays is not None:
            return self._remove_cosmic_rays

        with _andor_api.lock:
            status, self._remove_cosmic_rays = _andor_api.ccd.GetFilterMode()
        _andor_api.log_ccd_response("Getting filter mode (cosmic ray removal)", status)
        return bool(self._remove_cosmic_rays)

    @remove_cosmic_rays.setter
    @prevent_none_set
    def remove_cosmic_rays(self, value: bool):
        """
        Sets whether the CCD is configured to remove cosmic rays in accumulation mode.

        Since the Andor API does not like keeping the cosmic ray filter enabled while
        on Sinlge Scan or Run Till Abort modes, we keep the user preferred value in a
        local variable that we return.
        To double-down, we will make sure the filter is off if this property is called,
        but only on the device end. We will not change the internal value, and when the
        mode changes to something that supports accumulation, the filter will be turned
        on automatically.
        """

        with _andor_api.lock:
            allowed_modes = [
                self.AcquisitionMode.ACCUMULATE.name,
                self.AcquisitionMode.KINETICS.name,
                self.AcquisitionMode.FAST_KINETICS.name
            ]
            if value and self.acquisition_mode not in allowed_modes:
                _andor_api.logger.warning(f'Enabling cosmic ray filter is not allowed in {self.acquisition_mode}.')
                self.temporarily_disable_cosmic_ray_filter()
                return

            status = _andor_api.ccd.SetFilterMode(int(value) * 2)
        _andor_api.log_ccd_response("Setting filter mode (cosmic ray removal)", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._remove_cosmic_rays = value

    @staticmethod
    def temporarily_disable_cosmic_ray_filter():
        if _andor_api.ccd.GetFilterMode()[1]:
            status = _andor_api.ccd.SetFilterMode(0)
            _andor_api.log_ccd_response("Temporarily disabling filter mode (cosmic ray removal)", status)

    @property
    def baseline_clamp(self) -> bool:
        """
        Returns whether the CCD is configured to clamp the baseline counts.
        """
        with _andor_api.lock:
            status, baseline_clamp = _andor_api.ccd.GetBaselineClamp()
        _andor_api.log_ccd_response("Getting baseline clamp", status)
        return bool(baseline_clamp)

    @baseline_clamp.setter
    @prevent_none_set
    def baseline_clamp(self, value: bool):
        """
        Sets whether the CCD is configured to clamp the baseline counts.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.SetBaselineClamp(int(value))
        _andor_api.log_ccd_response("Setting baseline clamp", status)

    @property
    def acquisition_mode(self) -> str:
        """
        Returns the current acquisition mode.
        """
        return self._acquisition_mode

    @acquisition_mode.setter
    @prevent_none_set
    def acquisition_mode(self, mode_name: str):
        """
        Sets the acquisition mode.
        """
        mode_value = self.AcquisitionMode[mode_name].value

        if mode_name not in self.SUPPORTED_ACQUISITION_MODES:
            error_message = (f"Unsupported acquisition mode: {mode_name}. "
                             f"Supported modes are {self.SUPPORTED_ACQUISITION_MODES}.")
            self.logger.error(error_message)
            # raise ValueError(error_message)
            return

        with _andor_api.lock:
            status = _andor_api.ccd.SetAcquisitionMode(mode_value)
        _andor_api.log_ccd_response("Setting acquisition mode", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._acquisition_mode = mode_name
            if mode_name in [self.AcquisitionMode.SINGLE_SCAN.name, self.AcquisitionMode.RUN_TILL_ABORT.name]:
                self.temporarily_disable_cosmic_ray_filter()
            else:
                self.remove_cosmic_rays = self._remove_cosmic_rays

    @property
    def read_mode(self) -> str:
        """
        Returns the current read mode.
        """
        return self._read_mode

    @read_mode.setter
    @prevent_none_set
    def read_mode(self, mode_name: str):
        """
        Sets the read mode.
        """
        mode_value = self.ReadMode[mode_name].value

        if mode_name not in self.SUPPORTED_READ_MODES:
            error_message = (f"Unsupported read mode: {mode_name}. "
                             f"Supported modes are {self.SUPPORTED_READ_MODES}.")
            self.logger.error(error_message)
            # raise ValueError(error_message)
            return

        with _andor_api.lock:
            status = _andor_api.ccd.SetReadMode(mode_value)
        _andor_api.log_ccd_response("Setting read mode", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._read_mode = mode_name

    @property
    def trigger_mode(self) -> str:
        """
        Returns the current trigger mode.
        """
        return self._trigger_mode

    @trigger_mode.setter
    @prevent_none_set
    def trigger_mode(self, mode_name: str):
        """
        Sets the trigger mode.
        """
        mode_value = self.TriggerMode[mode_name].value

        if mode_name not in self.SUPPORTED_TRIGGER_MODES:
            error_message = (f"Unsupported trigger mode: {mode_name}. "
                             f"Supported modes are {self.SUPPORTED_TRIGGER_MODES}")
            self.logger.error(error_message)
            # raise ValueError(error_message)
            return

        with _andor_api.lock:
            status = _andor_api.ccd.SetTriggerMode(mode_value)
        _andor_api.log_ccd_response("Setting trigger mode", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._trigger_mode = mode_name

    @property
    def horizontal_bin_size(self) -> int:
        """
        Returns the horizontal binning of the CCD.
        """
        return self._horizontal_bin_size

    @horizontal_bin_size.setter
    @prevent_none_set
    def horizontal_bin_size(self, value: int):
        """
        Sets the horizontal binning of the CCD.
        """
        if value <= 0:
            error_message = f"Horizontal bin size must be a positive integer. Got {value}."
            self.logger.error(error_message)
            # raise ValueError(error_message)
            return

        if self.read_mode == self.ReadMode.FVB.name:
            setting_bin_size_method: Callable[[int], int] = _andor_api.ccd.SetFVBHBin
        elif self.read_mode == self.ReadMode.SINGLE_TRACK.name:
            setting_bin_size_method: Callable[[int], int] = _andor_api.ccd.SetSingleTrackHBin
        elif self.read_mode == self.ReadMode.MULTI_TRACK.name:
            setting_bin_size_method: Callable[[int], int] = _andor_api.ccd.SetMultiTrackHBin
        elif self.read_mode == self.ReadMode.RANDOM_TRACK.name:
            setting_bin_size_method: Callable[[int], int] = _andor_api.ccd.SetCustomTrackHBin
        else:
            raise NotImplementedError(f"Horizontal binning is not supported for read mode {self.read_mode}.")

        with _andor_api.lock:
            status = setting_bin_size_method(value)
        _andor_api.log_ccd_response("Setting horizontal bin size", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._horizontal_bin_size = value

    @property
    def keep_clean_on_external_trigger(self) -> bool:
        """
        Returns whether the CCD is configured to keep the clean buffer on external trigger.
        """
        return self._keep_clean_on_external_trigger

    @keep_clean_on_external_trigger.setter
    @prevent_none_set
    def keep_clean_on_external_trigger(self, value: bool):
        """
        Sets whether the CCD is configured to keep the clean buffer on external trigger.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.EnableKeepCleans(int(value))
        _andor_api.log_ccd_response("Setting keep clean on external trigger", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._keep_clean_on_external_trigger = value

    @property
    def keep_clean_time(self) -> int:
        """
        Returns the keep clean time of the CCD in seconds.
        """
        with _andor_api.lock:
            status, keep_clean_time = _andor_api.ccd.GetKeepCleanTime()
        _andor_api.log_ccd_response("Getting keep clean time", status)
        return keep_clean_time

    @property
    def single_track_read_mode_parameters(self):
        return self._single_track_read_mode_parameters

    @single_track_read_mode_parameters.setter
    @prevent_none_set
    def single_track_read_mode_parameters(self, single_track_read_mode_parameters: SingleTrackReadModeParameters):
        """
        Sets the single track parameters. Does not change the read mode.
        """
        if single_track_read_mode_parameters.track_height is None:
            return
        if single_track_read_mode_parameters.track_center_row is None:
            return

        with _andor_api.lock:
            status = _andor_api.ccd.SetSingleTrack(
                single_track_read_mode_parameters.track_center_row, single_track_read_mode_parameters.track_height)
        _andor_api.log_ccd_response("Setting single track parameters", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._single_track_read_mode_parameters = single_track_read_mode_parameters

    @property
    def single_acquisition_data_size(self) -> int:
        """
        Returns the size of the data returned by a single acquisition.
        This size is related to the read mode and the pixel number of the CCD.

        As of now, only single-track and full vertical binning read-modes are supported.
        This is because:
            - These two modes produce 1-D arrays for single acquisition.
            - The other modes require setting arbitrary parameters that result in
            2-D arrays of various row and column numbers.
            It would take too long to implement methods and attributes to track these
            parameters, because the Andor API does not implement Getter methods for them
            (I know - what a shocker).
        If you want to support a new mode, define a dataclass with all the relevant info
        regarding that mode, and store it in an internal class attribute.
        See the single track implementation as an example.
        """
        if self.read_mode in [self.ReadMode.FVB.name, self.ReadMode.SINGLE_TRACK.name]:
            return self.ccd_info.number_of_pixels_horizontally // self.horizontal_bin_size

        error_message = f"Read mode {self.read_mode} is not supported."
        self.logger.error(error_message)
        raise NotImplementedError(error_message)

    @property
    def total_number_of_single_acquisitions_per_acquisition_cycle(self) -> int:
        if self.acquisition_mode in [self.AcquisitionMode.SINGLE_SCAN.name, self.AcquisitionMode.RUN_TILL_ABORT.name]:
            return 1
        elif self.acquisition_mode in [self.AcquisitionMode.ACCUMULATE.name, self.AcquisitionMode.FAST_KINETICS.name]:
            return self.number_of_accumulations
        else:  # KINETICS
            return self.number_of_accumulations * self.number_of_kinetics

    # TODO: for vertical voltage clock amplitudes: SetVSAmplitude, GetNumberVSAmplitudes, GetVSAmplitudeValue,
    #  GetVSAmplitudeFromString, GetVSAmplitudeString

    @property
    def vertical_shift_speed(self) -> float:
        """
        Returns the vertical shift speed of the CCD (units of microseconds).
        """
        if self._vertical_shift_speed_index == -1:
            idx = self.ccd_info.fastest_recommended_vertical_shift_speed[0]
        else:
            idx = self._vertical_shift_speed_index

        try:
            return self.ccd_info.available_vertical_shift_speeds[idx]
        except IndexError:
            return np.nan

    @vertical_shift_speed.setter
    @prevent_none_set
    def vertical_shift_speed(self, speed: float):
        """
        Sets the vertical shift speed of the CCD (units of microseconds).
        """
        target_speed_index = self.ccd_info.available_vertical_shift_speeds.index(speed)
        with _andor_api.lock:
            status = _andor_api.ccd.SetVSSpeed(target_speed_index)
        _andor_api.log_ccd_response("Setting vertical shift speed", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._vertical_shift_speed_index = target_speed_index

    @property
    def pre_amp_gain(self) -> float:
        """
        Returns the pre-amp gain of the CCD.
        """
        if self._pre_amp_gain_index in range(self.ccd_info.number_of_pre_amp_gains):
            return self.ccd_info.available_pre_amp_gains[self._pre_amp_gain_index]

        return np.nan

    @pre_amp_gain.setter
    @prevent_none_set
    def pre_amp_gain(self, gain: float):
        """
        Sets the pre-amp gain of the CCD.
        """
        target_pre_amp_gain_index = self.ccd_info.available_pre_amp_gains.index(gain)
        with _andor_api.lock:
            status = _andor_api.ccd.SetPreAmpGain(target_pre_amp_gain_index)
        _andor_api.log_ccd_response("Setting pre-amp gain", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._pre_amp_gain_index = target_pre_amp_gain_index

    @property
    def ad_channel(self) -> int:
        """
        Returns the AD channel of the CCD.
        """
        return self._ad_channel

    @ad_channel.setter
    @prevent_none_set
    def ad_channel(self, channel: int):
        """
        Sets the AD channel of the CCD.
        """
        if channel not in range(self.ccd_info.number_of_ad_channels):
            error_message = (f"Unsupported A/D channel: {channel}. "
                             f"Supported channel are {range(self.ccd_info.number_of_ad_channels)}")
            self.logger.error(error_message)
            # raise ValueError(error_message)
            return

        with _andor_api.lock:
            status = _andor_api.ccd.SetADChannel(channel)
        _andor_api.log_ccd_response("Setting A/D channel", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._ad_channel = channel

    @property
    def output_amplifier(self) -> int:
        """
        Returns the amplifier of the CCD.
        """
        return self._output_amplifier

    @output_amplifier.setter
    @prevent_none_set
    def output_amplifier(self, output_amplifier: int):
        """
        Sets the amplifier of the CCD.
        """
        if output_amplifier not in range(self.ccd_info.number_of_output_amplifiers):
            error_message = (f"Unsupported amplifier: {output_amplifier}. "
                             f"Supported amplifiers are {range(self.ccd_info.number_of_output_amplifiers)}")
            self.logger.error(error_message)
            # raise ValueError(error_message)

        with _andor_api.lock:
            status = _andor_api.ccd.SetOutputAmplifier(output_amplifier)
        _andor_api.log_ccd_response("Setting output amplifier", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._output_amplifier = output_amplifier

    @property
    def horizontal_shift_speed(self) -> float:
        """
        Returns the horizontal shift speed of the CCD (units of MHz).
        """
        key = (self.ad_channel, self.output_amplifier)
        idx = self._horizontal_shift_speed_index
        if key in self.ccd_info.available_horizontal_shift_speeds:
            return self.ccd_info.available_horizontal_shift_speeds[key][idx]
        return np.nan

    @horizontal_shift_speed.setter
    @prevent_none_set
    def horizontal_shift_speed(self, speed: float):
        """
        Sets the horizontal shift speed of the CCD (units of MHz).
        """
        key = (self.ad_channel, self.output_amplifier)
        target_speed_index = self.ccd_info.available_horizontal_shift_speeds[key].index(speed)
        with _andor_api.lock:
            status = _andor_api.ccd.SetHSSpeed(self.output_amplifier, target_speed_index)
        _andor_api.log_ccd_response("Setting horizontal shift speed", status)
        if status == _andor_api.ccd_error_codes.DRV_SUCCESS:
            self._horizontal_shift_speed_index = target_speed_index


class AndorSpectrometerDataAcquisition(SpectrometerDataAcquisition):
    DEVICE_NAME: str = 'Andor Spectrometer'

    ACQUISITION_MODES: Set[str] = {'single', 'kinetic series', 'accumulation'}

    def __init__(self, spectrometer_config: AndorSpectrometerConfig):
        """
        Parameters
        ----------
        spectrometer_config : AndorSpectrometerConfig, optional
            The Andor spectrometer configuration object.
            Used to set the appropriate acquisition settings when needed.
        """
        super().__init__(spectrometer_config)
        self.spectrometer_config: AndorSpectrometerConfig
        self._reach_temperature_before_acquisition = False
        self.wait_for_temperature_flag = True

    def _base_acquisition_method(self) -> bool:
        """
        Base method that starts the acquisition and waits for it to finish.
        This method is used by all the acquisition methods.
        It is not meant to be called directly by the user.
        It is meant to be called by the acquire method.

        Returns
        -------
        bool
            Whether the acquisition was successful and new data were created.
        """
        with _andor_api.lock:
            status = _andor_api.ccd.StartAcquisition()
        _andor_api.log_ccd_response("Starting acquisition", status)
        with _andor_api.lock:
            for _ in range(self.spectrometer_config.total_number_of_single_acquisitions_per_acquisition_cycle):
                status = _andor_api.ccd.WaitForAcquisition()
                _andor_api.log_ccd_response("Waiting for acquisition", status)

        return status == _andor_api.ccd_error_codes.DRV_SUCCESS

    def _get_acquired_data(self, data_size: int):
        """
        Retrieves the acquired data from the CCD.

        Parameters
        ----------
        data_size : int
            The size of the data to be retrieved.
            See `AndorSpectrometerConfig.single_acquisition_data_size`
            for more information.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            The data array and the wavelengths corresponding to the data.
            Data array is filled with np.nan if no data were acquired
            (e.g., acquisition was aborted).
        """
        with _andor_api.lock:
            status, data = _andor_api.ccd.GetAcquiredData(data_size)
        _andor_api.log_ccd_response("Getting acquired data", status)

        if status != _andor_api.ccd_error_codes.DRV_SUCCESS:
            data = np.empty(data_size)
            data.fill(np.nan)

        return data, self.spectrometer_config.get_wavelengths()

    def acquire(self, acquisition_mode: Literal['single', 'kinetic series', 'accumulation'], **kwargs) \
            -> Union[Tuple[np.ndarray, np.ndarray], None]:
        return super().acquire(acquisition_mode, **kwargs)

    def single_acquisition(self) -> Tuple[np.ndarray, np.ndarray]:
        self._base_acquisition_method()
        data_size = self.spectrometer_config.single_acquisition_data_size
        return self._get_acquired_data(data_size)

    def accumulation_acquisition(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.single_acquisition()

    def kinetic_series_acquisition(self) -> Tuple[np.ndarray, np.ndarray]:
        self._base_acquisition_method()

        single_acquisition_data_size = self.spectrometer_config.single_acquisition_data_size
        number_of_kinetics = self.spectrometer_config.number_of_kinetics
        data_size = single_acquisition_data_size * number_of_kinetics

        data, wavelengths = self._get_acquired_data(data_size)
        data = np.reshape(data, (number_of_kinetics, single_acquisition_data_size))

        return data, wavelengths

    def stop_acquisition(self):
        """
        Stop the current acquisition.
        """
        if _andor_api.ccd.GetStatus() == _andor_api.ccd_error_codes.DRV_ACQUIRING:
            with _andor_api.lock:
                status = _andor_api.ccd.AbortAcquisition()
            _andor_api.log_ccd_response("Aborting acquisition", status)

    @property
    def reach_temperature_before_acquisition(self) -> bool:
        """
        Whether the controller should wait for the target temperature to be reached.
        """
        return self._reach_temperature_before_acquisition

    @reach_temperature_before_acquisition.setter
    @prevent_none_set
    def reach_temperature_before_acquisition(self, value: bool):
        """
        If True, the controller will wait for the target temperature to be reached.
        """
        self._reach_temperature_before_acquisition = value

    def wait_for_target_temperature_if_necessary(self):
        """
        Stay in this method until the target temperature is reached.

        The wait-loop can be broken from another thread if the
        `wait_for_temperature_flag` attribute is set to false.
        """
        if not self.reach_temperature_before_acquisition:
            return

        self.logger.info(f"Waiting for CCD to be cooled down to "
                         f"{self.spectrometer_config.sensor_temperature_set_point} °C.")
        self.wait_for_temperature_flag = True
        acceptable_statuses = [
            _andor_api.ccd_error_codes.DRV_TEMPERATURE_STABILIZED,  # stabilized
            _andor_api.ccd_error_codes.DRV_TEMPERATURE_NOT_STABILIZED,  # reached but not stabilized
            _andor_api.ccd_error_codes.DRV_TEMPERATURE_DRIFT,  # stabilized but drifted since
        ]

        while self.wait_for_temperature_flag:
            with _andor_api.lock:
                status, current_temperature = _andor_api.ccd.GetTemperatureF()

            if status in acceptable_statuses:
                self.logger.info(
                    f'The current temperature is {current_temperature:.1f} °C. '
                    f'The target temperature of {self.spectrometer_config.sensor_temperature_set_point} °C '
                    f'is reached!'
                )
                self.wait_for_temperature_flag = False
                return

            self.logger.info(
                f'The current temperature is {current_temperature:.1f} °C, '
                f'while the target temperature is {self.spectrometer_config.sensor_temperature_set_point} °C.')
            time.sleep(2)

        self.logger.info(f'Waiting for CCD to be cooled down to '
                         f'{self.spectrometer_config.sensor_temperature_set_point} °C is aborted.')

    def stop_waiting_to_reach_temperature(self):
        """
        Stops waiting for the target temperature to be reached.
        """
        if self.wait_for_temperature_flag:
            self.logger.info(f"Stopping waiting for CCD to be cooled down to "
                             f"{self.spectrometer_config.sensor_temperature_set_point} °C.")
            self.wait_for_temperature_flag = False

    def close(self):
        self.stop_acquisition()
        self.stop_waiting_to_reach_temperature()

    def __del__(self):
        self.close()
