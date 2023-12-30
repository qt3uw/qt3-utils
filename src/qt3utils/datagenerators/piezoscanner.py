import numpy as np
import scipy.optimize
import time
import logging

logger = logging.getLogger(__name__)

def gauss(x, *p):
    C, mu, sigma, offset = p
    return C*np.exp(-(x-mu)**2/(2.*sigma**2)) + offset


class CounterAndScanner:
    def __init__(self, rate_counter, stage_controller):

        self.running = False
        self.current_y = 0
        self.ymin = stage_controller.minimum_allowed_position
        self.ymax = stage_controller.maximum_allowed_position
        self.xmin = stage_controller.minimum_allowed_position
        self.xmax = stage_controller.maximum_allowed_position
        self.step_size = 0.5
        self.raster_line_pause = 0.150  # wait 150ms for the piezo stage to settle before a line scan

        self.scanned_raw_counts = []
        self.scanned_count_rate = []

        self.stage_controller = stage_controller
        self.rate_counter = rate_counter
        self.num_daq_batches = 1 # could change to 10 if want 10x more samples for each position

    def stop(self):
        self.rate_counter.stop()
        self.running = False

    def start(self):
        self.running = True
        self.rate_counter.start()

    def set_to_starting_position(self):
        self.current_y = self.ymin
        if self.stage_controller:
            self.stage_controller.go_to_position(x = self.xmin, y = self.ymin)

    def close(self):
        self.rate_counter.close()


    def sample_counts(self):
        return self.rate_counter.sample_counts(self.num_daq_batches)

    def sample_count_rate(self, data_counts=None):
        if data_counts is None:
            data_counts = self.sample_counts()
        return self.rate_counter.sample_count_rate(data_counts)

    def set_scan_range(self, xmin, xmax, ymin, ymax):
        if self.stage_controller:
            self.stage_controller.check_allowed_position(xmin, ymin)
            self.stage_controller.check_allowed_position(xmax, ymax)

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

    def get_completed_scan_range(self) -> tuple:
        """
        Returns a tuple of the scan range that has been completed
        :return: xmin, xmax, ymin, current_y
        """
        return self.xmin, self.xmax, self.ymin, self.current_y

    def still_scanning(self):
        if self.running == False: #this allows external process to stop scan
            return False

        if self.current_y < self.ymax: #stops scan when reaches final position
            return True
        else:
            self.running = False
            return False

    def move_y(self):
        if self.stage_controller and self.current_y < self.ymax:
            self.current_y += self.step_size
            try:
                self.stage_controller.go_to_position(y=self.current_y)
            except ValueError as e:
                logger.info(f'out of range\n\n{e}')

    def scan_x(self):
        """
        Scans the x axis from xmin to xmax in steps of step_size.

        Stores results in self.scanned_raw_counts and self.scanned_count_rate.
        """
        raw_counts_for_axis = self.scan_axis('x', self.xmin, self.xmax, self.step_size)
        self.scanned_raw_counts.append(raw_counts_for_axis)
        self.scanned_count_rate.append([self.sample_count_rate(raw_counts) for raw_counts in raw_counts_for_axis])

    def scan_axis(self, axis, min, max, step_size):
        """
        Moves the stage along the specified axis from min to max in steps of step_size.
        Returns a list of raw counts from the scan in the shape
        [[[counts, clock_samples]], [[counts, clock_samples]], ...] where each [[counts, clock_samples]] is the
        result of a single call to sample_counts at each scan position along the axis.
        """
        raw_counts = []
        self.stage_controller.go_to_position(**{axis:min})
        time.sleep(self.raster_line_pause)
        for val in np.arange(min, max, step_size):
            if self.stage_controller:
                logger.info(f'go to position {axis}: {val:.2f}')
                self.stage_controller.go_to_position(**{axis:val})
            _raw_counts = self.sample_counts()
            raw_counts.append(_raw_counts)
            logger.info(f'raw counts, total clock samples: {_raw_counts}')
            if self.stage_controller:
                logger.info(f'current position: {self.stage_controller.get_current_position()}')

        return raw_counts

    def reset(self):
        self.scanned_raw_counts = []
        self.scanned_count_rate = []

    def optimize_position(self, axis, center_position, width = 2, step_size = 0.25):
        '''
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

        '''
        min_val = center_position - width
        max_val = center_position + width
        if self.stage_controller:
            min_val = np.max([min_val, self.stage_controller.minimum_allowed_position])
            max_val = np.min([max_val, self.stage_controller.maximum_allowed_position])
        else:
            min_val = np.max([min_val, 0.0])
            max_val = np.min([max_val, 80.0])

        self.start()
        raw_counts = self.scan_axis(axis, min_val, max_val, step_size)
        self.stop()
        axis_vals = np.arange(min_val, max_val, step_size)
        count_rates = [self.sample_count_rate(count) for count in raw_counts]

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
            logger.warning(e)

        return count_rates, axis_vals, optimal_position, coeff

