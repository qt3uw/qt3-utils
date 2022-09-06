import abc
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

class BasePiezoScanner(abc.ABC):
    def __init__(self, controller = None):

        self.running = False

        self.current_y = 0
        self.ymin = 0.01
        self.ymax = 40.01
        self.xmin = 0.01
        self.xmax = 40.01
        self.step_size = 0.5

        self.data = []
        self.controller = controller

        self.num_daq_batches = 1 #could change to 10 if want 10x more samples for each position

    def stop(self):
        self.running = False

    def start(self):
        self.running = True

    def set_to_starting_position(self):
        self.current_y = self.ymin
        if self.controller:
            self.controller.go_to_position(x = self.xmin, y = self.ymin)

    def close(self):
        return

    def set_scan_range(self, xmin, xmax, ymin, ymax):
        if self.controller:
            self.controller.check_allowed_position(xmin, ymin)
            self.controller.check_allowed_position(xmax, ymax)

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
        if self.controller and self.current_y <= self.ymax:
            try:
                self.controller.go_to_position(y=self.current_y)
            except ValueError as e:
                logger.info(f'out of range\n\n{e}')

    @abc.abstractmethod
    def sample_count_rate(self):
        '''
        must return an array-like object
        '''
        pass

    @abc.abstractmethod
    def set_num_data_samples_per_batch(self, N):
        pass

    def scan_x(self):

        scan = self.scan_axis('x', self.xmin, self.xmax, self.step_size)
        self.data.append(scan)

    def scan_axis(self, axis, min, max, step_size):
        scan = []
        for val in np.arange(min, max, step_size):
            if self.controller:
                logger.info(f'go to position {axis}: {val:.2f}')
                if self.controller:
                    self.controller.go_to_position(**{axis:val})
            cr = np.mean(self.sample_count_rate())
            scan.append(cr)
            logger.info(f'count rate: {cr}')
            if self.controller:
                logger.info(f'current position: {self.controller.get_current_position()}')

        return scan

    def reset(self):
        self.data = []


class NiDaqPiezoScanner(BasePiezoScanner):
    def __init__(self, nidaqsampler, controller):
        super().__init__(controller)
        self.nidaqsampler = nidaqsampler

    def set_num_data_samples_per_batch(self, N):
        self.nidaqsampler.num_data_samples_per_batch = N

    def sample_count_rate(self):
        return self.nidaqsampler.sample_count_rate(self.num_daq_batches)

    def stop(self):
        self.nidaqsampler.stop()
        super().stop()

    def start(self):
        super().start()
        self.nidaqsampler.start()

    def close(self):
        super().close()
        self.nidaqsampler.close()

class RandomPiezoScanner(BasePiezoScanner):
    '''
    This random scanner acts like it finds bright light sources
    at random positions across a scan.
    '''
    def __init__(self, controller = None):
        super().__init__(controller)
        self.default_offset = 350
        self.signal_noise_amp  = 0.2
        self.possible_offset_values = np.arange(5000, 100000, 1000)

        self.current_offset = self.default_offset

    def set_num_data_samples_per_batch(self, N):
        #for the random sampler, there is only one sample per batch. So, we set
        #number of batches here
        self.num_daq_batches = N

    def sample_count_rate(self):
        #time.sleep(.25) #simulate time for data acquisition
        if np.random.random(1)[0] < 0.005:
            self.current_offset = np.random.choice(self.possible_offset_values)
        else:
            self.current_offset = self.default_offset

        return self.signal_noise_amp*self.current_offset*np.random.random(self.num_daq_batches) + self.current_offset
