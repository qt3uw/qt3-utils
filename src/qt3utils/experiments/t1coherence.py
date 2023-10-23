import logging
import numpy as np
import time

import qt3utils.experiments.common
import qt3utils.errors

logger = logging.getLogger(__name__)

def signal_and_background(data_buffer, experiment):
    trace = qt3utils.experiments.common.aggregate_sum(data_buffer, experiment)

    aom_width = int((experiment.pulser.aom_pulse_duration_time + experiment.pulser.aom_response_time) // experiment.pulser.clock_period)
    aom_width += int(xperiment.pulser.clock_delay // experiment.pulser.clock_period)  # we add two clock periods to handle the clock_delay in the experiment

    start_background = 0
    end_background = start_background + aom_width
    background_counts = np.sum(trace[start_background:end_background])

    start_signal = len(trace) // 2
    end_signal = start_signal + aom_width
    signal_counts = np.sum(trace[start_signal:end_signal])

    return [signal_counts, background_counts]
def contrast_calculator(data_buffer, experiment):
    signal_counts, background_counts = signal_and_background(data_buffer, experiment)
    contrast = signal_counts / background_counts

    return contrast

def contrast_calculator_with_error(data_buffer, experiment):
    signal_counts, background_counts = signal_and_background(data_buffer, experiment)

    contrast = signal_counts / background_counts
    contrast_error = (np.sqrt(signal_counts) / signal_counts) ** 2
    contrast_error += (np.sqrt(background_counts) / background_counts) ** 2
    contrast_error = np.sqrt(contrast_error) * contrast

    return [contrast, contrast_error]

class T1Coherence(qt3utils.experiments.common.Experiment):

    def __init__(self, t1pulser, edge_counter_config,
                       photon_counter_nidaq_terminal = 'PFI0',
                       clock_nidaq_terminal = 'PFI12',
                       trigger_nidaq_terminal = 'PFI1',
                       tau_delay_low=1e-6,
                       tau_delay_high=100e-6,
                       tau_delay_step=1e-6):
        '''
        The input parameters to this object specify the conditions
        of an experiment and the hardware system setup.

        Hardware Settings
            t1pulser - a qt3utils.pulsers.interface.ODMRPulser object (such as qt3utils.pulsers.pulseblaster.PulserBlasterT1)
            edge_counter_config - a qt3utils.nidaq.config.EdgeCounter object

            NI DAQ Connections
            * photon_counter_nidaq_terminal - terminal connected to TTL pulses that indicate a photon
            * clock_nidaq_terminal - terminal connected to the clock_pulser_channel
            * trigger_nidaq_terminal - terminal connected to the trigger_pulser_channel

        Experimental parameters

            The tau parameters define the range and step size of the scan.


        The user is responsible for analyzing the data. However, during acquisition,
        a callback function can be supplied in order to perform an analysis
        during the scan. The default callback function is defined in this module,
        qt3utils.experiments.cwodmr.aggregate_data.

        Without a callback function the raw data will be stored and could require
        prohibitive amounts of memory.

        '''
        self.tau_delay_low = tau_delay_low
        self.tau_delay_high = tau_delay_high
        self.tau_delay_step = tau_delay_step
        self.pulser = t1pulser

        self.photon_counter_nidaq_terminal = photon_counter_nidaq_terminal
        self.clock_nidaq_terminal = clock_nidaq_terminal
        self.trigger_nidaq_terminal  = trigger_nidaq_terminal

        self.edge_counter_config = edge_counter_config

    def experimental_conditions(self):
        '''
        Returns a dictionary that captures the essential experimental conditions.
        '''
        return {
            'tau_delay_low':self.tau_delay_low,
            'tau_delay_high':self.tau_delay_high,
            'tau_delay_step':self.tau_delay_step,
            'pulser':self.pulser.experimental_conditions()
        }

    def run(self, N_cycles=50000,
                  post_process_function=contrast_calculator,
                  random_order=False, *args, **kwargs):
        '''
        Performs the scan over the specificed range of readout delays.

        For each tau_delay value, some number of cycles of data are acquired. A cycle
        is one full sequence of the pulse train used in the experiment. For T1,
        a cycle is {<fill in the sequence>}.

        The N_cycles specifies the total number of these cycles to
        acquire at each tau. The choice depends on the desired resolution or signal-to-noise
        ratio, the post-data acquisition processing function, and the amount of memory
        available on the computer.

        For each tau_delay, the number of data points read from the NI DAQ will be
        N_clock_ticks_per_cycle * N_cycles, where N_clock_ticks_per_cycle
        is the value returned by self.pulser.program_pulser_state().

        These data are found in a data_buffer within this method. They
        may be analyzed with a function passed to post_process_function,
        which is useful to reduce the required memory to hold the raw data.

        After data acquisition for each tau_delay in the scan,
        the post_process_function function is called and takes two arguments:
            1) data_buffer: the full trace of data acquired
            2) self: a reference to an instance of this object

        The output of post_process_function is recorded in the data
        returned by this function.

        If post_process_function = None, the full raw data trace will be kept.

        The return from this function is a list. Each element of the list
        is a list of the following values
            tau_delay,
            data_post_processing_output (or raw data trace)

        The remaining (fixed) values for analysis can be obtained from the
        self.experimental_conditions function.

        '''

        self.N_cycles = int(N_cycles)

        # Because we fix the full cycle length for each tau delay,
        # we do the following to extract the number of clock ticks per cycle,
        # calculate the total number of data samples we acquire from the DAQ,
        # and calculate the amount of time it will take to acquire data.
        # We can thus configure the DAQ Task once at the beginning of the run
        # without needing to close the resource
        
        self.N_clock_ticks_per_cycle = self.pulser.program_pulser_state(self.tau_delay_low)
        self.pulser.start()  # start the pulser

        self.N_clock_ticks_per_tau = int(self.N_clock_ticks_per_cycle * self.N_cycles)
        self.daq_time = self.N_clock_ticks_per_tau * self.pulser.clock_period

        self.edge_counter_config.configure_counter_period_measure(
            source_terminal=self.photon_counter_nidaq_terminal,
            N_samples_to_acquire_or_buffer_size=self.N_clock_ticks_per_tau,
            clock_terminal=self.clock_nidaq_terminal,
            trigger_terminal=self.trigger_nidaq_terminal)

        self.edge_counter_config.create_counter_reader()
        data = []

        taus_to_scan = np.arange(self.tau_delay_low, self.tau_delay_high + self.tau_delay_step, self.tau_delay_step)
        if random_order:
            np.random.shuffle(taus_to_scan)
        try:
            for tau_delay in taus_to_scan:

                self.current_tau = tau_delay
                n_clock_ticks_per_cycle = self.pulser.program_pulser_state(self.current_tau)
                self.pulser.start()
                if n_clock_ticks_per_cycle != self.N_clock_ticks_per_cycle:
                    raise qt3utils.errors.PulseTrainWidthError('''N clock ticks for the pulse sequence
                    different from the beginning of the run. The pulser has unexpectedly changed. Exiting run.''')

                logger.info(f'tau {self.current_tau:.2e}')
                logger.debug(f'Acquiring {self.N_clock_ticks_per_tau} samples')
                logger.debug(f'   Sample period of {self.pulser.clock_period} seconds')
                logger.debug(f'   acquisition time of {self.daq_time} seconds')

                data_buffer = np.zeros(self.N_clock_ticks_per_tau)

                self.edge_counter_config.counter_task.wait_until_done()
                self.edge_counter_config.counter_task.start()
                time.sleep(self.daq_time*1.1) #pause for acquisition

                read_samples = self.edge_counter_config.counter_reader.read_many_sample_double(
                                        data_buffer,
                                        number_of_samples_per_channel=self.N_clock_ticks_per_tau,
                                        timeout=5)

                #should we assert that we read all samples? read_samples == self.N_clock_ticks_per_tau
                self.edge_counter_config.counter_task.stop()
                if post_process_function:
                    data_buffer = post_process_function(data_buffer, self)

                #should we make this a dictionary with self.current_tau as the key?
                data.append([self.current_tau,
                             data_buffer])

        except Exception as e:
            logger.error(f'{type(e)}: {e}')
            raise e

        finally:
            try:
                self.edge_counter_config.counter_task.stop()
            except Exception as e:
                pass
            try:
                self.edge_counter_config.counter_task.close()
            except Exception as e:
                pass

            return data

    def build_spectrum_animator(self):
        pass
