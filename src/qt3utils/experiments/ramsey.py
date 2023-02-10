import logging
import time
import numpy as np
import nidaqmx.errors

import qt3utils.experiments.podmr
from qt3utils.errors import PulseTrainWidthError

logger = logging.getLogger(__name__)


class Ramsey:

    def __init__(self, ramsey_pulser, rfsynth, edge_counter_config,
                       photon_counter_nidaq_terminal = 'PFI0',
                       clock_nidaq_terminal = 'PFI12',
                       trigger_nidaq_terminal = 'PFI1',
                       tau_low = 1e-6,
                       tau_high = 10e-6,
                       tau_step = 0.2e-6,
                       rf_power = -25,
                       rf_frequency = 2870e6,
                       rfsynth_channel = 0):
        '''
        The input parameters to this object specify the conditions
        of an experiment and the hardware system setup.

        Hardware Settings
            ramsey_pulser - a qt3utils.pulsers.pulseblaster.PulseBlasterRamHahnDD object
            rfsynth - a qt3rfsynthcontrol.Pulser object
            edge_counter_config - a qt3utils.nidaq.config.EdgeCounter object

            NI DAQ Connections
            * photon_counter_nidaq_terminal - terminal connected to TTL pulses that indicate a photon
            * clock_nidaq_terminal - terminal connected to the clock_pulser_channel
            * trigger_nidaq_terminal - terminal connected to the trigger_pulser_channel

        Experimental parameters

            The free precession time is scanned from tau_low, to tau_high,
            in step sizes of tau_step.
            The scan is inclusive of tau_low and tau_high.
            The rf_power specifices the power of the MW source in units of dB mWatt.

            In order to control the width of the pi/2 pulses, use the ramsey_pulser
            object to set the rf_pi_pulse_width value.

        The user is responsible for analyzing the data. However, during acquisition,
        a callback function can be supplied in order to perform an analysis
        during the scan. The default callback function is defined in this module,
        qt3utils.experiments.cwodmr.aggregate_data.

        Without a callback function the raw data will be stored and could require
        prohibitive amounts of memory.

        '''

        ## TODO: assert conditions on rf width low, high and step sizes
        # to be compatible with pulser.

        self.tau_low = np.round(tau_low, 9)
        self.tau_high = np.round(tau_high, 9)
        self.tau_step = np.round(tau_step, 9)
        self.rf_power = rf_power
        self.rf_frequency = rf_frequency

        self.pulser = ramsey_pulser
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
            'tau_low':self.tau_low,
            'tau_high':self.tau_high,
            'tau_step':self.tau_step,
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

    def run(self, N_cycles = 50000,
                  post_process_function = qt3utils.experiments.podmr.simple_measure_contrast):
        """
        Performs the scan over the specificed range of free precession times.

        For each RF pulse delay, tau, some number of cycles of data are acquired. A cycle
        is one full sequence of the pulse train used in the experiment as specified
        by the supplied ramsey_pulser object.

        The N_cycles specifies the total number of these cycles to
        acquire. Your choice depends on your desired resolution or signal-to-noise
        ratio, your post-data acquisition processing choices, and the amount of memory
        available on your computer.

        For each free precession time, tau, the number of data read from the NI DAQ will be
        N_clock_ticks_per_cycle * N_cycles, where N_clock_ticks_per_cycle
        is the value returned by self.set_pulser_state(tau).

        The acquired data are stored in a data_buffer within this method. They
        may be processed with a function passed to post_process_function,
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
            RF Frequency (float),
            data_post_processing_output, or raw data trace (typically of type numpy array(dtype = float))

        Because of the mixed types in this array, the numpy array data type returned
        here is an 'object'.

        The remaining (fixed) values for analysis can be obtained from the
        self.experimental_conditions function.
        """

        #first check that the pulser width is large enough
        try:
            self.pulser.raise_for_pulse_width(self.tau_low, 0)
            #this should NEVER raise an exception. But we keep it here
            #because this kind of check should be performed for all experiments
            #before a run is started. HahnEcho and Dynamic Decoupling classes
            #should follow this pattern.
        except PulseTrainWidthError as e:
            logger.error(f'The smallest requested free precession time, self.tau_low = {self.tau_low}, is too small.')
            raise e

        self.N_cycles = int(N_cycles)

        self.rfsynth.stop_sweep()
        self.rfsynth.trigger_mode('disabled')
        self.rfsynth.set_power(self.rfsynth_channel, self.rf_power)
        self.rfsynth.set_frequency(self.rfsynth_channel, self.rf_frequency)

        self.rfsynth.rf_on(self.rfsynth_channel)
        time.sleep(0.5) #wait for RF box

        data = []
        tau_list = np.arange(self.tau_low, self.tau_high + self.tau_step, self.tau_step)

        try:
            for tau in tau_list:
                self.current_tau = np.round(tau, 9)
                logger.info(f'Free Precession Time, tau: {self.current_tau} seconds')

                self.N_clock_ticks_per_cycle = self.pulser.program_pulser_state(self.current_tau)
                self.pulser.start()

                # compute the total number of samples to be acquired and the DAQ time
                # these will be the same for each RF frequency through the scan
                self.N_clock_ticks_per_frequency = int(self.N_clock_ticks_per_cycle * self.N_cycles)
                self.daq_time = self.N_clock_ticks_per_frequency * self.pulser.clock_period
                logger.debug(f'Acquiring {self.N_clock_ticks_per_frequency} total samples')
                logger.debug(f'  sample period of {self.pulser.clock_period} seconds')
                logger.debug(f'  acquisition time of {self.daq_time} seconds')

                #self._stop_and_close_daq_tasks() #be sure tasks are closed
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

                read_samples = self.edge_counter_config.counter_reader.read_many_sample_double(
                                        data_buffer,
                                        number_of_samples_per_channel=self.N_clock_ticks_per_frequency,
                                        timeout=5)

                #should we assert that we read all samples? read_samples == self.N_clock_ticks_per_frequency

                self.edge_counter_config.counter_task.stop()
                self.pulser.stop()

                if post_process_function:
                    data_buffer = post_process_function(data_buffer, self)

                #should we make this a dictionary with self.current_tau as the key?
                data.append([self.current_tau, data_buffer])

        except Exception as e:
            logger.error(f'{type(e)}: {e}')
            raise e

        finally:
            try:
                self.edge_counter_config.counter_task.stop()
            except Exception as e:
                logger.error(f'in finally.stop. {type(e)}: {e}')
            try:
                self.edge_counter_config.counter_task.close()
            except Exception as e:
                logger.error(f'in finally.close. {type(e)}: {e}')
            #rfsynth.rf_off(self.rfsynth_channel)
            data = np.array(data, dtype=object)

            return data

