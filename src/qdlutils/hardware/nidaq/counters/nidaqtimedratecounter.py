import time
import logging

import numpy as np
import nidaqmx


from qdlutils.hardware.nidaq.counters.nidaqbatchedratecounter import NidaqBatchedRateCounter

logger = logging.getLogger(__name__)


class NidaqTimedRateCounter(NidaqBatchedRateCounter):
    '''
    This class implements an NIDAQ timed rate counter utilizing the edge counter 
    interface. This represents one layer of abstraction away from directly interfacing
    with the hardware since the NIDAQ API is qutie complicated.

    Specifically, this class represents a standard rate counter which is structured
    around "timed" data collection wherein the counts are readout in batches of a 
    set "sample_time" in seconds.
    
    This represents a slightly more user-friendly version of the `NidaqBatchedRateCounter`
    and inhereits most functionality from it.

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

    sample_time_in_seconds : float
        The length of time to measure a single batch.

    Methods
    -------
    configure(config_dict) -> None
        Configures the rate counter to settings with matching keys provided in 
        `config_dict`, leaves values unchanged if not present. Note that this method
        should only be called before starting (or after stopping) the rate counter
        via the `self.start()` method as it will not automatically reconfigure the
        NidaqEdgeCounterInterface. In this class it is updated to automatically
        calculate the number of cycles per batch based off of the sample time.

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


    configure_sample_time(sample_time) -> None
        Updates the sample time and number of cycles per batch within the instance and
        updates the counter task accordingly.
    '''


    def __init__(self,
                 daq_name: str = 'Dev1',
                 signal_terminal: str  = 'PFI0',
                 clock_rate: int  = 1000000,
                 sample_time_in_seconds: float  = 1,
                 clock_terminal: str  = None,
                 read_write_timeout: float  = 10,
                 signal_counter: str  = 'ctr2',
                 trigger_terminal: str  = None):
        
        # Save the only new attribute
        self.sample_time_in_seconds = sample_time_in_seconds

        # Calculate the number of samples per batch upto nearest integer
        num_data_samples_per_batch = int(sample_time_in_seconds * clock_rate)

        # Run the batched rate counter init to get the remaining variables
        super().__init__(daq_name = daq_name,
                         signal_terminal = signal_terminal,
                         clock_rate = clock_rate,
                         num_data_samples_per_batch = num_data_samples_per_batch,
                         clock_terminal = clock_terminal,
                         read_write_timeout = read_write_timeout,
                         signal_counter = signal_counter,
                         trigger_terminal = trigger_terminal)

    def configure(self, config_dict) -> None:
        '''
        This overwrites the parent class configure to include the new sample time 
        parameter and calculation or relevant number of samples per batch.

        **Warning**: Using this method to update the clock parameters will not work
        if the clock task has already been started. To avoid accidentially making 
        changes like this, a separate method `configure_sample_time()` is provided 
        to adjust the sample time dynamically (and the number of samples per batch 
        respectively).

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
        self.sample_time_in_seconds = config_dict.get('sample_time_in_seconds', self.sample_time_in_seconds)
        self.clock_terminal = config_dict.get('clock_terminal', self.clock_terminal)
        self.signal_counter = config_dict.get('signal_counter', self.signal_counter)
        self.read_write_timeout = config_dict.get('read_write_timeout', self.read_write_timeout)
        self.trigger_terminal = config_dict.get('trigger_terminal', self.trigger_terminal)

        # Update the number of samples per batch
        self.num_data_samples_per_batch = int(self.sample_time_in_seconds * self.clock_rate)
        # Also need to update the coutner task if it exists
        if self.edge_counter_interface and self.edge_counter_interface.counter_task:
            self.edge_counter_interface.counter_task.timing.samp_quant_samp_per_chan = self.num_data_samples_per_batch

    def configure_sample_time(self, sample_time: float) -> None:
        '''
        Configures the sample time and the number of samples per batch without adjusting
        other parameters.

        Parameters
        ----------
        sample_time : float
            Sample time in seconds to update instance to.
        '''
        # Update the sample time
        self.sample_time_in_seconds = sample_time
        # Update the number of samples per batch
        self.num_data_samples_per_batch = int(self.sample_time_in_seconds * self.clock_rate)
        # Also need to update the coutner task if it exists
        if self.edge_counter_interface and self.edge_counter_interface.counter_task:
            self.edge_counter_interface.counter_task.timing.samp_quant_samp_per_chan = self.num_data_samples_per_batch