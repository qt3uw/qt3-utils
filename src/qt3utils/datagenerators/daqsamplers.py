import time
import logging
import abc
from typing import Generator

import numpy as np
import nidaqmx

import qt3utils.nidaq

logger = logging.getLogger(__name__)


class RateCounterBase(abc.ABC):
    """
    Subclasses must implement a clock_rate attribute or property.
    """
    def __init__(self):
        self.running = False
        self.clock_rate = 0

    def stop(self):
        """
        subclasses may override this for custom behavior
        """
        self.running = False

    def start(self):
        """
        subclasses may override this for custom behavior
        """
        self.running = True

    def close(self):
        """
        subclasses may override this for custom behavior
        """
        pass

    @abc.abstractmethod
    def _read_samples(self):
        """
        subclasses must implement this method

        Should return total_counts, num_clock_samples
        """
        pass

    def sample_counts(self, n_batches=1, sum_counts=True) -> np.ndarray:
        """
        Performs n_batches of batch reads from _read_samples method.

        This is useful when hardware (such as NIDAQ) is pre-configured to acquire a fixed number of samples
        and the caller wishes to read more data than the number of samples acquired.
        For example, if the NiDAQ is configured to acquire 1000 clock samples, but the caller
        wishes to read 10000 samples, then this function may be called with n_batches=10.

        For each batch read (of size `num_data_samples_per_batch`), the
        total counts are summed. Because it's possible (though unlikely)
        for the hardware to return fewer than `num_data_samples_per_batch` measurements,
        the actual number of data samples per batch are also recorded.

        If sum_counts is False, a numpy array of shape (n_batches, 2) is returned, where
        the first element is the sum of the counts, and the second element is
        the actual number of clock samples per batch. This may be useful for the caller if
        they wish to perform their own averaging or other statistical analysis that may be time dependent.

        For example, if `self.num_data_samples_per_batch` is 5 and n_batches is 3,
        then reading counts from the NiDAQ may return

        #sample 1
        raw_counts_1 = [3,5,4,6,4]  # there are num_data_samples_per_batch=5 requested samples in this batch
        sum_counts_1 = 22
        size_counts_1 = 5
           summed batch 1: (22, 5)
        #sample 2
        raw_counts_2 = [5,5,7,3,4]
        sum_counts_2 = 24
        size_counts_2 = 5
           summed batch 2: (24, 5)
        #sample 3
        raw_counts_3 = [5,3,5,7] # it's possible, thought unlikely, nidaq returns fewer than num_data_samples_per_batch
        sum_counts_3 = 20
        size_counts_2 = 4
           summed batch 3: (20, 4)

        The summed batch values are combined into a numpy array of shape (3, 2)

        data = [
                [22, 5],
                [24, 5],
                [20, 4]
               ]
        If sum_counts is False, this numpy array of shape (3,2) will be returned.

        If sum_counts is True, data will be summed along axis=0 with keepdim=True,
        resulting in a numpy array of shape (1, 2).
        Following the example, the return value would be [[66, 14]].
        """

        data = np.zeros((n_batches, 2))
        for i in range(n_batches):
            data_sample, samples_read = self._read_samples()
            if samples_read > 0:
                data[i][0] = np.sum(data_sample[:samples_read])
            data[i][1] = samples_read
            logger.info(f'batch data (sum counts, num clock cycles per batch): {data[i]}')

        if sum_counts:
            return np.sum(data, axis=0, keepdims=True)
        else:
            return data

    def sample_count_rate(self, data_counts: np.ndarray) -> np.floating:
        """
        Converts the average count rate given the data_counts, using the object's
        clock_rate value. Expects data_counts to be a 2d numpy array
        of [[counts, clock_samples], [counts, clock_samples], ...] or a 2d array with one row: [[counts, clock_samples]]
        as is returned by the function, sample_counts, in this class.

        Returns the average count rate in counts/second
            = self.clock_rate * total counts/ total clock_samples)

        If the sum of all clock_samples is 0, will return np.nan.
        """
        _data = np.sum(data_counts, axis=0)
        if _data[1] > 0:
            return self.clock_rate * _data[0]/_data[1]
        else:
            return np.nan

    def yield_count_rate(self) -> Generator[np.floating, None, None]:
        while self.running:
            count_data = self.sample_counts()  # because n_batches=1 (and sum=True) this returns a 2d array of shape (1, 2)
            yield self.sample_count_rate(count_data)  # because count_data is 2d, sample count rate returns a float c


class RandomRateCounter(RateCounterBase):
    """
    This random source acts like a light source with variable intensity.

    This is similar to a PL source moving in and out of focus.

    When 'simulated_single_light_source' is True at instantiation,
    this will simulate a sample with isolated bright spots, like NV centers in diamond and
    is used when testing the CounterAndScanner class in piezoscanner.py module.
    """
    def __init__(self, simulate_single_light_source=False, num_data_samples_per_batch=10):
        super().__init__()
        self.default_offset = 100
        self.signal_noise_amp = 0.2

        self.current_offset = self.default_offset
        self.current_direction = 1
        self.clock_rate = 0.9302010 # a totally random number :P
        self.simulate_single_light_source = simulate_single_light_source
        self.possible_offset_values = np.arange(5000, 100000, 1000)  # these create the "bright" positions
        self.num_data_samples_per_batch = num_data_samples_per_batch

    def _read_samples(self):
        """
        Returns a random number of counts
        """
        if self.simulate_single_light_source:
            if np.random.random(1)[0] < 0.005:
                self.current_offset = np.random.choice(self.possible_offset_values)
            else:
                self.current_offset = self.default_offset

        else:
            if np.random.random(1)[0] < 0.05:
                if np.random.random(1)[0] < 0.1:
                    self.current_direction = -1 * self.current_direction
                self.current_offset += self.current_direction*np.random.choice(self.possible_offset_values)

            if self.current_offset < self.default_offset:
                self.current_offset = self.default_offset
                self.current_direction = 1

        counts = self.signal_noise_amp * self.current_offset * np.random.random(self.num_data_samples_per_batch) + self.current_offset

        return counts, self.num_data_samples_per_batch


class NiDaqDigitalInputRateCounter(RateCounterBase):

    def __init__(self, daq_name = 'Dev1',
                       signal_terminal = 'PFI0',
                       clock_rate = 10000,
                       num_data_samples_per_batch = 1000,
                       clock_terminal = None,
                       read_write_timeout = 10,
                       signal_counter = 'ctr2',
                       trigger_terminal = None,
                       ):
        super().__init__()
        self.daq_name = daq_name
        self.signal_terminal = signal_terminal
        self.clock_rate = clock_rate
        self.clock_terminal = clock_terminal
        self.signal_counter = signal_counter
        self.read_write_timeout = read_write_timeout
        self.num_data_samples_per_batch = num_data_samples_per_batch
        self.trigger_terminal = trigger_terminal

        self.read_lock = False

    def _configure_daq(self):
        self.nidaq_config = qt3utils.nidaq.EdgeCounter(self.daq_name)

        if self.clock_terminal is None:
            self.nidaq_config.configure_di_clock(clock_rate = self.clock_rate)
            clock_terminal = self.nidaq_config.clock_task_config['clock_terminal']
        else:
            clock_terminal = self.clock_terminal

        self.nidaq_config.configure_counter_period_measure(
            daq_counter = self.signal_counter,
            source_terminal = self.signal_terminal,
            N_samples_to_acquire_or_buffer_size = self.num_data_samples_per_batch,
            clock_terminal = clock_terminal,
            trigger_terminal = self.trigger_terminal,
            sampling_mode = nidaqmx.constants.AcquisitionType.FINITE)

        self.nidaq_config.create_counter_reader()

    def _read_samples(self):

        if self.running is False: #external thread could have stopped
            return np.zeros(1),0

        data_buffer = np.zeros(self.num_data_samples_per_batch)
        samples_read = 0

        try:
            self.read_lock = True
            logger.info('starting counter task')
            self.nidaq_config.counter_task.wait_until_done()
            self.nidaq_config.counter_task.start()
            #DO WE NEED TO PAUSE HERE FOR DATA ACQUISITION?
            #another method will probably be to configure the task to continuously fill a buffer and read it
            #out... then we don't need to start and stop, right? TODO
            #and, with continuous acquisition, there might not need to be any time.sleep
            logger.info(f'waiting for {1.1*self.num_data_samples_per_batch / self.clock_rate:.6f} seconds for data acquisition.')
            time.sleep(1.1*self.num_data_samples_per_batch / self.clock_rate)
            logger.info('reading data')
            samples_read = self.nidaq_config.counter_reader.read_many_sample_double(
                                    data_buffer,
                                    number_of_samples_per_channel=self.num_data_samples_per_batch,
                                    timeout=self.read_write_timeout)
            logger.info(f'returned {samples_read} samples')

        except Exception as e:
            logger.error(f'{type(e)}: {e}')
            raise e

        finally:
            try:
                self.nidaq_config.counter_task.stop()
            except Exception as e:
                logger.error(f'in finally.stop. {type(e)}: {e}')

            self.read_lock = False
            return data_buffer, samples_read

    def start(self):
        if self.running:
            self.stop()

        self._configure_daq()
        if self.nidaq_config.clock_task:
            self.nidaq_config.clock_task.start()
        self.running = True

    def _burn_and_log_exception(self, f):
        try:
            f()
        except Exception as e:
            logger.debug(e)
            pass

    def stop(self):
        if self.running:
            while self.read_lock:
                time.sleep(0.1) # wait for current read to complete

            if self.nidaq_config.clock_task:
                self._burn_and_log_exception(self.nidaq_config.clock_task.stop)
                self._burn_and_log_exception(self.nidaq_config.clock_task.close) # close the task to free resource on NIDAQ
            # self._burn_and_log_exception(self.nidaq_config.counter_task.stop) # will need to stop task if we move to continuous buffered acquisition
            self._burn_and_log_exception(self.nidaq_config.counter_task.close)

        self.running = False

    def close(self):
        self.stop()




