import time
import logging

import numpy as np
import nidaqmx

import qt3utils.nidaq

logger = logging.getLogger(__name__)

class SamplerInterface:
    def stop(self):
        pass

    def start(self):
        pass

    def close(self):
        pass

    def sample_count_rate(self, n_samples = None):
        pass

    def yield_count_rate(self):
        #this should be a generator function
        #yield np.mean(self.sample_count_rate())
        pass


class RandomSampler(SamplerInterface):

    '''
    This random source acts like a light source with variable intensity.

    This is similar to a PL source moving in and out of focus.
    '''
    def __init__(self):
        self.default_offset = 100
        self.signal_noise_amp  = 0.2
        self.possible_offset_values = np.arange(0, 1000, 50)

        self.current_offset = self.default_offset
        self.current_direction = 1
        self.running = False

    def stop(self):
        self.running = False

    def start(self):
        self.running = True

    def close(self):
        pass

    def sample_count_rate(self, n_samples = 1):
        if np.random.random(1)[0] < 0.05:
            if np.random.random(1)[0] < 0.1:
                self.current_direction = -1 * self.current_direction
            self.current_offset += self.current_direction*np.random.choice(self.possible_offset_values)

        if self.current_offset < self.default_offset:
            self.current_offset = self.default_offset
            self.current_direction = 1

        return self.signal_noise_amp*self.current_offset*np.random.random(n_samples) + self.current_offset

    def yield_count_rate(self):
        while self.running:
            yield np.mean(self.sample_count_rate())


class NiDaqSampler(SamplerInterface):

    def __init__(self, daq_name = 'Dev1',
                       signal_terminal = 'PFI0',
                       clock_rate = 10000,
                       num_data_samples_per_batch = 1000,
                       clock_terminal = None,
                       read_write_timeout = 10,
                       signal_counter = 'ctr2'
                       ):

        self.daq_name = daq_name
        self.signal_terminal = signal_terminal
        self.clock_rate = clock_rate
        self.clock_terminal = clock_terminal
        self.signal_counter = signal_counter
        self.read_write_timeout = read_write_timeout
        self.num_data_samples_per_batch = num_data_samples_per_batch
        self.running = False

        self.read_lock = False

    def _configure_daq(self):
        self.nidaq_config = qt3utils.nidaq.EdgeCounter(self.daq_name)

        if self.clock_terminal is None:
            self.nidaq_config.configure_di_clock(clock_rate = self.clock_rate)
            clock_terminal = self.nidaq_config.clock_task_config['clock_terminal']
        else:
            clock_terminal = clock_terminal

        self.nidaq_config.configure_counter_period_measure(
            daq_counter = self.signal_counter,
            source_terminal = self.signal_terminal,
            N_samples_to_acquire_or_buffer_size = self.num_data_samples_per_batch,
            clock_terminal = clock_terminal,
            trigger_terminal = None,
            sampling_mode = nidaqmx.constants.AcquisitionType.FINITE)

        self.nidaq_config.create_counter_reader()

    def _read_samples(self):

        if self.running is False: #external thread could have stopped
            return np.zeros(1),0

        self.read_lock = True
        data_buffer = np.zeros(self.num_data_samples_per_batch)
        logger.info('starting counter task')
        self.nidaq_config.counter_task.start()
        #DO WE NEED TO PAUSE HERE FOR DATA ACQUISITION?
        #another method will probably be to configure the task to continuously fill a buffer and read it
        #out... then we don't need to start and stop, right? TODO
        #and, with continuous acquisition, there might not need to be any time.sleep
        time.sleep(1.05*self.num_data_samples_per_batch / self.clock_rate)
        logger.info(f'pausing for {1.05*self.num_data_samples_per_batch / self.clock_rate:.6f} seconds')
        logger.info('reading data')
        samples_read = self.nidaq_config.counter_reader.read_many_sample_double(
                                data_buffer,
                                number_of_samples_per_channel=self.num_data_samples_per_batch,
                                timeout=self.read_write_timeout)
        logger.info(f'returned {samples_read} samples')
        self.nidaq_config.counter_task.stop()
        self.read_lock = False
        return data_buffer, samples_read

    def start(self):
        if self.running:
            self.stop()

        self._configure_daq()
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

            self._burn_and_log_exception(self.nidaq_config.clock_task.stop)
            #self._burn_and_log_exception(self.nidaq_config.counter_task.stop) #will need to stop task if we move to continuous buffered acquisition
            self._burn_and_log_exception(self.nidaq_config.clock_task.close) #close the task to free resource on NIDAQ
            self._burn_and_log_exception(self.nidaq_config.counter_task.close)

        self.running = False

    def close(self):
        self.stop()

    def sample_count_rate(self, n_samples = 1):

        data =np.zeros(n_samples)
        for i in range(n_samples):
            data_sample, samples_read = self._read_samples()
            if samples_read > 0:
                data[i] = np.mean(data_sample[:samples_read] * self.clock_rate)
                logger.info(f'total counts {np.sum(data_sample[:samples_read])}')
        return data

        # data_sample, samples_read = self._read_samples()
        # return data_sample[:samples_read] * self.clock_rate

    def yield_count_rate(self):
        while self.running:
            yield np.mean(self.sample_count_rate())
