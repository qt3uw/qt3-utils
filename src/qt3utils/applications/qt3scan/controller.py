import json
import logging
import pickle
import time
import tkinter as tk
from typing import Tuple

import h5py
import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from qt3utils.applications.qt3scan.interface import (
    QT3ScanDAQControllerInterface,
    QT3ScanCounterDAQControllerInterface,
    QT3ScanPositionControllerInterface,
    QT3ScanSpectrometerDAQControllerInterface,
)

import qt3utils.datagenerators
from qt3utils.errors import convert_nidaq_daqnotfounderror, QT3Error

matplotlib.use('Agg')

module_logger = logging.getLogger(__name__)
module_logger.setLevel(logging.ERROR)


def weighted_mean_wavelength(wavelengths, spectra):
    """
    Calculates the mean wavelength for each x, y coordinate weighted by the counts.

    Args:
    spectra: A 3D numpy array containing the spectra data, where the first two
             dimensions represent the x and y coordinates and the third dimension
             represents the wavelengths.

    Returns:
    A 2D numpy array containing the mean wavelength for each x, y coordinate.
    """
    # Check if 3D array
    if len(spectra.shape) != 3:
        raise ValueError("Input data must be a 3D numpy array.")

    # Get number of dimensions (x, y, wavelengths)
    x_dim, y_dim, wavelength_dim = spectra.shape

    # Initialize array for mean wavelengths
    mean_wavelengths = np.zeros((x_dim, y_dim))

    # Loop over each x,y coordinate
    for x in range(x_dim):
        for y in range(y_dim):
            # Extract spectrum for current coordinate
            spectrum = spectra[x, y, :]

            # Calculate weighted mean using counts as weights
            try:
                mean_wavelengths[x, y] = np.average(wavelengths, weights=spectrum)
            except ZeroDivisionError:
                # Avoids error if filtered range is off the available wavelength limits
                # and there are no data to be processed
                mean_wavelengths[x, y] = np.nan

    return mean_wavelengths


# If we need to implement this for more than a single axis, we need to use the np.apply_over_axes method,
# and also make sure to take into account the number of axes and the number of count axes (though, it should be 1?)
# I guess if we have multidimensional axes (e.g. wavelength and number of frames), we need to aggregate that too.
STANDARD_COUNT_AGGREGATION_METHODS = {
    'Counts-Sum': lambda _, data: np.sum(data, axis=-1),
    'Counts-Mean': lambda _, data: np.mean(data, axis=-1),
    'Counts-Max': lambda _, data: np.max(data, axis=-1),
    'Counts-Min': lambda _, data: np.min(data, axis=-1),
    'Axes-Weighted-Mean': lambda params, data: weighted_mean_wavelength(params, data),
    'Axes-ArgMax': lambda params, data: params[np.argmax(data, axis=-1)],
    'Axes-ArgMin': lambda params, data: params[np.argmin(data, axis=-1)],
}


class QT3ScanConfocalApplicationController:
    """
    Implements qt3utils.applications.qt3scan.interface.QT3ScanApplicationControllerInterface

    Note that the DAQ controller here must implement QT3ScanCounterDAQControllerInterface
    """

    def __init__(self,
                 position_controller: QT3ScanPositionControllerInterface,
                 daq_controller: QT3ScanCounterDAQControllerInterface,
                 logger_level: int) -> None:

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.daq_and_scanner = qt3utils.datagenerators.CounterAndScanner(daq_controller, position_controller)
        self.data_clock_rate = None
        self.data_configs = {'DAQ': None, 'Scanner': None}
        self.data_saved_once = False

    @property
    def step_size(self) -> float:
        return self.daq_and_scanner.step_size

    @step_size.setter
    def step_size(self, value):
        self.daq_and_scanner.step_size = value

    @property
    def scanned_count_rate(self) -> np.ndarray:
        return self.daq_and_scanner.scanned_count_rate

    @property
    def scanned_raw_counts(self) -> np.ndarray:
        return self.daq_and_scanner.scanned_raw_counts

    @property
    def position_controller(self) -> QT3ScanPositionControllerInterface:
        return self.daq_and_scanner.stage_controller

    @property
    def daq_controller(self) -> QT3ScanDAQControllerInterface:
        return self.daq_and_scanner.rate_counter

    @property
    def xmin(self) -> float:
        return self.daq_and_scanner.xmin

    @property
    def xmax(self) -> float:
        return self.daq_and_scanner.xmax

    @property
    def ymin(self) -> float:
        return self.daq_and_scanner.ymin

    @property
    def ymax(self) -> float:
        return self.daq_and_scanner.ymax

    @property
    def current_y(self) -> float:
        return self.daq_and_scanner.current_y

    @convert_nidaq_daqnotfounderror(module_logger)
    def start(self) -> None:
        self.data_clock_rate = self.daq_controller.clock_rate
        self.data_configs['DAQ'] = self.daq_controller.last_config_dict
        self.data_configs['Scanner'] = self.position_controller.last_config_dict
        self.daq_and_scanner.start()

    @convert_nidaq_daqnotfounderror(module_logger)
    def stop(self) -> None:
        self.daq_and_scanner.stop()

    @convert_nidaq_daqnotfounderror(module_logger)
    def post_stop(self) -> None:
        self.daq_and_scanner.post_stop()

    @convert_nidaq_daqnotfounderror(module_logger)
    def reset(self) -> None:
        self.daq_and_scanner.reset()
        self.data_clock_rate = None
        self.data_configs = {'DAQ': None, 'Scanner': None}
        self.data_saved_once = False

    @convert_nidaq_daqnotfounderror(module_logger)
    def set_to_starting_position(self) -> None:
        self.daq_and_scanner.set_to_starting_position()

    def still_scanning(self) -> bool:
        return self.daq_and_scanner.still_scanning()

    @convert_nidaq_daqnotfounderror(module_logger)
    def scan_x(self) -> None:
        self.daq_and_scanner.scan_x()

    @convert_nidaq_daqnotfounderror(module_logger)
    def move_y(self) -> None:
        self.daq_and_scanner.move_y()

    @convert_nidaq_daqnotfounderror(module_logger)
    def optimize_position(
            self, axis: str,
            central: float,
            range: float,
            step_size: float
    ) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        """
        The returned tuple elements should be:
        0th: np.ndarray of count rates across the axis
        1st: np.ndarray of axix positions (same length as 0, example: 31.5, 32, 32.5, ... 38.5, 39 )
        2nd: float of the position of the maximum count rate
        3rd: np.ndarray of the fit coefficients (C, mu, sigma, offset) that describe the best-fit gaussian shape to the raw_data
        """
        return self.daq_and_scanner.optimize_position(axis, central, range, step_size)

    def set_scan_range(self, xmin: float, xmax: float, ymin: float, ymax: float) -> None:
        self.daq_and_scanner.set_scan_range(xmin, xmax, ymin, ymax)

    def get_completed_scan_range(self) -> Tuple[float, float, float, float]:
        return self.daq_and_scanner.get_completed_scan_range()

    @staticmethod
    def allowed_file_save_formats() -> list:
        """
        Returns a list of tuples of the allowed file save formats
            [(description, file_extension), ...]
        """
        formats = [('Compressed Numpy MultiArray', '*.npz'), ('Numpy Array (count rate only)', '*.npy'),
                   ('HDF5', '*.h5')]
        return formats

    @staticmethod
    def default_file_format() -> str:
        """
        Returns the default file format
        """
        return '.npz'

    def save_scan(self, afile_name) -> None:
        file_type = afile_name.split('.')[-1]

        data = dict(
            scan_range=self.get_completed_scan_range(),
            raw_counts=self.daq_and_scanner.scanned_raw_counts,
            count_rate=self.daq_and_scanner.scanned_count_rate,
            step_size=self.daq_and_scanner.step_size,
            daq_clock_rate=self.data_clock_rate,
            daq_config=self.data_configs['DAQ'],
            scanner_config=self.data_configs['Scanner'],
        )

        if file_type == 'npy':
            np.save(afile_name, data['count_rate'])

        elif file_type == 'npz':
            np.savez_compressed(afile_name, **data)

        elif file_type == 'h5':
            h5file = h5py.File(afile_name, 'w')
            for key, value in data.items():
                if key not in ['daq_config', 'scanner_config']:
                    h5file.create_dataset(key, data=value)
                else:
                    h5file.attrs[key] = json.dumps(value)
            h5file.close()
        else:
            return
        self.data_saved_once = True

    def load_scan(self, afile_name):
        file_type = afile_name.split('.')[-1]

        if file_type == 'npy':
            logging.error('Filetype "npy" is not supported for loading scans.')
            return
        elif file_type == 'npz':
            data_dict = dict(np.load(afile_name, allow_pickle=True))
            for key, value in data_dict.items():
                if len(value.shape) == 0:
                    data_dict[key] = value[()]
        elif file_type == 'h5':
            with h5py.File(afile_name, 'r') as h5file:
                data_dict = {}
                for key in h5file.keys():
                    try:
                        data_dict[key] = h5file[key][:]
                    except ValueError:
                        data_dict[key] = h5file[key][()]
                for key, value in dict(h5file.attrs).items():
                    data_dict[key] = json.loads(value)
        elif file_type == 'pkl':
            with open(afile_name, 'rb') as f:
                data_dict = pickle.load(f)

        self.daq_and_scanner.scanned_raw_counts = data_dict.get('raw_counts', [])
        self.daq_and_scanner.scanned_count_rate = data_dict.get('count_rate', [])
        (self.daq_and_scanner.xmin, self.daq_and_scanner.xmax,
         self.daq_and_scanner.ymin, self.daq_and_scanner.current_y) = \
            data_dict.get('scan_range', (
                self.position_controller.minimum_allowed_position,
                self.position_controller.maximum_allowed_position,
                self.position_controller.minimum_allowed_position,
                self.position_controller.maximum_allowed_position)
                          )
        self.daq_and_scanner.step_size = data_dict.get('step_size', 0.5)
        self.daq_and_scanner.ymax = self.daq_and_scanner.current_y - self.daq_and_scanner.step_size
        self.data_clock_rate = data_dict.get('daq_clock_rate', None)
        self.data_configs['DAQ'] = data_dict.get('daq_config', None)
        self.data_configs['Scanner'] = data_dict.get('scanner_config', None)
        self.data_saved_once = False

    def scan_image_rightclick_event(self, event: MouseEvent, index_x: int, index_y: int) -> None:
        """
        This method is called when the user right clicks on the scan image.
        """
        self.logger.debug(f"scan_image_rightclick_event. click at {event.xdata}, {event.ydata}")


class QT3ScanHyperSpectralApplicationController:
    """
     Implements qt3utils.applications.qt3scan.interface.QT3ScanApplicationControllerInterface

     For HyperSpectral imaging, the daq_controller object will be a spectrometer that
     acquires a spectrum at each position in the scan.

     Note that the DAQ controller here must implement QT3ScanSpectrometerDAQControllerInterface
    """

    def __init__(
            self,
            position_controller: QT3ScanPositionControllerInterface,
            daq_controller: QT3ScanSpectrometerDAQControllerInterface,
            logger_level: int
    ) -> None:

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self._daq_controller = daq_controller
        self._position_controller = position_controller

        self.running = False
        self._current_y = 0
        self._ymin = self.position_controller.minimum_allowed_position
        self._ymax = self.position_controller.maximum_allowed_position
        self._xmin = self.position_controller.minimum_allowed_position
        self._xmax = self.position_controller.maximum_allowed_position

        self._step_size = 0.5
        self.raster_line_pause = 0.150  # wait 150ms for the piezo stage to settle before a line scan
        self._filter_view_range = (-np.inf, np.inf)
        self._counts_aggregation_option = list(STANDARD_COUNT_AGGREGATION_METHODS.keys())[0]

        self.hyper_spectral_raw_data = None  # is there way to create a "default numpy array", similar a 'default dict'?
        self.hyper_spectral_wavelengths = None
        self.data_clock_rate = None
        self.data_configs = {'DAQ': None, 'Scanner': None}
        self.data_saved_once = False

    @property
    def step_size(self) -> float:
        return self._step_size

    @step_size.setter
    def step_size(self, value: float):
        self._step_size = value

    @property
    def scanned_count_rate(self) -> np.ndarray:
        if not self.counts_aggregation_option.startswith('Axes'):
            return self.scanned_raw_counts * self.daq_controller.clock_rate
        else:
            return self.scanned_raw_counts

    @property
    def filter_view_range(self) -> Tuple[float, float]:
        return self._filter_view_range

    @filter_view_range.setter
    def filter_view_range(self, value: Tuple[float, float]):

        filter_min = value[0]
        filter_max = value[1]
        if filter_min > filter_max:
            filter_min, filter_max = filter_max, filter_min

        if self.hyper_spectral_wavelengths is not None:
            error_occurred = False

            min_allowed_filter_difference = 1.001 * np.max(np.diff(self.hyper_spectral_wavelengths))
            filter_difference = filter_max - filter_min
            if filter_difference < min_allowed_filter_difference:
                self.logger.error(f"Filter range difference {filter_difference} is larger than "
                                  f"the smallest allowed value {min_allowed_filter_difference}.")
                error_occurred = True

            wl_min = np.min(self.hyper_spectral_wavelengths)
            wl_max = np.max(self.hyper_spectral_wavelengths)
            if filter_max < wl_min:
                self.logger.error(f"Filter maximum {filter_max} is smaller than "
                                  f"the smallest available wavelength {wl_min}.")
                error_occurred = True
            if filter_min > wl_max:
                self.logger.error(f"Filter minimum {filter_min} is larger than "
                                  f"the largest available wavelength {wl_max}.")
                error_occurred = True
            if error_occurred:
                self.logger.error(f'Filter will stay as {self.filter_view_range}.')
                return

        self._filter_view_range = filter_min, filter_max
        self.logger.debug(f'Filter Range changed to {self.filter_view_range}.')

    @property
    def counts_aggregation_option(self):
        return self._counts_aggregation_option

    @counts_aggregation_option.setter
    def counts_aggregation_option(self, value: str):
        valid_values = tuple(STANDARD_COUNT_AGGREGATION_METHODS.keys())
        if value in valid_values:
            self._counts_aggregation_option = value
            self.logger.debug(f'Counts aggregation option changed to {value}.')
        else:
            self.logger.error(f'Counts aggregation option "{value}", not in list of valid values {valid_values}.')

    @property
    def counts_aggregation_method(self):
        return STANDARD_COUNT_AGGREGATION_METHODS[self.counts_aggregation_option]

    @property
    def scanned_raw_counts(self) -> np.ndarray:
        if self.hyper_spectral_raw_data is not None:
            wl_min, wl_max = min(self.filter_view_range), max(self.filter_view_range)
            wls = self.hyper_spectral_wavelengths
            data_in_range = self.hyper_spectral_raw_data[:, :, (wls >= wl_min) & (wls <= wl_max)]
            wls_in_range = wls[(wls >= wl_min) & (wls <= wl_max)]
            return self.counts_aggregation_method(wls_in_range, data_in_range)
        else:
            return np.array([])

    @property
    def position_controller(self) -> QT3ScanPositionControllerInterface:
        return self._position_controller

    @property
    def daq_controller(self) -> QT3ScanDAQControllerInterface:
        return self._daq_controller

    @property
    def xmin(self) -> float:
        return self._xmin

    @property
    def xmax(self) -> float:
        return self._xmax

    @property
    def ymin(self) -> float:
        return self._ymin

    @property
    def ymax(self) -> float:
        return self._ymax

    @property
    def current_y(self) -> float:
        return self._current_y

    def start(self) -> None:
        """
        This method is used to start the scan over the scan range. It should prepare the hardware to
        begin acquistion of data.
        """
        self.running = True
        self.data_clock_rate = self.daq_controller.clock_rate
        self.data_configs['DAQ'] = self.daq_controller.last_config_dict
        self.data_configs['Scanner'] = self.position_controller.last_config_dict
        self.daq_controller.start()

    def stop(self) -> None:
        """
        This method is used to stop the scan. It should stop the scanning loop.
        """
        self.running = False

    def post_stop(self) -> None:
        """
        This method is called after the scan is stopped.
        It should do the necessary cleanup.
        For example, it should stop the DAQ.
        """
        self.daq_controller.stop()

    def reset(self) -> None:
        """
        Resets internal data structure. NB: this blows away any previously stored data.
        """
        self.hyper_spectral_raw_data = None
        self.hyper_spectral_wavelengths = None
        self.data_clock_rate = None
        self.data_configs = {'DAQ': None, 'Scanner': None}
        self.data_saved_once = False

    def set_to_starting_position(self) -> None:
        self._current_y = self.ymin
        self.position_controller.go_to_position(x=self.xmin, y=self.ymin)

    def still_scanning(self) -> bool:
        if self.running is False:  # this allows external process to stop scan
            return False

        if self.current_y <= self.ymax:  # stops scan when reaches final position
            return True
        else:
            self.running = False
            return False

    def scan_x(self):
        """
        Scans the x axis from xmin to xmax in steps of step_size.
        """
        raw_counts_for_axis, wavelengths = (
            self.scan_axis('x', self.xmin, self.xmax, self.step_size)
        )
        # raw_counts_for_axis is of shape (N steps, M spectrum size)
        # wavelengths is of shape (M spectrum size,)
        assert len(wavelengths) == raw_counts_for_axis.shape[-1]

        # rehape raw_counts to
        # (1, N, M)
        raw_counts_for_axis = raw_counts_for_axis.reshape(1, len(raw_counts_for_axis), -1)

        if self.hyper_spectral_raw_data is None:
            self.hyper_spectral_raw_data = raw_counts_for_axis
            self.logger.debug(f'Creating new hyperspectral array of shape: {self.hyper_spectral_raw_data.shape}')
        else:
            if self.hyper_spectral_raw_data.shape[-1] != raw_counts_for_axis.shape[-1]:
                raise QT3Error("Inconsistent spectrum size obtained during scan_x! Check your hardware."
                               f"expected shape[-1] {self.hyper_spectral_raw_data.shape[-1]}. found {raw_counts_for_axis.shape[-1]}")

            self.hyper_spectral_raw_data = np.vstack((self.hyper_spectral_raw_data, raw_counts_for_axis))

        if self.hyper_spectral_wavelengths is None:
            self.hyper_spectral_wavelengths = wavelengths

        if np.array_equal(self.hyper_spectral_wavelengths, wavelengths) is False:
            raise QT3Error("Inconsistent wavelength array obtained during scan_x! Check your hardware.")

    def scan_axis(self, axis, min, max, step_size) -> Tuple[np.ndarray, np.ndarray]:
        """
        Moves the microscope along the specified axis from min to max in steps of step_size.
        Returns a tuple of two numpy arrays
        The first numpy array is the raw spectrum from the scan in the shape
        (N, M) where N is the number of positions along the axis and M
        is the size of the spectrum
        The second numpy array is an array of wavelength values for the spectrum of shape (M,)
        """
        spectrums_in_scan = []

        # we use these to check the returned spectrum
        # and wavelength array for consistency.
        # we also currently do not support the
        # values of the wavelengths changing for each position
        # that is, the spectrometer must scan over the same set of wavelengths each time.
        wavelength_array = None
        initial_spectrum_size = None

        self.position_controller.go_to_position(**{axis: min})
        time.sleep(self.raster_line_pause)

        for val in np.arange(min, max + step_size, step_size):
            self.position_controller.go_to_position(**{axis: val})
            measured_spectrum, measured_wavelengths = self.daq_controller.sample_spectrum()

            if initial_spectrum_size is None:
                initial_spectrum_size = len(measured_spectrum)
            if wavelength_array is None:
                wavelength_array = measured_wavelengths

            if initial_spectrum_size != len(measured_spectrum):
                raise QT3Error("Inconsistent spectrum size obtained during scan! Check your hardware.")
            if initial_spectrum_size != len(measured_wavelengths):
                raise QT3Error("Inconsistent wavelength array size obtained during scan! Check your hardware.")
            if len(measured_spectrum) != len(measured_wavelengths):
                raise QT3Error(
                    "Inconsistent wavelength array and spectrum size obtained during scan! Check your hardware.")
            if np.array_equal(wavelength_array, measured_wavelengths) is False:
                raise QT3Error("Inconsistent wavelength array obtained during scan! Check your hardware.")
            spectrums_in_scan.append(measured_spectrum)

        return np.array(spectrums_in_scan), wavelength_array

    def move_y(self) -> None:
        if self.current_y <= self.ymax:
            self._current_y += self.step_size
        try:
            self.position_controller.go_to_position(y=self.current_y)
        except ValueError as e:
            self.logger.info(f'move y: out of range\n\n{e}')

    def optimize_position(
            self, axis: str,
            central: float,
            range: float,
            step_size: float
    ) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        """
        Performs a scan over a particular axis about `center_position`.

        The scan ranges from center_position +- width and progresses with step_size.

        Returns a tuple of
           (raw_data, axis_positions, optimal_position, fit_coeff)

        where
           raw_data is an array of count rates at each position
           axis_positions is an array of position values along the specified axis
           optimal_position is a float position that represents the brightest position along the scan
           fit_coeff is an array of coefficients (C, mu, sigma) that describe
                 the best-fit gaussian shape to the raw_data
                 C * np.exp( -(raw_data-mu)**2 / (2.*sigma**2) )
        example:
           ([r0, r1, ...], [x0, x1, ...], x_optimal, [C, mu, sigma])

        In cases where the data cannot be successfully fit to a gaussian function,
        the optimal_position returned is the absolute brightest position in the scan,
        and the fit_coeff is set to None.
        When the fit is successful, x_optimal = mu.

        """
        import scipy
        def gauss(x, *p):
            C, mu, sigma, offset = p
            return C * np.exp(-(x - mu) ** 2 / (2. * sigma ** 2)) + offset

        min_val = central - range
        max_val = central + range
        if self.position_controller:
            min_val = np.max([min_val, self.position_controller.minimum_allowed_position])
            max_val = np.min([max_val, self.position_controller.maximum_allowed_position])

        self.start()
        raw_data, wavelengths = self.scan_axis(axis, min_val, max_val, step_size)
        self.stop()
        self.post_stop()
        axis_vals = np.arange(min_val, max_val + step_size, step_size)

        wl_min, wl_max = min(self.filter_view_range), max(self.filter_view_range)
        raw_data_in_range = raw_data[:, (wavelengths >= wl_min) & (wavelengths <= wl_max)]
        wls_in_range = wavelengths[(wavelengths >= wl_min) & (wavelengths <= wl_max)]
        count_rates = self.counts_aggregation_method(wls_in_range, raw_data_in_range)
        if not self.counts_aggregation_option.startswith('Axes'):
            count_rates *= self.data_clock_rate

        optimal_position = axis_vals[np.argmax(count_rates)]
        coeff = None
        params = [np.max(count_rates), optimal_position, 1.0, np.min(count_rates)]
        bounds = ((0, -np.inf, 0, 0), (np.inf, np.inf, np.inf, np.inf))
        try:
            coeff, var_matrix = scipy.optimize.curve_fit(gauss, axis_vals, count_rates, p0=params, bounds=bounds)
            optimal_position = coeff[1]
            # ensure that the optimal position is within the scan range
            optimal_position = np.max([min_val, optimal_position])
            optimal_position = np.min([max_val, optimal_position])
        except RuntimeError as e:
            self.logger.warning(e)

        return count_rates, axis_vals, optimal_position, coeff

    def set_scan_range(self, xmin: float, xmax: float, ymin: float, ymax: float) -> None:
        """
        This method is used to set the scan range and is called in qt3scan.main
        """
        self.position_controller.check_allowed_position(xmin, ymin)
        self.position_controller.check_allowed_position(xmax, ymax)

        self._ymin = ymin
        self._ymax = ymax
        self._xmin = xmin
        self._xmax = xmax

    def get_completed_scan_range(self) -> Tuple[float, float, float, float]:
        """
        Returns a tuple of the scan range that has been completed
        :return: xmin, xmax, ymin, current_y
        """
        return self.xmin, self.xmax, self.ymin, self.current_y

    def save_scan(self, afile_name) -> None:
        file_type = afile_name.split('.')[-1]

        data = dict(
            wavelengths=self.hyper_spectral_wavelengths,
            hyperspectral_image=self.hyper_spectral_raw_data,
            scan_range=self.get_completed_scan_range(),
            raw_counts=self.scanned_raw_counts,
            count_rate=self.scanned_count_rate,
            step_size=self.step_size,
            daq_clock_rate=self.data_clock_rate,
            filter_range=self.filter_view_range,
            counts_aggregation_option=self.counts_aggregation_option,
            daq_config=self.data_configs['DAQ'],
            scanner_config=self.data_configs['Scanner']
        )

        if file_type == 'npy':
            np.save(afile_name, data['count_rate'])

        elif file_type == 'npz':
            np.savez_compressed(afile_name, **data)

        elif file_type == 'h5':
            with h5py.File(afile_name, 'w') as h5file:
                for key, value in data.items():
                    if key not in ['daq_config', 'scanner_config']:
                        h5file.create_dataset(key, data=value)
                    else:
                        h5file.attrs[key] = json.dumps(value)

        elif file_type == 'pkl':
            with open(afile_name, 'wb') as f:
                pickle.dump(data, f)
        else:
            return

        self.data_saved_once = True

    def load_scan(self, afile_name):
        file_type = afile_name.split('.')[-1]

        if file_type == 'npy':
            logging.error('Filetype "npy" is not supported for loading scans.')
            return
        elif file_type == 'npz':
            data_dict = dict(np.load(afile_name, allow_pickle=True))
            for key, value in data_dict.items():
                if len(value.shape) == 0:
                    data_dict[key] = value[()]
        elif file_type == 'h5':
            with h5py.File(afile_name, 'r') as h5file:
                data_dict = {}
                for key in h5file.keys():
                    try:
                        data_dict[key] = h5file[key][:]
                    except ValueError:
                        data_dict[key] = h5file[key][()]
                for key, value in dict(h5file.attrs).items():
                    data_dict[key] = json.loads(value)
        elif file_type == 'pkl':
            with open(afile_name, 'rb') as f:
                data_dict = pickle.load(f)

        self.hyper_spectral_wavelengths = data_dict.get('wavelengths', None)
        self.hyper_spectral_raw_data = data_dict.get('hyperspectral_image', None)
        self._xmin, self._xmax, self._ymin, self._current_y = \
            data_dict.get('scan_range', (
                self.position_controller.minimum_allowed_position,
                self.position_controller.maximum_allowed_position,
                self.position_controller.minimum_allowed_position,
                self.position_controller.maximum_allowed_position)
                          )
        self._step_size = data_dict.get('step_size', 0.5)
        self._ymax = self.current_y - self.step_size
        self.data_clock_rate = data_dict.get('daq_clock_rate', None)
        self.filter_view_range = data_dict.get('filter_range', (-np.inf, np.inf))
        self.counts_aggregation_option = (
            data_dict.get('counts_aggregation_option', list(STANDARD_COUNT_AGGREGATION_METHODS.keys())[0]))
        self.data_configs['DAQ'] = data_dict.get('daq_config', None)
        self.data_configs['Scanner'] = data_dict.get('scanner_config', None)
        self.data_saved_once = True

    @staticmethod
    def allowed_file_save_formats() -> list:
        """
        Returns a list of tuples of the allowed file save formats
            [(description, file_extension), ...]
        """
        formats = [('Compressed Numpy MultiArray', '*.npz'),
                   ('Numpy Array (count rate only)', '*.npy'),
                   ('HDF5', '*.h5'),
                   ('Pickle', '*.pkl'),
                   ]
        return formats

    @staticmethod
    def default_file_format() -> str:
        """
        Returns the default file format
        """
        return '.npz'

    def scan_image_rightclick_event(self, event: MouseEvent, index_x: int, index_y: int) -> None:
        """
        This method is called when the user right-clicks on the scan image.
        """
        self.logger.debug(f"Mouse Event {event}")

        if event.xdata is None or event.ydata is None:
            return

        win = tk.Toplevel()
        win.title(f'Spectrum for location (x,y): {np.round(event.xdata, 4)}, {np.round(event.ydata, 4)}')
        fig, ax = plt.subplots()
        ax: plt.Axes
        ax.set_xlabel('Wavelength (nm)')
        ax.set_ylabel('Counts / bin')

        self.logger.debug(
            f'Selecting {index_y}, {index_x} from hyper spectral array of shape {self.hyper_spectral_raw_data.shape}')
        selected_spectrum = self.hyper_spectral_raw_data[index_y, index_x, :]

        ax.plot(self.hyper_spectral_wavelengths, selected_spectrum, label='data')
        ax.grid(True)

        min_range, max_range = self.filter_view_range
        if not (min_range == -np.inf and max_range == np.inf):
            if min_range == -np.inf:
                min_range = np.min(self.hyper_spectral_wavelengths)
            if max_range == np.inf:
                max_range = np.max(self.hyper_spectral_wavelengths)

            # ax.axvline(min_range, color='k', linestyle='--')
            # ax.axvline(max_range, color='k', linestyle='--')
            ax.axvspan(min_range, max_range, alpha=0.1, color='k')

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas.draw()
