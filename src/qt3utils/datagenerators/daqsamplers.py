import time
import logging
import abc

import numpy as np
import nidaqmx

import qt3utils.nidaq

logger = logging.getLogger(__name__)

class RateCounterBase(abc.ABC):

    def __init__(self):
        self.clock_rate = 1 # default clock rate
        self.running = False

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
    def sample_counts(self, n_samples = 1) -> np.ndarray:
        """
        Should return a numpy array of size n_samples, with each row being
        an array (or tuple) of two values, The first value is equal to the number of counts,
        and the second value is the number of clock samples that were used to measure the counts.

        Example, if n_samples = 3
        data = [
                [22, 5], # 22 counts were observed in 5 clock samples
                [24, 5],
                [20, 4] # this data indicates there was an error with data acquisition - 4 clock samples were observed.
               ]
        """
        pass

    def sample_count_rate(self, data_counts: np.ndarray):
        """
        Converts the output of sample_counts to a count rate. Expects data_counts to be a 2d numpy array

        Under normal conditions, will return a numpy array of size n_samples, with values
        equal to the estimated count rate.

        However, there are two possible outcomes if there are errors with the data (which can be caused by NIDAQ errors)

        1. return a numpy array of count rate measurements of size 0 < N < n_samples (if there's partial error)
        2. return a numpy array of size N = n_samples with value of np.nan if no data are returned

        If the NiDAQ is configured properly and sufficient time is allowed for data to be
        acquired per batch, it's very unlikely that any errors will occur.
        """

        _data = data_counts[np.where(data_counts[:, 1] > 0)] #removes all rows where no data were acquired
        if _data.shape[0] > 0:
            return self.clock_rate * _data[:, 0]/_data[:, 1]
        else:
            return np.nan*np.ones(len(data_counts))

    def yield_count_rate(self):
        while self.running:
            count_data = self.sample_counts()
            yield np.mean(self.sample_count_rate(count_data))


class RandomRateCounter(RateCounterBase):

    '''
    This random source acts like a light source with variable intensity.

    This is similar to a PL source moving in and out of focus.
    '''
    def __init__(self):
        super().__init__()
        self.default_offset = 100
        self.signal_noise_amp  = 0.2
        self.possible_offset_values = np.arange(0, 1000, 50)

        self.current_offset = self.default_offset
        self.current_direction = 1
        self.running = False

    def sample_counts(self, n_samples = 1):
        """
        Returns a random number of counts
        """
        if np.random.random(1)[0] < 0.05:
            if np.random.random(1)[0] < 0.1:
                self.current_direction = -1 * self.current_direction
            self.current_offset += self.current_direction*np.random.choice(self.possible_offset_values)

        if self.current_offset < self.default_offset:
            self.current_offset = self.default_offset
            self.current_direction = 1

        counts = self.signal_noise_amp*self.current_offset*np.random.random(n_samples) + self.current_offset
        count_size = np.ones(n_samples)
        return np.column_stack((counts, count_size))


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
        self.running = False

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
                time.sleep(0.1) #wait for current read to complete

            if self.nidaq_config.clock_task:
                self._burn_and_log_exception(self.nidaq_config.clock_task.stop)
                self._burn_and_log_exception(self.nidaq_config.clock_task.close) #close the task to free resource on NIDAQ
            #self._burn_and_log_exception(self.nidaq_config.counter_task.stop) #will need to stop task if we move to continuous buffered acquisition
            self._burn_and_log_exception(self.nidaq_config.counter_task.close)

        self.running = False

    def close(self):
        self.stop()

    def sample_counts(self, n_samples = 1):
        '''
        Performs n_samples of batch reads from the NiDAQ.

        For each batch read (of size `num_data_samples_per_batch`), the
        total counts are summed. Additionally, because it's possible (though unlikely)
        for the NiDAQ to return fewer than `num_data_samples_per_batch` measurements,
        the actual number of data samples per batch are also recorded.

        Finally, a numpy array of shape (n_samples, 2) is returned, where
        the first element is the sum of the counts, and the second element is
        the actual number of data samples per batch.

        For example, if `num_data_samples_per_batch` is 5 and n_samples is 3,
        (typical values are 100 and 10, 100 and 1, 1000 and 1, etc)

        reading counts from the NiDAQ may return

        #sample 1
        raw_counts_1 = [3,5,4,6,4]
        sum_counts_1 = 22
        size_counts_1 = 5
           (22, 5)
        #sample 2
        raw_counts_2 = [5,5,7,3,4]
        sum_counts_2 = 24
        size_counts_2 = 5
           (24, 5)
        #sample 3
        raw_counts_3 = [5,3,5,7]
        sum_counts_3 = 20
        size_counts_2 = 4
           (20, 4)

        In this example, the numpy array is of shape (3, 2) and will be
        data = [
                [22, 5],
                [24, 5],
                [20, 4]
               ]

        With these data, and knowing the clock_rate, one can easily compute
        the count rate

        #removes rows where num samples per batch were zero (which would be a bug in the code)
        data = data[np.where(data[:,1] > 0)]

        #count rate is the mean counts per clock cycle multiplied by the clock rate.
        count_rate = clock_rate * data[:,0]/data[:,1]
        '''

        data = np.zeros((n_samples, 2))
        for i in range(n_samples):
            data_sample, samples_read = self._read_samples()
            if samples_read > 0:
                data[i][0] = np.sum(data_sample[:samples_read])
            data[i][1] = samples_read
            logger.info(f'batch data (sum counts, num clock cycles per batch): {data[i]}')
        return data

