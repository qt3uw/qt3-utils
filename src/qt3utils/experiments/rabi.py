import logging
import time
import numpy as np
import nidaqmx.errors
import nidaqmx.constants
import qt3utils.experiments.common
import qt3utils.experiments.podmr

from qt3utils.errors import PulseTrainWidthError

logger = logging.getLogger(__name__)

def signal_to_background(trace, pre_trigger, aom_width, rf_pulse_duration, verbose=False,
                        aom_width_duty = 1.0):
    '''
    Assumes trace produced by qt3utils.experiments.rabi.Rabi class and
    is the aggregated data for a particular RF width.

    The inputs `pre_trigger`, `aom_width` and `rf_pulse_duration` are all in units of index of the trace.
    That is, they are in units of clock ticks.

    Assumes that trace is of shape
        * pre_trigger
        * aom_width: aom on / rf off (background)
        * rf_pulse_duration:  aom off / rf on
        * aom_width: aom on/ rf off  (signal)

    returns sum(signal) / sum(background)

    '''
    background_end = pre_trigger + int(aom_width*aom_width_duty)
    signal_start = pre_trigger + aom_width + rf_pulse_duration
    signal_end = signal_start + int(aom_width*aom_width_duty)

    background = np.sum(trace[pre_trigger:background_end])
    signal = np.sum(trace[signal_start:signal_end])

    if verbose:
        print('background')
        print(trace[pre_trigger:background_end])
        print('signal')
        print(trace[signal_start:signal_end])

    return signal / background


class Rabi(qt3utils.experiments.common.Experiment):

    def __init__(self, podmr_pulser, rfsynth, edge_counter_config,
                       photon_counter_nidaq_terminal = 'PFI0',
                       clock_nidaq_terminal = 'PFI12',
                       trigger_nidaq_terminal = 'PFI1',
                       rf_pulse_duration_low = 100e-9,
                       rf_pulse_duration_high = 10e-6,
                       rf_pulse_duration_step = 50e-9,
                       rf_power = -20,
                       rf_frequency = 2870e6,
                       rfsynth_channel = 0):
        '''
        The input parameters to this object specify the conditions
        of an experiment and the hardware system setup.

        Hardware Settings
            podmr_pulser - a qt3utils.pulsers.interface.ODMRPulser object (such as qt3utils.pulsers.qcsapphire.QCSapphPulsedODMRPulser)
            rfsynth - a qt3rfsynthcontrol.Pulser object
            edge_counter_config - a qt3utils.nidaq.config.EdgeCounter object

            NI DAQ Connections
            * photon_counter_nidaq_terminal - terminal connected to TTL pulses that indicate a photon
            * clock_nidaq_terminal - terminal connected to the clock_pulser_channel
            * trigger_nidaq_terminal - terminal connected to the trigger_pulser_channel

        Experimental parameters

            The rf width parameters define the range and step size of the scan.
                The scan is inclusive of rf_pulse_duration_low and rf_pulse_duration_high.
            The rf_power specifices the power of the MW source in units of dB mWatt.

        The user is responsible for analyzing the data. However, during acquisition,
        a callback function can be supplied in order to perform an analysis
        during the scan. The default callback function is defined in this module,
        qt3utils.experiments.cwodmr.aggregate_data.

        Without a callback function the raw data will be stored and could require
        prohibitive amounts of memory.

        '''

        ## TODO: assert conditions on rf width low, high and step sizes
        # to be compatible with pulser.

        self.rf_pulse_duration_low = np.round(rf_pulse_duration_low, 9)
        self.rf_pulse_duration_high = np.round(rf_pulse_duration_high, 9)
        self.rf_pulse_duration_step = np.round(rf_pulse_duration_step, 9)
        self.rf_power = rf_power
        self.rf_frequency = rf_frequency

        self.pulser = podmr_pulser
        #assert (type(self.pulser) = qcsapphire.Pulser) or (type(self.pulser) = pulseblaster.Pulser)
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
            'rf_pulse_duration_low':self.rf_pulse_duration_low,
            'rf_pulse_duration_high':self.rf_pulse_duration_high,
            'rf_pulse_duration_step':self.rf_pulse_duration_step,
            'rf_power':self.rf_power,
            'rf_frequency':self.rf_frequency,
            'pulser':self.pulser.experimental_conditions()
        }

    # def _stop_and_close_daq_tasks(self):
    #     try:
    #         self.edge_counter_config.counter_task.stop()
    #     except:
    #         pass
    #     try:
    #         self.edge_counter_config.counter_task.close()
    #     except:
    #         pass

    def _acquire_data_at_parameter(self, rf_pulse_duration, N_cycles = 10000,
                              post_process_function = qt3utils.experiments.podmr.simple_measure_contrast):

        self.N_cycles = int(N_cycles)

        self.current_rf_pulse_duration = np.round(rf_pulse_duration, 9)
        logger.info(f'RF Width: {self.current_rf_pulse_duration} seconds')

        self.N_clock_ticks_per_cycle = self.pulser.program_pulser_state(self.current_rf_pulse_duration)
        self.pulser.start()

        # compute the total number of samples to be acquired and the DAQ time
        # these will be the same for each RF frequency through the scan
        self.N_clock_ticks_per_frequency = int(self.N_clock_ticks_per_cycle * self.N_cycles)
        self.daq_time = self.N_clock_ticks_per_frequency * self.pulser.clock_period
        logger.debug(f'Acquiring {self.N_clock_ticks_per_frequency} total samples')
        logger.debug(f'  sample period of {self.pulser.clock_period} seconds')
        logger.debug(f'  acquisition time of {self.daq_time} seconds')

        self.edge_counter_config.configure_counter_period_measure(
            source_terminal = self.photon_counter_nidaq_terminal,
            N_samples_to_acquire_or_buffer_size = self.N_clock_ticks_per_frequency,
            clock_terminal = self.clock_nidaq_terminal,
            trigger_terminal = self.trigger_nidaq_terminal)

        self.edge_counter_config.create_counter_reader()

        data_buffer = np.zeros(self.N_clock_ticks_per_frequency)

        self.edge_counter_config.counter_task.wait_until_done()
        self.edge_counter_config.counter_task.start()

        time.sleep(self.daq_time*1.1) #pause for acquisition

        # data_buffer = self.edge_counter_config.counter_task.read(nidaqmx.constants.READ_ALL_AVAILABLE,
        #                                                          nidaqmx.constants.WAIT_INFINITELY)
        # data_buffer = np.array(data_buffer)
        # print(data_buffer.shape)
        read_samples = self.edge_counter_config.counter_reader.read_many_sample_double(
                                data_buffer,
                                number_of_samples_per_channel=self.N_clock_ticks_per_frequency,
                                timeout=np.max([5,self.daq_time*10]))

        #should we assert that we read all samples? read_samples == self.N_clock_ticks_per_frequency
        #self._stop_and_close_daq_tasks()
        self.edge_counter_config.counter_task.stop()
        self.edge_counter_config.counter_task.close()

        self.pulser.stop()

        if post_process_function:
            data_buffer = post_process_function(data_buffer, self)

        #should we make this a dictionary with self.current_rf_pulse_duration as the key?
        return [self.current_rf_pulse_duration, data_buffer]

    def run(self, N_cycles = 50000,
                  post_process_function = qt3utils.experiments.podmr.simple_measure_contrast):
        """
        Performs the scan over the specificed range of RF widths.

        For each RF width, some number of cycles of data are acquired. A cycle
        is one full sequence of the pulse train used in the experiment.
        For Rabi, a cycle is {AOM on, AOM off/RF on, AOM on, AOM off/RF off}.

        The N_cycles specifies the total number of these cycles to
        acquire. Your choice depends on your desired resolution or signal-to-noise
        ratio, your post-data acquisition processing choices, and the amount of memory
        available on your computer.

        For each width, the number of data read from the NI DAQ will be
        N_clock_ticks_per_cycle * N_cycles, where N_clock_ticks_per_cycle
        is the value returned by self.set_pulser_state(rf_pulse_duration).

        Given the way our pulser is configured, N_clock_ticks_per_cycle will
        grow linearly by rf_pulse_duration.

        The acquired data are stored in a data_buffer within this method. They
        may be analyzed with a function passed to post_process_function,
        which is useful to reduce the required memory to hold the raw data.

        After data acquisition for each width in the scan,
        the post_process_function is called and takes two arguments:
            1) data_buffer: the full trace of data acquired
            2) self: a reference to an instance of this object

        The output of post_process_function is recorded in the data
        returned by this function.

        If post_process_function = None, the full raw data trace will be kept.

        The return from this function is a numpy array. Each element of the array
        is a list of the following values
            RF width (float),
            data_post_processing_output, or raw data trace (typically of type numpy array(dtype = float))

        Because of the mixed types in this array, the numpy array data type returned
        here is an 'object'.

        The remaining (fixed) values for analysis can be obtained from the
        self.experimental_conditions function.
        """

        #first check that the pulser width is large enough
        try:
            self.pulser.raise_for_pulse_width(self.rf_pulse_duration_high)
            #quesiton: should we automatically increase the pulser width or force the user to do it?
        except PulseTrainWidthError as e:
            logger.error(f'The largest requested RF width pulse, self.rf_pulse_duration_high = {self.rf_pulse_duration_high}, is too large.')
            raise e

        self.rfsynth.stop_sweep()
        self.rfsynth.trigger_mode('disabled')
        self.rfsynth.set_power(self.rfsynth_channel, self.rf_power)
        self.rfsynth.set_frequency(self.rfsynth_channel, self.rf_frequency)

        self.rfsynth.rf_on(self.rfsynth_channel)
        time.sleep(0.5) #wait for RF box

        data = []
        rf_pulse_duration_list = np.arange(self.rf_pulse_duration_low, self.rf_pulse_duration_high + self.rf_pulse_duration_step, self.rf_pulse_duration_step)

        try:
            for rf_pulse_duration in rf_pulse_duration_list:
                data.append(self._acquire_data_at_parameter(rf_pulse_duration, N_cycles, post_process_function))

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
            #rfsynth.rf_off(self.rfsynth_channel)
            data = np.array(data, dtype=object)

            return data

