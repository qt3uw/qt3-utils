import abc
import inspect
import logging

from typing import Any, Callable, Dict, List, Literal, Set, Tuple, TypeVar, Union

import numpy as np


def get_method_argument_names(method: Callable) -> List[str]:
    """
    Returns a method's argument names.
    """
    return list(inspect.signature(method).parameters.keys())


def filter_only_valid_kwargs_for_method(method: Callable, all_kwargs: dict) -> Dict[str, Any]:
    """
    Filters out kwargs that are not valid for the given method.
    """
    return {k: v for k, v in all_kwargs.items() if k in get_method_argument_names(method)}


class SpectrometerConfig(abc.ABC):
    """
    Base class for spectrometer configurations.

    Subclass this class to control all the spectrometer settings prior to data acquisition.
    For controlling the data acquisition, refer to the `SpectrometerDataAcquisition` abstract class.
    """

    DEVICE_NAME: str = ''
    """ The name of the device used for logging purposes. """

    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        logger_name = f'{self.DEVICE_NAME} Config' if self.DEVICE_NAME != '' else self.__class__.__name__
        self.logger = logging.getLogger(logger_name)

    @abc.abstractmethod
    def open(self) -> None:
        """
        Initializes the connection to devices.
        """
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """
        Terminates connection to devices.
        """
        pass
    
    @property
    @abc.abstractmethod
    def grating_list(self) -> List[str]:
        """
        A list of all installed gratings.
        """
        return []

    @property
    @abc.abstractmethod
    def current_grating(self) -> str:
        """
        Current spectrometer grating.
        """
        return ''

    @current_grating.setter
    @abc.abstractmethod
    def current_grating(self, value: str) -> None:
        """
        Set the spectrometer grating.
        """
        pass
    
    @property
    @abc.abstractmethod
    def center_wavelength(self) -> float:
        """
        The grating center wavelength.
        """
        return np.nan

    @center_wavelength.setter
    @abc.abstractmethod
    def center_wavelength(self, nanometers: float) -> None:
        """
        Sets the grating center wavelength.
        """
        pass
    
    @property
    @abc.abstractmethod
    def starting_wavelength(self) -> float:
        """ 
        The Step and Glue starting wavelength.
        """
        pass

    @starting_wavelength.setter
    @abc.abstractmethod
    def starting_wavelength(self, lambda_min: float) -> None:
        """ 
        Sets the Step and Glue starting wavelength.
        """
        pass
    
    @property
    @abc.abstractmethod
    def ending_wavelength(self) -> float:
        """ 
        The Step and Glue ending wavelength.
        """
        pass

    @ending_wavelength.setter
    @abc.abstractmethod
    def ending_wavelength(self, lambda_max: float) -> None:
        """ 
        Sets the Step and Glue ending wavelength.
        """
        pass
    
    @abc.abstractmethod
    def get_wavelengths(self) -> np.ndarray:
        """
        Returns the wavelength calibration for a single frame.
        """
        pass
    
    @property
    @abc.abstractmethod
    def sensor_temperature_set_point(self) -> float:
        """
        The sensor set-point temperature in Celsius.
        """
        return np.nan

    @sensor_temperature_set_point.setter
    @abc.abstractmethod
    def sensor_temperature_set_point(self, deg_celsius: float) -> None:
        """
        Sets the sensor target temperature in Celsius.
        """
        pass
    
    @property
    @abc.abstractmethod
    def exposure_time(self) -> float:
        """
        Returns the single frame exposure time (in ms).
        """
        return np.nan

    @exposure_time.setter
    @abc.abstractmethod
    def exposure_time(self, ms: float) -> None:
        """
        Sets the single frame exposure time in milliseconds.
        """
        pass

    def __del__(self):
        self.close()


SpectrometerConfigType = TypeVar('SpectrometerConfigType', bound=SpectrometerConfig)


class SpectrometerDataAcquisition(abc.ABC):
    """
    An abstract class for acquiring spectrometer data.

    Subclass this class to control the data acquisition process after configuring the spectrometer.
    For controlling the spectrometer settings, refer to the `SpectrometerConfig` abstract class.

    If you want to add a new acquisition mode
        1. Modify the class constant attribute `ACQUISITION_MODES` to
         include all the possible modes that are accessible with your
         spectrometer.
        2. overwrite the `acquire` method,
        3. within the overwrote method definition, call the old definition
         via super().acquire(...), return the response if it is not None,
        4. and use an if statement for each different mode you implement.

    Since asserting for valid acquisition modes will block
    any usage of unsuuported modes, it is not required to modify
    the respective unsupported acquisition methods, since they will
    never be accessed.

    If you want to remove modes, modify the class
    constant attribute `ACQUISITION_MODES` accordingly.

    For example, if we want to add a mode called 'my-mode'
    and remove modes 'accumulation' and 'kinetic series':

        >>> ACQUISITION_MODES = {'single', 'step-and-glue', 'my-mode'}
        ... def acquire(
        ...    self,
        ... acquisition_mode: Literal['single', 'step-and-glue', 'my-mode'],
        ... **kwargs
        ... ) -> Tuple[np.ndarray, np.ndarray]:
        ... response = super().acquire(acquisition_mode, **kwargs)
        ... if response is not None:
        ...     return response
        ... if acquisition_mode == 'my-mode':
        ...     valid_kwargs = filter_only_valid_kwargs_for_method(self.single_acquisition, kwargs)
        ...     return self.single_acquisition(**valid_kwargs)
    """

    DEVICE_NAME: str = ''
    """ The name of the device used for logging purposes. """

    ACQUISITION_MODES: Set[str] = {'single', 'step-and-glue', 'kinetic series', 'accumulation'}
    """ The supported acquisition modes. """

    def __init__(self, spectrometer_config: SpectrometerConfigType = None):
        """
        Parameters
        ----------
        spectrometer_config : Type[SpectrometerConfigType], optional
            The spectrometer configuration object related to the same spectrometer as this data acquisition object.
            Used in case the acquisition requires using methods defined in the configuration object.
            Defaults to None.
        """
        logging.basicConfig(level=logging.INFO)
        logger_name = f'{self.DEVICE_NAME} Data Acquisition' if self.DEVICE_NAME != '' else self.__class__.__name__
        self.logger = logging.getLogger(logger_name)
        self.spectrometer_config = spectrometer_config

    def acquire(
            self,
            acquisition_mode: Literal['single', 'step-and-glue', 'kinetic series', 'accumulation'],
            **kwargs
    ) -> Union[Tuple[np.ndarray, np.ndarray], None]:
        """
        General method that acquires data depending on the acquisition mode.

        It will raise an error for unsupported acquisition modes.
        Depending on the valid mode provided, it will call the corresponding method.
        You can pass any keyword arguments that are relevant to the method of interest.
        This method will find which of these arguments are accepted by the target method
        and only pass them down, without raising argument errors.

        Parameters
        ----------
        acquisition_mode : Literal['single', 'step-and-glue', 'kinetic series', 'accumulation']
            The acquisition mode.
        **kwargs
            Additional keyword arguments.
        Returns
        -------
        Tuple[np.ndarray, np.ndarray] | None
            The single or multiple spectra and the wavelength array,
            if the mode has a corresponding method defined.
            If the mode is valid, but it is not taken into consideration
            (e.g., user defines a new mode), this method returns None.

        """
        if acquisition_mode not in self.ACQUISITION_MODES:
            raise ValueError(f'Unsupported acquisition mode: {acquisition_mode}')
        if acquisition_mode == 'single':
            valid_kwargs = filter_only_valid_kwargs_for_method(self.single_acquisition, kwargs)
            return self.single_acquisition(**valid_kwargs)
        if acquisition_mode == 'step-and-glue':
            valid_kwargs = filter_only_valid_kwargs_for_method(self.step_and_glue_acquisition, kwargs)
            return self.step_and_glue_acquisition(**valid_kwargs)
        if acquisition_mode == 'kinetic series':
            valid_kwargs = filter_only_valid_kwargs_for_method(self.kinetic_series_acquisition, kwargs)
            return self.kinetic_series_acquisition(**valid_kwargs)
        if acquisition_mode == 'accumulation':
            valid_kwargs = filter_only_valid_kwargs_for_method(self.accumulation_acquisition, kwargs)
            return self.accumulation_acquisition(**valid_kwargs)

    def single_acquisition(self, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """
        Method that acquires a single frame.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            The single-frame spectrum and the wavelength array.
        """
        raise NotImplementedError()

    def step_and_glue_acquisition(self, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """
        Method that acquires a single frame via the step-and-glue method.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            The step-and-glued spectrum and the wavelength array.
        """
        raise NotImplementedError()

    def kinetic_series_acquisition(self, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """
        Method that acquires a series of frames.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            The series of spectra and the wavelength array.
        """
        raise NotImplementedError()

    def accumulation_acquisition(self, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
        """
        Method that acquires a single frame by accumulating multiple single frames and adds them together.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            The average spectrum and the wavelength array.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def stop_acquisition(self) -> None:
        """
        Stop/Pause the current acquisition.
        """
        pass


SpectrometerDataAcquisitionType = TypeVar('SpectrometerDataAcquisitionType', bound=SpectrometerDataAcquisition)
