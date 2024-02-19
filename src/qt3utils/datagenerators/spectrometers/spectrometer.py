import abc
import inspect
import logging

from typing import Any, Callable, Dict, List, Literal, Tuple

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


class Spectrometer(abc.ABC):

    DEVICE_NAME: str = ''
    """ The name of the device used for logging purposes. """

    ACQUISITION_MODES: set[str] = {'single', 'step-and-glue', 'kinetic series', 'accumulation'}
    """ The supported acquisition modes. """

    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.DEVICE_NAME if self.DEVICE_NAME != '' else self.__class__.__name__)

    @abc.abstractmethod
    def open(self) -> None:
        """
        Initializes the connection to devices.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def close(self) -> None:
        """
        Terminates connection to devices.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    @property
    def grating_list(self) -> List[str]:
        """
        A list of all installed gratings.
        """
        return []

    @abc.abstractmethod
    @property
    def current_grating(self) -> str:
        """
        Current spectrometer grating.
        """
        return ''

    @abc.abstractmethod
    @current_grating.setter
    def current_grating(self, value: str) -> None:
        """
        Set the spectrometer grating.
        """
        pass

    @abc.abstractmethod
    @property
    def center_wavelength(self) -> float:
        """
        The grating center wavelength.
        """
        return np.nan

    @abc.abstractmethod
    @center_wavelength.setter
    def center_wavelength(self, nanometers: float) -> None:
        """
        Sets the grating center wavelength.
        """
        pass

    @abc.abstractmethod
    def get_wavelengths(self) -> np.ndarray:
        """
        Returns the wavelength calibration for a single frame.
        """
        pass

    @abc.abstractmethod
    @property
    def sensor_temperature_set_point(self) -> float:
        """
        The sensor set-point temperature in Celsius.
        """
        return np.nan

    @abc.abstractmethod
    @sensor_temperature_set_point.setter
    def sensor_temperature_set_point(self, deg_celsius: float) -> None:
        """
        Sets the sensor target temperature in Celsius.
        """
        pass

    @abc.abstractmethod
    @property
    def exposure_time(self) -> float:
        """
        Returns the single frame exposure time (in ms).
        """
        return np.nan

    @abc.abstractmethod
    @exposure_time.setter
    def exposure_time(self, ms: float) -> None:
        """
        Sets the single frame exposure time in milliseconds.
        """
        pass

    @property
    def clock_rate(self) -> float:
        """
        The clock rate of a single exposure (1/exposure_time in Hz).
        """
        try:
            _t = self.exposure_time / 1000.0  # Converting from milliseconds to seconds.
        except Exception as e:
            self.logger.error(e)
            _t = 2
        return 1.0 / _t

    def acquire(
            self,
            acquisition_mode: Literal['single', 'step-and-glue', 'kinetic series', 'accumulation'],
            **kwargs
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        General method that acquires data depending on the acquisition mode.
        If you want to add a new mode, overwrite this method, call it via super().acquire(...) and then
        use an if statement for each different mode you implemented.

        Parameters
        ----------
        acquisition_mode : Literal['single', 'step-and-glue', 'kinetic series', 'accumulation']
            The acquisition mode.
        **kwargs
            Additional keyword arguments.
        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            The single or multiple spectra and the wavelength array.
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
        raise NotImplementedError()

    def __del__(self):
        self.close()

