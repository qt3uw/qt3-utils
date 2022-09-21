import time
import logging

import numpy as np
import nidaqmx
import nidaqmx.errors

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
                       signal_counter = 'ctr2',
                       sampling_mode = 'continuous',
                       trigger_terminal = None
                       ):
        '''
        NI DAQ Connections
        * signal_terminal - terminal connected to TTL pulses that indicate a photon (PFI0)
        * clock_terminal - terminal connected to the clock_pulser_channel (PFI12)
        * trigger_terminal - terminal connected to the trigger_pulser_channel (PFI1)

        For some applications, you only need the signal terminal -- such as the qt3scope / qt3scan applications.

        For ODMR experiments, you'll likely need to configure a clock and trigger terminal.

        sample_mode = either 'continous' or 'finite' are allowed.

        IF 'continous' sampling mode is chosen, the data buffer size will equal num_data_samples_per_batch.
        The user of this object is responsible for ensuring enough time has elapsed before reading out the buffer.
        That is, if conditions of the experiment change (such as RF frequency), you should wait enough time
        such that the data buffer contains only data taken at the same experimental condition. The amount of
        time that should be waited is at least num_data_samples_per_batch / clock_rate.

        If 'finite' sampling mode is chosen, then the signal counter NIDAQ task will start and stop
        with each read of the DAQ. Also, the code will wait the appropriate amount of time before
        reading the buffer. The drawback of the finite method is the overhead to create, start and stop
        NIDAQ task objects. Thus, the continuous mode sampling should be faster.

        '''
        self.daq_name = daq_name
        self.signal_terminal = signal_terminal
        self.clock_rate = clock_rate
        self.clock_terminal = clock_terminal
        self.trigger_terminal = trigger_terminal
        self.signal_counter = signal_counter
        self.read_write_timeout = read_write_timeout
        self.num_data_samples_per_batch = num_data_samples_per_batch
        self.running = False
        self.read_lock = False

        assert sampling_mode in ['continuous', 'finite']

        if sampling_mode == 'continuous':
            self.sampling_mode = nidaqmx.constants.AcquisitionType.CONTINUOUS
        else:
            self.sampling_mode = nidaqmx.constants.AcquisitionType.FINITE

        self.sample_data = collections.deque(maxlen = self.num_data_samples_per_batch)

    def _continuous_sampling_callback(self, task_handle, every_n_samples_event_type,
        number_of_samples, callback_data):
         self.sample_data.extend(self.nidaq_config.counter_task.read(number_of_samples_per_channel=self.num_data_samples_per_batch))
        return 0


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
            trigger_terminal = self.trigger_terminal,
            sampling_mode = self.sampling_mode)

        if self.sampling_mode == nidaqmx.constants.AcquisitionType.CONTINUOUS:
            self.nidaq_config.counter_task.register_every_n_samples_acquired_into_buffer_event(self.num_data_samples_per_batch, self._continuous_sampling_callback)

        self.nidaq_config.create_counter_reader()

    def _read_samples(self):

        if self.running is False: #external thread could have stopped
            return np.zeros(1),0

        self.read_lock = True
        data_buffer = np.zeros(self.num_data_samples_per_batch)
        samples_read = 0

        try:

            logger.info('starting counter task')
            if self.sampling_mode == nidaqmx.constants.AcquisitionType.FINITE:
                self.nidaq_config.counter_task.start()
                time.sleep(1.1*self.num_data_samples_per_batch / self.clock_rate)
                logger.info(f'pausing for {1.1*self.num_data_samples_per_batch / self.clock_rate:.6f} seconds')
            logger.info('reading data')
            #todo: consider using nidaqmx.Task.read function here instead.
            #it probably only saves the need to configure a buffer though.

            #todo: consider using nidaqmx.Task.register_every_n_samples_acquired_into_buffer_event
            #to register a callback function.
            #the simple solution would be to register a callback that simply stores
            #the most recent buffer values.
            #then any other user of this object can just read the data.
            samples_read = self.nidaq_config.counter_reader.read_many_sample_double(
                                    data_buffer,
                                    number_of_samples_per_channel=self.num_data_samples_per_batch,
                                    timeout=self.read_write_timeout)
            logger.info(f'returned {samples_read} samples')
            if self.sampling_mode == nidaqmx.constants.AcquisitionType.FINITE:
                self.nidaq_config.counter_task.stop()
        except nidaqmx.errors.DaqError as e:
            logging.warning(e)

        finally:
            self.read_lock = False
        return data_buffer, samples_read

    def start(self):
        if self.running:
            self.stop()

        self._configure_daq()
        self.nidaq_config.clock_task.start()
        if self.sampling_mode == nidaqmx.constants.AcquisitionType.CONTINUOUS:
            self.nidaq_config.counter_task.start()
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
            if self.sampling_mode == nidaqmx.constants.AcquisitionType.CONTINUOUS:
                self._burn_and_log_exception(self.nidaq_config.counter_task.stop) #will need to stop task if we move to continuous buffered acquisition
            self._burn_and_log_exception(self.nidaq_config.clock_task.close) #close the task to free resource on NIDAQ
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

        data =np.zeros((n_samples, 2))
        for i in range(n_samples):
            data_sample, samples_read = self._read_samples()
            if samples_read > 0:
                data[i][0] = np.sum(data_sample[:samples_read])
            data[i][1] = samples_read
            logger.info(f'batch data (sum counts, num clock cycles per batch): {data[i]}')
        return data

    def sample_count_rate(self, n_samples = 1):
        '''
        Utilizes sample_counts method above and compute the count rate as described
        in that method's docstring.

        Under normal conditions, will return a numpy array of size n_samples, with values
        equal to the estimated count rate.

        However, there are two possible outcomes if there are errors reading the NiDAQ.

        1. return a numpy array of count rate measurements of size 0 < N < n_samples (if there's partial error)
        2. return a numpy array of size N = n_samples with value of np.nan if no data are returned

        If the NiDAQ is configured properly and sufficient time is allowed for data to be
        acquired per batch, it's very unlikely that any errors will occur.
        '''

        data = self.sample_counts(n_samples)
        data = data[np.where(data[:,1] > 0)]
        if data.shape[0] > 0:
            return self.clock_rate * data[:,0]/data[:,1]
        else:
            return np.nan*np.ones(n_samples)

    def yield_count_rate(self):
        while self.running:
            yield np.mean(self.sample_count_rate())
