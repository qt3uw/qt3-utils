import logging
import time
import numpy as np
import qt3utils.analysis.aggregation

logger = logging.getLogger(__name__)


def aggregate_data(data_buffer, experiment):
    '''
    Calls qt3utils.analysis.aggregation.reshape_sum_trace, where
        cwodmr.N_cycles = N_rows
        cwodmr.N_clock_ticks_per_cycle = N_samples_per_row

    '''
    return qt3utils.analysis.aggregation.reshape_sum_trace(data_buffer,
                                                           experiment.N_cycles,
                                                           experiment.N_clock_ticks_per_cycle)

class PulsedODMR:

    def __init__(self, podmr_pulser, rfsynth, edge_counter_config,
                       photon_counter_nidaq_terminal = 'PFI0',
                       clock_nidaq_terminal = 'PFI12',
                       trigger_nidaq_terminal = 'PFI1',
                       freq_low = 2820e6,
                       freq_high = 2920e6,
                       freq_step = 1e6,
                       rf_power = -20,
                       rfsynth_channel = 0):
        '''
        The input parameters to this object specify the conditions
        of an experiment and the hardware system setup.

        Hardware Settings
            podmr_pulser - a qt3utils.experiments.pulsers.interface.ODMRPulser object (such as qt3utils.experiments.pulsers.qcsapphire.QCSapphPulsedODMRPulser)
            rfsynth - a qt3rfsynthcontrol.Pulser object
            The rfsynth_channel specifies which output channel from the Windfreak RF SynthHD is used to provde the RF signal (either 0 or 1)
            edge_counter_config - a qt3utils.nidaq.config.EdgeCounter object

            NI DAQ Connections
            * photon_counter_nidaq_terminal - terminal connected to TTL pulses that indicate a photon
            * clock_nidaq_terminal - terminal connected to the clock_pulser_channel
            * trigger_nidaq_terminal - terminal connected to the trigger_pulser_channel

        Experimental parameters

            The frequency parameters define the range and step size of the scan.
                The scan is inclusive of freq_low and freq_high.
            The rf_power specifices the power of the MW source in units of dB mWatt.

        The user is responsible for analyzing the data. However, during acquisition,
        a callback function can be supplied in order to perform an analysis
        during the scan. The default callback function is defined in this module,
        qt3utils.experiments.cwodmr.aggregate_data.

        Without a callback function the raw data will be stored and could require
        prohibitive amounts of memory.

        '''
        self.freq_low = freq_low
        self.freq_high = freq_high
        self.freq_step = freq_step
        self.rf_power = rf_power

        self.pulser = podmr_pulser
        #assert (type(self.pulser) = qt3utils.experiments.pulsers.interface.ODMRPulser

        self.rfsynth = rfsynth
        self.rfsynth_channel = rfsynth_channel
        #assert(type(self.rfsynth) = qt3rfsynthcontrol.QT3SynthHD)

        self.photon_counter_nidaq_terminal = photon_counter_nidaq_terminal
        self.clock_nidaq_terminal = clock_nidaq_terminal
        self.trigger_nidaq_terminal  = trigger_nidaq_terminal

        self.edge_counter_config = edge_counter_config

    def experimental_conditions(self):
        '''
        Returns a dictionary that captures the essential experimental conditions.
        '''
        return {
            'freq_low':self.freq_low,
            'freq_high':self.freq_high,
            'freq_step':self.freq_step,
            'rf_power':self.rf_power,
            'pulser':self.pulser.experimental_conditions()
        }

    def _stop_and_close_daq_tasks(self):
        try:
            self.edge_counter_config.counter_task.stop()
        except:
            pass
        try:
            self.edge_counter_config.counter_task.close()
        except:
            pass

    def run(self, N_cycles = 500000,
                  post_process_function = aggregate_data):
        '''
        Performs the PulsedODMR scan over the specificed range of frequencies.

        For each frequency, some number of cycles of data are acquired. A cycle
        is one full sequence of the pulse train used in the experiment. For PulsedODMR,
        a cycle is {AOM on, AOM off/RF on, AOM on, AOM off/RF off}.

        The N_cycles specifies the total number of these cycles to
        acquire. Your choice depends on your desired resolution or signal-to-noise
        ratio, your post-data acquisition processing choices, and the amount of memory
        available on your computer.

        For each frequency, the number of data read from the NI DAQ will be
        N_clock_ticks_per_cycle * N_cycles, where N_clock_ticks_per_cycle
        is the value returned by self.pulser.program_pulser_state().

        These data are found in a data_buffer within this method. They
        may be analyzed with a function passed to the argument `post_process_function`,
        which is useful to reduce the required memory to hold the raw data.

        After data acquisition for each frequency in the scan,
        the post_process_function function is called and takes two arguments:
            1) data_buffer: the full trace of data acquired
            2) self: a reference to an instance of this object

        The output of post_process_function is recorded in the data
        returned by this function.

        If post_process_function = None, the full raw data trace will be kept.

        The return from this function is a list. Each element of the list
        is a list of the following values
            RF Frequency,
            data_post_processing_output (or raw data trace)

        The remaining (fixed) values for analysis can be obtained from the
        self.experimental_conditions function.


        '''

        self.N_cycles = int(N_cycles)

        self.rfsynth.stop_sweep()
        self.rfsynth.trigger_mode('disabled')
        self.rfsynth.set_power(self.rfsynth_channel, self.rf_power)
        self.rfsynth.rf_on(self.rfsynth_channel)
        time.sleep(1) #wait for RF box to fully turn on

        self.N_clock_ticks_per_cycle = self.pulser.program_pulser_state()
        self.pulser.start() #start the pulser

        # compute the total number of samples to be acquired and the DAQ time
        # these will be the same for each RF frequency through the scan
        self.N_clock_ticks_per_frequency = int(self.N_clock_ticks_per_cycle * self.N_cycles)
        self.daq_time = self.N_clock_ticks_per_frequency * self.pulser.clock_period

        self.edge_counter_config.configure_counter_period_measure(
            source_terminal = self.photon_counter_nidaq_terminal,
            N_samples_to_acquire_or_buffer_size = self.N_clock_ticks_per_frequency,
            clock_terminal = self.clock_nidaq_terminal,
            trigger_terminal = self.trigger_nidaq_terminal)

        self.edge_counter_config.create_counter_reader()

        data = []
        rf_frequency_list = np.arange(self.freq_low, self.freq_high + self.freq_step, self.freq_step)

        for rf_freq in rf_frequency_list:

            self.current_rf_freq = np.round(rf_freq, 9)
            self.rfsynth.set_frequency(self.rfsynth_channel, self.current_rf_freq)

            logger.info(f'RF frequency: {self.current_rf_freq*1e-9} GHz')
            logger.debug(f'Acquiring {self.N_clock_ticks_per_frequency} samples')
            logger.debug(f'   Sample period of {self.pulser.clock_period} seconds')
            logger.debug(f'   acquisition time of {self.daq_time} seconds')

            data_buffer = np.zeros(self.N_clock_ticks_per_frequency)

            self.edge_counter_config.counter_task.wait_until_done()
            self.edge_counter_config.counter_task.start()
            time.sleep(self.daq_time*1.1) #pause for acquisition

            read_samples = self.edge_counter_config.counter_reader.read_many_sample_double(
                                    data_buffer,
                                    number_of_samples_per_channel=self.N_clock_ticks_per_frequency,
                                    timeout=5)

            #should we assert that we read all samples? read_samples == self.N_clock_ticks_per_frequency
            self.edge_counter_config.counter_task.stop()
            if post_process_function:
                data_buffer = post_process_function(data_buffer, self)

            #should we make this a dictionary with self.current_rf_freq as the key?
            data.append([self.current_rf_freq,
                         data_buffer])


        self._stop_and_close_daq_tasks()
        #rfsynth.rf_off(self.rfsynth_channel)

        return data
