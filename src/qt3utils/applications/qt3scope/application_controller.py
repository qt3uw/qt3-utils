import logging
import time

import numpy as np

from qt3utils.hardware.nidaq.timed_batch_signal_reader import TimedBatchSignalReader

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ScopeController:
    '''
    This is the main class which coordinates the collection of data.
    '''

    def __init__(self,
                 counter_controller: TimedBatchSignalReader):

        self.counter_controller = counter_controller

        # Time over which measurements were taken
        self.readout_time = None

        # Flag to check if running
        self.running = False

    def read_counts_continuous(self,
                               sample_time: float,
                               get_rate: bool = True):
        '''
        This method reads out the counts quasi-continuously.

        Parameters
        ----------
        sample_time : float
            The time in seconds per sample on the DAQ board. The DAQ will be progrmamed
            to sample the counter for sample_time seconds. Note that the actual time
            between samples will be slightly larger due to computational overhead; see
            the Notes section below.
        get_rate : bool
            If `True` (default behavior), the return value will be the count rate
            (determined by the sample_time input -- not the DAQ timing! See the Notes).
            On the other hand, if `False` then the counts over each samples are instead
            returned.

        Yields
        ------
        float
            The count rate (or raw number of counts) measured over `sample_time` seconds,
            repeating until the internal `self.running` flag is set to `False`.

        Notes
        -----
        The specific timing of the samples will vary slightly from the predicted rate of
        1/sample_time as there is some computational overhead involved with the sampling
        itself (computations before/after the actual sampling, etc.) As a result, this
        method may return slightly incorrectly timed data, especially over long periods
        of time where the small errors (likely < 0.1%) can accumulate.

        To deal with this issue, we provide a class attribute `self.readout_time`, which
        measures (in seconds using the python `time` module) the length of time between
        the start and end of the sampling. While this in and of itself may be slightly
        inaccurate, you can use this to correct for the accumulated errors over long time
        periods. Such correction is not implemented directly into this method, however.

        Also note that the normalization of the counts (to get the count rate) uses the
        provided `sample_time` parameter and does not use the DAQ "num_samples" output.
        As a consequence, the actual DAQ sample time might vary slightly due to dropped
        samples (see the documentation for
            qt3utils.hardware.nidaq.counters.NidaqBatchedRateCounter
        for more information), however dropped samples are rare and typically do not
        correspond to any meaningful time difference (< 10 μs).
        '''
        # Set the running flag
        self.running = True

        # Set the scaling factor (equals 1 for getting counts explicitly or 1/sample_time
        # if returning the count rate). We do this out front so that each yield call does
        # not need to check if we must compute the rate.
        if get_rate:
            scale = 1 / sample_time
        else:
            scale = 1

        # Start up the counter
        self.counter_controller.start()

        # Configure the DAQ sampling time
        self.counter_controller.configure_sample_time(sample_time=sample_time)

        # Record the starting time
        start_time = time.time()

        while self.running:

            # While the counter is running, yield the counts, scaled by `scale`
            yield (self.counter_controller.sample_batch_counts() * scale)

        # Get the final time
        stop_time = time.time()
        self.readout_time = stop_time - start_time

        # Stop the counter
        self.counter_controller.stop()

    def read_counts_batches(self,
                            sample_time: float,
                            batch_time: float,
                            get_rate: bool = True):
        '''
        This method reads out counts in discrete batches of length `batch_time` in
        seconds. This is useful in cases where the precise timing of the individual
        count samples in relation to each other is important. Recall that the
        `self.read_counts_continuous()` method suffers from a slightly decreased sample
        rate due (compared to the theoretical `1/sample_time` rate) to the overhead of
        communicating with the DAQ and passing data around.

        This method works around this issue by scheduling readout of a set number of
        samples sequentially and only handing data off to the software after each "batch"
        lasting `batch_time` seconds long. This way, the overhead time cost only occurs
        after each batch and so the timing between samples is preserved with in the
        batch. Use this method if the exact timing between data points is important.

        Parameters
        ----------
        sample_time : float
            The time in seconds per sample on the DAQ board. Each data point in the
            output will correspond to this many seconds long.
        batch_time : float
            The length of time in seconds that samples are acquired over. Timing between
            batches is not guaranteed as it depends on the computational overhead.
        get_rate : bool
            If `True` (default behavior), the return value will be the count rate.

        Yields
        ------
        np.ndarray
            A vector of the counts/count rate as a function of time over the batch.
        '''
        # Set the running flag
        self.running = True

        # Set the scaling factor (equals 1 for getting counts explicitly or 1/sample_time
        # if returning the count rate). We do this out front so that each yield call does
        # not need to check if we must compute the rate.
        if get_rate:
            scale = 1 / sample_time
        else:
            scale = 1

        # Compute the number of samples to record per batch. There will be some slight
        # truncation error if the `sample_time` is not a factor of `batch_time`.
        n_samples = int(batch_time / sample_time)
        # Note that the terminology of samples and batches used here is distinct from the
        # low-level definition of samples and batches. At the low level, data is read out
        # once per clock cycle where each readout is referred to as a "sample". The sum
        # of clock cycle "samples" over `sample_time` is called at this level a "batch".
        # In this application, each low-level "batch" is a sample and we take `n_samples`
        # of these batched readout samples per yield (the "batch" at this level).
        # If attempting to modify this method, DO NOT modify the low level hardware code!

        # Start up the counter
        self.counter_controller.start()

        # Configure the DAQ sampling time
        self.counter_controller.configure_sample_time(sample_time=sample_time)

        # Record the starting time
        start_time = time.time()

        while self.running:

            # While the counter is running, yield the counts, scaled by `scale`
            yield (self.counter_controller.sample_nbatches_counts(n_batches=n_samples) * scale)

        # Get the final time
        stop_time = time.time()
        self.readout_time = stop_time - start_time

        # Stop the counter
        self.counter_controller.stop()
