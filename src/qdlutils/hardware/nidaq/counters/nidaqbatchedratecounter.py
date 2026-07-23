import time
import logging

import numpy as np
import nidaqmx


from qdlutils.hardware.nidaq.counters.nidaqedgecounterinterface import NidaqEdgeCounterInterface

logger = logging.getLogger(__name__)


class NidaqBatchedRateCounter:
    '''
    This class implements an NIDAQ batched rate counter utilizing the edge counter 
    interface. This represents one layer of abstraction away from directly interfacing
    with the hardware since the NIDAQ API is qutie complicated.

    Specifically, this class represents a standard rate counter which is structured
    around "batched" data collection wherein the counts are readout in batches of
    some number of clock cycles. A single batch of `N_cycles` clock cycles at frequency
    `clock_rate` then corresponds to a sample over a time period `N_cycles / clock_rate`.

    This class implements the most basic and "natural" version of the rate counter, but
    in most use cases, it is generally preferable to use the sister class
    `NidaqTimedRateCounter` which computes the batch size needed to achieve the a 
    desired sample time.

    Historically, this class was implemented as `daqsamplers.NiDaqDigitalInputRateCounter`
    in `qt3utils`. However we have also merged the `QT3ScanNIDAQEdgeCounterController` 
    class functionality into this class since it largely served as a GUI wrapper.

    Attributes
    ----------
    daq_name : str
        Name of DAQ board for counter input
    signal_terminal : str
        Terminal for the signal to be counted
    clock_rate : int
        Clock rate of timing task for counting
    clock_terminal : str
        Terminal for the clock signal (if externally provided), leave as None if using
        the internal DAQ clock.
    signal_counter : str
        Name of the counter.
    read_write_timeout : float
        Time in seconds before timing out the measurement
    num_data_samples_per_batch : int
        The number of clock cycles (samples) to perform per batch of readout
    trigger_terminal : str
        The terminal of the external trigger input if provided
    running : bool
        True if the clock cycle task is running.
    read_lock : bool
        True if data is currently being read out.
    edge_counter_interface : ..edgecounterinterface.NidaqEdgeCounterInterface
        An NidaqEdgeCounterInterface class used to coordinate with the DAQ board for
        reading out the counter.


    Methods
    -------
    configure(config_dict) -> None
        Configures the rate counter to settings with matching keys provided in 
        `config_dict`, leaves values unchanged if not present. Note that this method
        should only be called before starting (or after stopping) the rate counter
        via the `self.start()` method as it will not automatically reconfigure the
        NidaqEdgeCounterInterface.

    start() -> None
        Starts up the rate counter, configures the DAQ via `self._read_samples()`
        then starts up the internal clock if configured to.
        This method must be run externally before attempting to read data.

    stop() -> None
        Waits for any measurements to be completed then stops and closes the clock
        and counter tasks on the DAQ.

    sample_nbatches_raw(n_batches, sum_counts) -> np.ndarray
        Get the counts of `n_batches` of counts from the DAQ where a batch is defined 
        by `self.num_data_samples_per_batch` clock cycles. Returns an array of tuples
        (counts, number of samples) for each batch measured. If `sum_counts` is `True`,
        then the counts and number of samples for all batches are summed.

    sample_nbatches_counts(n_batches, sum_counts) -> np.ndarray
        Same as `sample_nbatches_raw()` but returns only the counts themselves, possibly
        summed into a single number if `sum_counts` is `True`.

    sample_nbatches_time(n_batches, sum_counts) -> np.ndarray
        Same as `sample_nbatches_raw()` but converts the number of clock cycles into
        time in seconds based off the clock rate.

    sample_nbatches_rate(n_batches, sum_counts) -> np.ndarray
        Same as `sample_nbatches_raw()` but converts the data into a 1-d array of the 
        countrate per batch (or entire measure ment if `sum_counts` is `True`).

    sample_batch_raw() -> np.ndarray
        Samples a single batch and returns the (counts, number of cycles). This method 
        is slightly faster than `sample_nbatches_raw()` as it does not include the logic
        for additional batches.

    sample_batch_counts() -> int
        Same as `sample_nbatches_raw()` but returns only the counts as an integer

    sample_batch_time() -> np.ndarray
        Same as `sample_nbatches_raw()` but converts the number of clock cycles to a
        time in seconds.

    sample_batch_rate() -> float
        Same as `sample_nbatches_raw()` but returns the count rate as a float

    _read_samples() -> (np.ndarray, int)
        Internal method to read out a single batch on the DAQ, returns a tuple of an
        `np.ndarray` of shape (`self.num_data_samples_per_batch`,) where the value at
        each index corresponds to the number of detection events per clock cycle.
        The corresponding int is equal to or less than `self.num_data_samples_per_batch`
        and corresponds to the number of samples actually read out (on rare occassion
        this number can be less than the requested amount).

    _configure_daq() -> None
        Internal method to configure the DAQ and `NidaqEdgeCounterInterface`. Starts
        the internal clock cycle if an external one is not provided.

    '''


    def __init__(self,
                 daq_name = 'Dev1',
                 signal_terminal = 'PFI0',
                 clock_rate = 1000000,
                 num_data_samples_per_batch = 1000,
                 clock_terminal = None,
                 read_write_timeout = 10,
                 signal_counter = 'ctr2',
                 trigger_terminal = None) -> None:
        
        self.daq_name = daq_name
        self.signal_terminal = signal_terminal
        self.clock_rate = clock_rate
        self.clock_terminal = clock_terminal
        self.signal_counter = signal_counter
        self.read_write_timeout = read_write_timeout
        self.num_data_samples_per_batch = num_data_samples_per_batch
        self.trigger_terminal = trigger_terminal

        # Attribute to keep track if measurement is in progress
        # Other functions can use this attribute to stop an experiment in progress
        self.running = False
        # Attribute to keep track if currently reading and lock additonal queries
        self.read_lock = False
        # Edge counter interface of type NidaqEdgeCounterInterface
        self.edge_counter_interface = None

    def configure(self, config_dict) -> None:
        '''
        Configures the instance from the configuration dictonary.
        This function should only be called on initialiation of the parent application
        and not when an experiment is running.

        Parameters
        ----------
        config_dict : dict
            A dictionary containing keys matching the class atributes. If a match
            is found, then the corresponding attribute is updated. Otherwise it is 
            left unchanged.
        '''

        self.daq_name = config_dict.get('daq_name', self.daq_name)
        self.signal_terminal = config_dict.get('signal_terminal', self.signal_terminal)
        self.clock_rate = config_dict.get('clock_rate', self.clock_rate)
        self.clock_terminal = config_dict.get('clock_terminal', self.clock_terminal)
        self.signal_counter = config_dict.get('signal_counter', self.signal_counter)
        self.read_write_timeout = config_dict.get('read_write_timeout', self.read_write_timeout)
        self.num_data_samples_per_batch = config_dict.get('num_data_samples_per_batch', self.num_data_samples_per_batch)
        self.trigger_terminal = config_dict.get('trigger_terminal', self.trigger_terminal)


    def _configure_daq(self) -> None:
        '''
        This configures the DAQ for edge counting on the desired channel.
        
        Follows the initialization steps outline in `NidaqEdgeCounterInterface`
        class docstring.
        '''
        # Get the NidaqEdgeCounterInterface
        self.edge_counter_interface = NidaqEdgeCounterInterface(self.daq_name)
        # If an external clock terminal is not specified
        if self.clock_terminal is None:
            # Generate and configure an internal clock
            self.edge_counter_interface.configure_di_clock(
                    clock_rate=self.clock_rate)
            # Get the internal clock terminal from the config dictionary
            clock_terminal = self.edge_counter_interface.clock_task_config['clock_terminal']
        else:
            # Otherwise use the provided clock terminal
            clock_terminal = self.clock_terminal
        # Create and configure the counter task in the edge counter interface
        self.edge_counter_interface.configure_counter_period_measure(
            daq_counter = self.signal_counter,
            source_terminal = self.signal_terminal,
            N_samples_to_acquire_or_buffer_size = self.num_data_samples_per_batch,
            clock_terminal = clock_terminal,
            trigger_terminal = self.trigger_terminal,
            sampling_mode = nidaqmx.constants.AcquisitionType.FINITE)
        # Finally create a reader for the counter
        self.edge_counter_interface.create_counter_reader()


    def start(self) -> None:
        '''
        Configure the DAQ and start the clock task.
        This method is called externally before a measurement is set to begin.
        '''
        # If currently running, stop the clock task
        if self.running:
            self.stop()
        # Configure the DAQ for current measurement
        self._configure_daq()
        # If using an internal clock and a clock task was started start the clock task.
        if self.edge_counter_interface.clock_task:
            self.edge_counter_interface.clock_task.start()
        self.running = True

    def stop(self) -> None:
        '''
        Stop an experiment in progress
        '''
        # If the measurement is stil runing
        if self.running:
            # Wait out the current reading step
            while self.read_lock:
                time.sleep(0.1)
            # If the clock task exists, close attempt to close
            if self.edge_counter_interface.clock_task:
                # Attempt to stop and close the clock task
                try:
                    self.edge_counter_interface.clock_task.stop()
                except Exception as e:
                    logger.debug(e)
                try:
                    self.edge_counter_interface.clock_task.close()
                except Exception as e:
                    logger.debug(e)
            # Close the counter task
            try:
                self.edge_counter_interface.counter_task.close()
            except Exception as e:
                logger.debug(e)
        # Update state
        self.running = False

    def _save_do_states(self):
        '''Save current digital output states on port0/line0:3 before DAQ reinit.'''
        try:
            import nidaqmx
            task = nidaqmx.Task()
            task.di_channels.add_di_chan(f"{self.daq_name}/port1/line2:5")
            states = task.read(number_of_samples_per_channel=1)
            task.close()
            if states:
                result = list(states[0])
                logger.info(f'Saved DO mirror states: {result}')
                return result
        except Exception as e:
            logger.warning(f'Could not save DO states: {e}')
        return None

    def _restore_do_states(self, states):
        '''Restore digital output states on port0/line0:3 after DAQ reinit.'''
        try:
            import nidaqmx
            if not states or len(states) != 4:
                return
            task = nidaqmx.Task()
            task.do_channels.add_do_chan(f"{self.daq_name}/port1/line2:5")
            task.write(states, auto_start=True)
            task.close()
            logger.info(f'Restored DO mirror states: {states}')
        except Exception as e:
            logger.warning(f'Could not restore DO states: {e}')


    def _read_samples(self) -> tuple:
        '''
        This method reads a single batch corresponding to `self.num_data_samples_per_batch`
        samples (clock cycles).

        Parameters
        ----------
        None

        Returns
        -------
        (data_buffer, samples_read) : (np.ndarray, int)
            Returns a tuple where the first element corresponds to the data buffer where
            each element corresponds to the number of counts within a particular clock
            cycle of the batch. The `data_buffer` is a numpy array of dimension
            `(self.num_data_samples_per_batch,)`.
            The output `samples_read` is the number of samples (clock cycles) read by the
            DAQ during the batch. In most cases it is equal to the internal varriable
            `self.num_data_samples_per_batch` but can occasionally be less.
        '''
        # If not running (something else stopped it) return zero counts and zero samples
        if self.running is False:
            return np.zeros(1),0
        # Create a data buffer for the output
        data_buffer = np.zeros(self.num_data_samples_per_batch)
        # Base number of samples read
        samples_read = 0
        # Attempt to read out a single batch
        try:
            self.read_lock = True
            logger.debug('Starting counter task')

            #Flag the counter task to wait until it finishes and start it
            #self.edge_counter_interface.counter_task.wait_until_done()
            self.edge_counter_interface.counter_task.start()
            self.edge_counter_interface.counter_task.wait_until_done()
            logger.debug('Reading data')

            # Read the samples and load counts into the data_buffer
            # Get the number of samples read
            samples_read = self.edge_counter_interface.counter_reader.read_many_sample_double(
                                    data_buffer,
                                    number_of_samples_per_channel=self.num_data_samples_per_batch,
                                    timeout=self.read_write_timeout)
            logger.debug(f'Returned {samples_read} samples')
        except Exception as e:
            logger.error(f'{type(e)}: {e}')
            raise e
        # Stop the counter task and return the results
        finally:
            try:
                self.edge_counter_interface.counter_task.stop()
            except Exception as e:
                logger.error(f'in finally.stop. {type(e)}: {e}')
            self.read_lock = False
            return data_buffer, samples_read

    
    def sample_nbatches_raw(self, n_batches=1, sum_counts=True) -> np.ndarray:
        '''
        This method reads `n_batches` of batch reads returning the "raw" output of
        the `self._read_samples()` method.

        If the raw output is too verbose there are several derivative methods available 
        for reduced or modified output:
        1. `self.sample_nbatches_counts()`: Returns only the total counts per each batch
        2. `self.sample_nbatches_time()`  : Converts number of clock cycles to total time 
                                            per batch
        3. `self.sample_nbatches_rate()`  : Converts the total counts per batch and the
                                            number of cycles per batch into a count rate
                                            per batch. Returns only this value.

        For most practical cases, one may only be interested in sampling a single batch.
        In such cases users are pointed to `self.sample_batch_raw()` or its own 
        derivative methods which may be slightly faster.

        Parameters
        ----------
        n_batches : int
            The number of batches to sample
        sum_counts : bool
            If `True` (default) integrates the individual batch samples to obtain a
            single tuple (see Notes). If `False`, then each batch counts and number
            of samples are stored in an `(n_batches, 2)`-shaped array.

        Returns
        -------
        np.ndarray
            An array of tuple pairs corresponding to (counts, number of samples) for each
            batch resulting in an array of shape `(n_batches,2)`. If `sum_counts=True` then 
            each batch is integrated so that so that the output is a 2-tuple of the total 
            number of counts and number of clock cycles.
        
        Notes
        -----
        For each batch read (of size `num_data_samples_per_batch`), the total counts are
        summed. Because it's possible (though unlikely) for the hardware to return fewer 
        than `num_data_samples_per_batch` measurements, the actual number of data samples 
        per batch are also recorded.

        If sum_counts is False, a numpy array of shape (n_batches, 2) is returned, where
        the first element is the sum of the counts, and the second element is
        the actual number of clock samples per batch. This may be useful for the caller if
        they wish to perform their own averaging or other statistical analysis that may be 
        time dependent.

        For example, if `self.num_data_samples_per_batch` is 5 and n_batches is 3,
        then reading counts from the NiDAQ may return

        #sample 1
        raw_counts_1 = [3,5,4,6,4] 
        # ^ there are num_data_samples_per_batch=5 requested samples in this batch
        sum_counts_1 = 22
        size_counts_1 = 5
           summed batch 1: (22, 5)
        #sample 2
        raw_counts_2 = [5,5,7,3,4]
        sum_counts_2 = 24
        size_counts_2 = 5
           summed batch 2: (24, 5)
        #sample 3
        raw_counts_3 = [5,3,5,7] # nidaq may return fewer than num_data_samples_per_batch
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
        '''
        # Create a buffer for the results
        data = np.zeros((n_batches, 2))
        # Iterate for each batch to measure
        for i in range(n_batches):
            # Sample the batch
            data_sample, samples_read = self._read_samples()
            # Provided more than zero samples are read
            if samples_read > 0:
                # Collapse the data_sample bufffer (array of counts per each sample)
                data[i][0] = np.sum(data_sample[:samples_read])
            # Store the number of samples read
            data[i][1] = samples_read
            logger.debug(f'Batch data (sum counts, num clock cycles per batch): {data[i]}')
        # If sum_counts is true, collapse the result buffer
        if sum_counts:
            return np.sum(data, axis=0, keepdims=True)
        else:
            # Otherwise, return the full buffer
            return data

    def sample_nbatches_counts(self, n_batches=1, sum_counts=True) -> np.ndarray:
        '''
        Runs `self.sample_nbatches_raw()` but returns only the counts (not the number
        of samples). This is useful if the calling function expects only a single number
        of counts to be compatible with other hardware.

        Parameters
        ----------
        n_batches : int
            The number of batches to sample
        sum_counts : bool
            If `True` (default) integrates the individual batch samples to obtain a
            single tuple (see Notes). If `False`, then each batch counts and number
            of samples are stored in an `(n_batches, 2)`-shaped array.

        Returns
        -------
        np.ndarray
            An array corresponding to the number of counts per batch. If `sum_counts=True` 
            then the array is collapsed into a single number (`ndarray` of shape `(1,)`).
        '''
        # Get the output 
        output = self.sample_nbatches_raw(self, n_batches=n_batches, sum_counts=sum_counts)
        # Return only the counts
        # This indexing should work because the summation keeps the dimensions
        return output[:,0]

    def sample_nbatches_time(self, n_batches=1, sum_counts=True) -> np.ndarray:
        '''
        Runs `self.sample_nbatches_raw()` but converts the number of samples into a time
        in seconds. This is useful if the calling function expects output of this format
        for compatability with other hardware.

        Parameters
        ----------
        n_batches : int
            The number of batches to sample
        sum_counts : bool
            If `True` (default) integrates the individual batch samples to obtain a
            single tuple (see Notes). If `False`, then each batch counts and number
            of samples are stored in an `(n_batches, 2)`-shaped array.

        Returns
        -------
        np.ndarray
            An array of tuple pairs corresponding to (counts, time_in_seconds) for each
            batch resulting in an array of shape `(n_batches,2)`. If `sum_counts=True` then 
            each batch is integrated so that so that the output is a 2-tuple of the total 
            number of counts and time in seconds.
        '''
        if self.running is False:
            return np.zeros(1),0
        # Get the output 
        output = self.sample_nbatches_raw(self, n_batches=n_batches, sum_counts=sum_counts)
        # Get the time slice and update it by scaling by the clock cycle period
        output[:,1] = output[:,1] / self.clock_rate
        return output
    
    def sample_nbatches_rate(self, n_batches=1, sum_counts=True) -> np.ndarray:
        '''
        Runs `self.sample_nbatches_raw()` but returns the count rate. This is useful if 
        the calling function expects only the count rate to be compatible with other 
        hardware.

        Parameters
        ----------
        n_batches : int
            The number of batches to sample
        sum_counts : bool
            If `True` (default) integrates the individual batch samples to obtain a
            single tuple (see Notes). If `False`, then each batch counts and number
            of samples are stored in an `(n_batches, 2)`-shaped array.

        Returns
        -------
        np.ndarray
            An array corresponding to the countrate per batch. If `sum_counts=True` 
            then the array is collapsed into a single number.
        '''
        if self.running is False:
            return np.zeros(1),0
        # Get the output 
        output = self.sample_nbatches_raw(self, n_batches=n_batches, sum_counts=sum_counts)
        # The math is:
        #   counts = output[:,0]
        #   times = output[:,1] / self.clock_rate
        return (output[:,0] * self.clock_rate) / output[:,1]


    def sample_batch_raw(self) -> np.ndarray:
        '''
        Sample a single batch getting the raw counts and number of samples.

        Parameters
        ----------
        None

        Returns
        -------
        np.ndarray
            An array (number_of_counts, number_of_samples)
        '''
        if self.running is False:
            return np.zeros(1),0
        data_sample, samples_read = self._read_samples()
        return np.array([np.sum(data_sample), samples_read])

    def sample_batch_counts(self) -> int:
        '''
        Sample a single batch getting only the counts.

        Parameters
        ----------
        None

        Returns
        -------
        int
            The number of counts in the batch
        '''
        if self.running is False:
            return np.zeros(1),0
        data_sample, _ = self._read_samples()
        return int(np.sum(data_sample))
    
    def sample_batch_time(self) -> np.ndarray:
        '''
        Sample a single batch getting the raw counts and sample time in seconds.

        Parameters
        ----------
        None

        Returns
        -------
        np.ndarray
            An array (number_of_counts, number_of_samples)
        '''
        if self.running is False:
            return np.zeros(1),0
        data_sample, samples_read = self._read_samples()
        return np.array([np.sum(data_sample), samples_read/self.clock_rate])
    
    def sample_batch_rate(self) -> float:
        '''
        Sample a single batch getting the count rate.

        Parameters
        ----------
        None

        Returns
        -------
        float
            The count rate over the batch
        '''
        if self.running is False:
            return np.zeros(1),0
        data_sample, samples_read = self._read_samples()
        return float(np.sum(data_sample) * self.clock_rate /  samples_read)

