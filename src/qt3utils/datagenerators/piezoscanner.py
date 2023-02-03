import abc
import numpy as np
import scipy.optimize
import time
import logging

logger = logging.getLogger(__name__)

def gauss(x, *p):
    C, mu, sigma, offset = p
    return C*np.exp(-(x-mu)**2/(2.*sigma**2)) + offset

class BasePiezoScanner(abc.ABC):
    def __init__(self, stage_controller = None):

        self.running = False

        self.current_y = 0
        self.ymin = 0.0
        self.ymax = 80.0
        self.xmin = 0.0
        self.xmax = 80.0
        self.step_size = 0.5
        self.raster_line_pause = 0.0

        self.data = []
        self.stage_controller = stage_controller

        self.num_daq_batches = 1 #could change to 10 if want 10x more samples for each position

    def stop(self):
        self.running = False

    def start(self):
        self.running = True

    def set_to_starting_position(self):
        self.current_y = self.ymin
        if self.stage_controller:
            self.stage_controller.go_to_position(x = self.xmin, y = self.ymin)

    def close(self):
        return

    def set_scan_range(self, xmin, xmax, ymin, ymax):
        if self.stage_controller:
            self.stage_controller.check_allowed_position(xmin, ymin)
            self.stage_controller.check_allowed_position(xmax, ymax)

        self.ymin = ymin
        self.ymax = ymax
        self.xmin = xmin
        self.xmax = xmax

    def still_scanning(self):
        if self.running == False: #this allows external process to stop scan
            return False

        if self.current_y <= self.ymax: #stops scan when reaches final position
            return True
        else:
            self.running = False
            return False

    def move_y(self):
        self.current_y += self.step_size
        if self.stage_controller and self.current_y <= self.ymax:
            try:
                self.stage_controller.go_to_position(y=self.current_y)
            except ValueError as e:
                logger.info(f'out of range\n\n{e}')

    @abc.abstractmethod
    def sample_counts(self):
        """
        expectation is to return [[counts, clock_samples], [counts, clock_samples], ...] as is returned by daqsamplers.sample_counts.
        """
        pass

    @abc.abstractmethod
    def sample_count_rate(self):
        """
        must return a single floating point value
        """
        pass

    @abc.abstractmethod
    def set_num_data_samples_per_batch(self, N):
        pass

    def scan_x(self):

        scan = self.scan_axis('x', self.xmin, self.xmax, self.step_size)
        self.data.append(scan)

    def scan_axis(self, axis, min, max, step_size):
        scan = []
        self.stage_controller.go_to_position(**{axis:min})
        time.sleep(self.raster_line_pause)
        for val in np.arange(min, max, step_size):
            if self.stage_controller:
                logger.info(f'go to position {axis}: {val:.2f}')
                self.stage_controller.go_to_position(**{axis:val})
            cr = self.sample_count_rate()
            scan.append(cr)
            logger.info(f'count rate: {cr}')
            if self.stage_controller:
                logger.info(f'current position: {self.stage_controller.get_current_position()}')

        return scan

    def reset(self):
        self.data = []

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

        In cases where the data cannot be succesfully fit to a gaussian function,
        the optimial_position returned is the absolute brightest position in the scan,
        and the fit_coeff is set to None.
        When the fit is sucessful, x_optimal = mu.

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
        data = self.scan_axis(axis, min_val, max_val, step_size)
        self.stop()
        axis_vals = np.arange(min_val, max_val, step_size)

        optimal_position = axis_vals[np.argmax(data)]
        coeff = None
        params = [np.max(data), optimal_position, 1.0, np.min(data)]
        try:
            coeff, var_matrix = scipy.optimize.curve_fit(gauss, axis_vals, data, p0=params)
            optimal_position = coeff[1]
            # ensure that the optimal position is within the scan range
            optimal_position = np.max([min_val, optimal_position])
            optimal_position = np.min([max_val, optimal_position])
        except RuntimeError as e:
            print(e)

        return data, axis_vals, optimal_position, coeff

class NiDaqPiezoScanner(BasePiezoScanner):
    def __init__(self, nidaqratecounter, stage_controller, num_data_samples_per_batch = 50):
        super().__init__(stage_controller)
        self.nidaqratecounter = nidaqratecounter
        self.raster_line_pause = 0.150  #wait 150ms for the piezo stage to settle before a line scan
        self.set_num_data_samples_per_batch(num_data_samples_per_batch)

    def set_num_data_samples_per_batch(self, N):
        self.nidaqratecounter.num_data_samples_per_batch = N

    def sample_counts(self):
        return self.nidaqratecounter.sample_counts(self.num_daq_batches)

    def sample_count_rate(self, data_counts=None):
        if data_counts is None:
            data_counts = self.sample_counts()
        return self.nidaqratecounter.sample_count_rate(data_counts)

    def stop(self):
        self.nidaqratecounter.stop()
        super().stop()

    def start(self):
        super().start()
        self.nidaqratecounter.start()

    def close(self):
        super().close()
        self.nidaqratecounter.close()

class RandomPiezoScanner(BasePiezoScanner):
    '''
    This random scanner acts like it finds bright light sources
    at random positions across a scan.
    '''
    def __init__(self, stage_controller = None):
        super().__init__(stage_controller)
        self.default_offset = 350
        self.signal_noise_amp  = 0.2
        self.possible_offset_values = np.arange(5000, 100000, 1000)  # these create the "bright" positions

        self.current_offset = self.default_offset
        self.clock_period = 0.09302010  # a totally random number

    def set_num_data_samples_per_batch(self, N):
        #for the random sampler, there is only one sample per batch. So, we set
        #number of batches here
        self.num_daq_batches = N


    def sample_counts(self):
        if np.random.random(1)[0] < 0.005:
            self.current_offset = np.random.choice(self.possible_offset_values)
        else:
            self.current_offset = self.default_offset

        return self.signal_noise_amp * self.current_offset * np.random.random(
            self.num_daq_batches) + self.current_offset

    def sample_count_rate(self, data_counts = None):
        if data_counts is None:
            data_counts = self.sample_counts()
        return np.sum(data_counts) / self.clock_period
