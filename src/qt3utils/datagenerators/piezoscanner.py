import time
import logging
import threading
from typing import Union, Callable

import numpy as np
import scipy.optimize

logger = logging.getLogger(__name__)

def gauss(x, *p):
    C, mu, sigma, offset = p
    return C*np.exp(-(x-mu)**2/(2.*sigma**2)) + offset


class CounterAndScanner:
    def __init__(self, rate_counter, position_controller, hyper_data_acquisition_function: Callable = None):
        """

        :param rate_counter: a RateCounter object
        :param position_controller: a position controller object such as nipiezojenapy.BaseControl or PiezoControl
        :param hyper_data_acquisition_function: a function is called at each position of the scan

        Notes on hyper_data_acquisition_function:

        This function must have an attribute "in_parallel" that is True or False.
        It must store its own data if generated

        The function will be passed a copy of this CounterAndScanner object as the argument, from which the caller
        can extract the current position and other information that may be desired.

        If the function's "in_parallel" attribute is True, then the function will be called in a separate thread.
        This is useful, for example, if the spectrometer is being used to acquire data at each position.
        Both the spectrometer and the rate counter will acquire data simultaneously.

        If the function uses NiDAQ or any of the other hardware also used during a scan, then "in_parallel" must be
        False. Otherwise, both the scan and the function will be trying to use the same hardware simultaneously.

        """
        self.running = False
        self.ymin = 0.0
        self.ymax = 80.0
        self.xmin = 0.0
        self.xmax = 80.0
        self.step_size = 0.5
        self.raster_line_pause = 0.150  # wait 150ms for the piezo actuator to settle before a line scan

        self.scanned_raw_counts = []
        self.scanned_count_rate = []

        self.position_controller = position_controller
        self.rate_counter = rate_counter
        self.num_daq_batches = 1  # could change to 10 if want 10x more samples for each position

        self.hyper_data_acquisition_function = None
        self.set_hyper_data_acquisition_function(hyper_data_acquisition_function)

    def set_hyper_data_acquisition_function(self, hyper_data_acquisition_function: Callable):
        """
        Sets the function that is called at each position of the scan

        This function must have an attribute "in_parallel" that is True or False.
        If no attribute is provided, then it is assumed to be False.

        It must store its own data if generated

        The function will be passed a copy of this CounterAndScanner object as the argument, from which the caller
        can extract the current position and other information that may be desired.

        If the function's "in_parallel" attribute is True, then the function will be called in a separate thread.
        This is useful, for example, if the spectrometer is being used to acquire data at each position.
        Both the spectrometer and the rate counter will acquire data simultaneously.

        If the function uses NiDAQ or any of the other hardware also used during a scan, then "in_parallel" must be
        False. Otherwise, both the scan and the function will be trying to use the same hardware simultaneously.
        """
        self.hyper_data_acquisition_function = hyper_data_acquisition_function
        if self.hyper_data_acquisition_function is not None:
            if hasattr(self.hyper_data_acquisition_function, 'in_parallel') is False:
                logger.warning('hyper_data_acquisition_function does not have the attribute "in_parallel"')
                logger.warning('setting hyper_data_acquisition_function.in_parallel = False')
                self.hyper_data_acquisition_function.in_parallel = False

    def stop(self):
        self.rate_counter.stop()
        self.running = False

    def start(self):
        self.running = True
        self.rate_counter.start()

    def set_to_starting_position(self):
        """
        Move the actuator to the starting position (xmin, ymin)
        """
        self.position_controller.go_to_position(x=self.xmin, y=self.ymin)

    def close(self):
        self.rate_counter.close()

    def set_num_data_samples_per_batch(self, N):
        self.rate_counter.num_data_samples_per_batch = N

    def sample_counts(self):
        return self.rate_counter.sample_counts(self.num_daq_batches)

    def sample_count_rate(self, data_counts=None):
        if data_counts is None:
            data_counts = self.sample_counts()
        return self.rate_counter.sample_count_rate(data_counts)

    def set_scan_range(self, xmin, xmax, ymin, ymax):
        """
        Sets the scan range
        """
        self.position_controller.check_allowed_position(xmin, ymin)
        self.position_controller.check_allowed_position(xmax, ymax)

        self.ymin = ymin
        self.ymax = ymax
        self.xmin = xmin
        self.xmax = xmax

    def get_scan_range(self) -> tuple:
        """
        Returns a tuple of the full scan range
        :return: xmin, xmax, ymin, ymax
        """
        return self.xmin, self.xmax, self.ymin, self.ymax

    def get_current_position(self, axis=None, use_last_write_values=True) -> Union[dict, float]:
        """
        Returns the last position written to the actuator controller.

        This is the CURRENT position of the actuator.

        :param axis: 'x', 'y', or 'z'. If None, returns a dict of all axes
        :param use_last_write_values: if True, then the last position written to the actuator controller is returned.
            otherwise, the current position is returned as determined by the read voltages from the actuator controller.

        :return: dict of x, y, z positions or a single float of the position of the specified axis
        """
        if use_last_write_values:
            position = dict(zip(['x', 'y', 'z'], self.position_controller.last_write_values))
        else:
            position = dict(zip(['x', 'y', 'z'], self.position_controller.get_position()))

        if axis is None:
            return position
        else:
            return position[axis]

    def get_completed_scan_range(self) -> tuple:
        """
        Returns a tuple of the scan range that has been completed
        :return: xmin, xmax, ymin, get_current_position('y')
        """
        return self.xmin, self.xmax, self.ymin, self.get_current_position('y')

    def _still_scanning(self):
        if self.running == False:  # this allows external process to stop scan
            return False

        if self.get_current_position('y') < self.ymax:  # stops scan when reaches final position
            return True
        else:
            self.running = False
            return False

    def _move_y(self):
        if self.get_current_position('y') + self.step_size <= self.ymax:
            try:
                self.position_controller.go_to_position(y=self.get_current_position('y') + self.step_size)
            except ValueError as e:
                logger.info(f'out of range\n\n{e}')

    def _scan_x(self):
        """
        Scans the x axis from xmin to xmax in steps of step_size.

        Stores results in self.scanned_raw_counts and self.scanned_count_rate.
        """
        raw_counts_for_axis = self._scan_axis('x', self.xmin, self.xmax, self.step_size,
                                              hyper_data_acquisition_function=self.hyper_data_acquisition_function)
        self.scanned_raw_counts.append(raw_counts_for_axis)
        self.scanned_count_rate.append([self.sample_count_rate(raw_counts) for raw_counts in raw_counts_for_axis])

    def _scan_axis(self, axis, min, max, step_size, hyper_data_acquisition_function=None):
        """
        Moves the actuator along the specified axis from min to max in steps of step_size.
        Returns a list of raw counts from the scan in the shape
        [[[counts, clock_samples]], [[counts, clock_samples]], ...] where each [[counts, clock_samples]] is the
        result of a single call to sample_counts at each scan position along the axis.

        If hyper_data_acquisition_function is not None, it will be called at each scan position.
        If hyper_data_acquisition_function.in_parallel is True, it will be called in a separate thread.
        """
        raw_counts = []
        self.position_controller.go_to_position(**{axis: min})
        time.sleep(self.raster_line_pause)
        for val in np.arange(min, max, step_size):
            logger.info(f'go to position {axis}: {val:.2f}')
            self.position_controller.go_to_position(**{axis: val})

            if hyper_data_acquisition_function is not None:
                if hyper_data_acquisition_function.in_parallel:
                    thread = threading.Thread(target=hyper_data_acquisition_function, args=(self,))
                    thread.start()
                    _raw_counts = self.sample_counts()
                    thread.join()
                else:
                    hyper_data_acquisition_function(self)
                    _raw_counts = self.sample_counts()
            else:
                _raw_counts = self.sample_counts()

            raw_counts.append(_raw_counts)
            logger.info(f'raw counts, total clock samples: {_raw_counts}')
            logger.info(f'current actuator position: {self.get_current_position()}')

        return raw_counts

    def reset(self):
        self.scanned_raw_counts = []
        self.scanned_count_rate = []

    def get_raw_counts(self):
        """
        Returns a list of raw counts from the most recent scan
        """
        return self.scanned_raw_counts

    def get_count_rate(self):
        """
        Returns a list of count rates from the most recent scan
        """
        return self.scanned_count_rate

    def optimize_position(self, axis, center_position, width = 2, step_size = 0.25):
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

        This function does NOT call self.hyper_data_acquisition_function.
        """
        min_val = center_position - width
        max_val = center_position + width
        min_val = np.max([min_val, self.position_controller.minimum_allowed_position])
        max_val = np.min([max_val, self.position_controller.maximum_allowed_position])

        self.start()
        raw_counts = self._scan_axis(axis, min_val, max_val, step_size)
        self.stop()
        axis_vals = np.arange(min_val, max_val, step_size)
        count_rates = [self.sample_count_rate(count) for count in raw_counts]

        optimal_position = axis_vals[np.argmax(count_rates)]
        coeff = None
        params = [np.max(count_rates), optimal_position, 1.0, np.min(count_rates)]
        bounds = (len(params)*tuple((0,)), len(params)*tuple((np.inf,)))
        try:
            coeff, var_matrix = scipy.optimize.curve_fit(gauss, axis_vals, count_rates, p0=params, bounds=bounds)
            optimal_position = coeff[1]
            # ensure that the optimal position is within the scan range
            optimal_position = np.max([min_val, optimal_position])
            optimal_position = np.min([max_val, optimal_position])
        except RuntimeError as e:
            logger.warning(e)

        return count_rates, axis_vals, optimal_position, coeff

    def run_scan(self, reset_starting_position=True, line_scan_callback=None):
        """
        Runs a scan across the range of set parameters: xmin, xmax, ymin, ymax, with increments of step_size.

        To get the data after the scan, call get_raw_counts() or get_count_rate(). You may also
        provide a callback function that will be called after each line scan is completed.

        :param reset_starting_position: if True, the actuator will be reset to the starting position before the scan begins
        :param line_scan_callback: a function that will be called after each line scan is completed. The function
                                     should take a single argument, which will be an instance of this class.
                                     i.e. line_scan_callback(obj: CounterAndScanner)
        :return: None

        """

        if reset_starting_position:
            self.reset()
            self.set_to_starting_position()

        self.start()
        while self._still_scanning():
            self._scan_x()
            self._move_y()
            if line_scan_callback is not None:
                line_scan_callback(self)
        self.stop()

