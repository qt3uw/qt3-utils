import logging
import numpy as np
import qt3utils.analysis.aggregation

logger = logging.getLogger(__name__)

class T1Coherence:

    def __init__(self, pulser, edge_counter_config,
                       aom_pulser_channel = 'A'
                       photon_counter_nidaq_terminal = 'PFI12',
                       clock_pulser_channel = 'C',
                       clock_nidaq_terminal = 'PFI0',
                       trigger_pulser_channel = 'D',
                       trigger_nidaq_terminal = 'PFI1',
                       laser_delay_low = 1e-6,
                       laser_delay_high = 100e-6,
                       laser_delay_step = 1e-6,
                       aom_width = 3e-6,
                       aom_response_time = 800e-9):
        '''
        The input parameters to this object specify the conditions
        of an experiment and the hardware system setup.

        Hardware Settings
            pulser - a qcsapphire.Pulser object (future: support for PulseBlaster)
            edge_counter_config - a qt3utils.nidaq.config.EdgeCounter object

            External Pulser Connections
            * aom_pulser_channel output controls the AOM to provide laser pulses
            * clock_pulser_channel output provides a clock input to the NI DAQ card
            * trigger_pulser_channel output provides a rising edge trigger for the NI DAQ card

            NI DAQ Connections
            * photon_counter_nidaq_terminal - terminal connected to TTL pulses that indicate a photon
            * clock_nidaq_terminal - terminal connected to the clock_pulser_channel
            * trigger_nidaq_terminal - terminal connected to the trigger_pulser_channel

        Experimental parameters

            The laser delay parameters define the range and step size of the scan.
                The scan is inclusive of laser_delay_low and laser_delay_high.

        Ancillary parameters

            A cycle is one full sequence of the pulse train used in the experiment.
            For T1 coherence measurements, a cycle is {AOM/laser on, AOM/laser off}.

        The user is responsible for analyzing the data. However, during acquisition,
        a callback function can be supplied in order to perform an analysis
        during the scan. The default callback function is defined in this module,
        qt3utils.experiments.cwodmr.aggregate_data.

        Without a callback function the raw data will be stored and could require
        prohibitive amounts of memory.

        '''

        ## TODO: assert conditions on rf width low, high and step sizes
        # to be compatible with pulser.
        raise NotImplementedError('This class is old and was never finished. Need to reimplement.')

        self.laser_delay_low = np.round(laser_delay_low, 9)
        self.laser_delay_high = np.round(laser_delay_high, 9)
        self.laser_delay_step = np.round(laser_delay_step, 9)
        self.aom_width = np.round(aom_width, 9)
        self.aom_response_time = np.round(aom_response_time, 9)

        self.pulser = pulser
        #assert (type(self.pulser) = qcsapphire.Pulser) or (type(self.pulser) = pulseblaster.Pulser)
        #assert(type(self.rfsynth) = qt3rfsynthcontrol.QT3SynthHD)
        self.aom_pulser_channel = aom_pulser_channel
        self.clock_pulser_channel = clock_pulser_channel
        self.trigger_pulser_channel = trigger_pulser_channel

        self.photon_counter_nidaq_terminal = photon_counter_nidaq_terminal
        self.clock_nidaq_terminal = clock_nidaq_terminal
        self.trigger_nidaq_terminal  = trigger_nidaq_terminal

        self.clock_period = 200e-9
        self.edge_counter_config = edge_counter_config

        raise Exception("This Class is still a work in progress. Not ready for usage.")

    def experimental_conditions(self):
        '''
        Returns a dictionary that captures the essential experimental conditions.
        '''
        return {
            'laser_delay_low':self.laser_delay_low,
            'laser_delay_high':self.laser_delay_high,
            'laser_delay_step':self.laser_delay_step,
            'aom_width':self.aom_width,
            'aom_response_time':self.aom_response_time,
            'clock_period':self.clock_period
        }

    def set_pulser_state(self, laser_delay):
        '''
        Sets the pulser to generate a signals on all channels -- AOM channel,
        RF channel, clock channel and trigger channel.

        Allows the user to set a different rf_pulse_duration after object instantiation.

        This method is used during the data aquisition phase (see self.run()),
        but is also "public" to allow the user to setup the pulser and observe
        the output signals before starting acquisition.

        Note that the pulser will be in the OFF state after calling this function.
        Call pulser.system.state(1) for the QCSapphire to start the pulser.

        A cycle is one full sequence of the pulse train used in the experiment.
        For Rabi, a cycle is {AOM on, AOM off/RF on, AOM on, AOM off/RF off}.

        returns
            int: N_clock_ticks_per_cycle

        '''
        laser_delay = np.round(laser_delay, 9)

        assert np.isclose(laser_delay % self.clock_period, 0)
        assert np.isclose(self.aom_width % self.clock_period, 0)
        assert laser_delay >= self.clock_period
        assert self.aom_width >= self.clock_period

        clock_width = self.clock_period / 2
        aom_dc_on = np.round(self.aom_width / self.clock_period).astype(int)
        aom_dc_off = np.round(laser_delay / self.clock_period).astype(int)

        N_clock_ticks_per_cycle = aom_dc_on + aom_dc_off


        self._setup_qcsapphire_pulser(  self.clock_period,
                                        self.aom_channel,
                                        self.aom_width,
                                        aom_delay,
                                        aom_dc_on,
                                        aom_dc_off,
                                        aom_wait_count,
                                        self.clock_channel,
                                        clock_width,
                                        self.trigger_channel,
                                        clock_width)

        return int(N_clock_ticks_per_cycle)


    def _setup_qcsapphire_pulser(self, period = 200e-9,
                                      aom_channel = 'A',
                                      aom_width = 1e-6,
                                      aom_dc_on = 5,
                                      aom_dc_off = 2,
                                      aom_wait_count = 0,
                                      clock_channel = 'C',
                                      clock_width = 100e-9,
                                      trigger_channel = 'D',
                                      trigger_width = 1e-6):

        self.pulser.query('*RCL 0') #restores system default
        self.pulser.system.period(period)
        self.pulser.system.mode('normal')

        # force inputs not to exceed resolution of pulser
        # should this be done inside the qcsapphire object?
        aom_width = np.round(aom_width, 9)
        aom_delay = np.round(aom_delay, 9)
        clock_width = np.round(clock_width, 9)

        ch_aom = self.pulser.channel(aom_channel)
        ch_aom.cmode('dcycle')
        ch_aom.width(aom_width)
        ch_aom.output.amplitude(5.0)
        ch_aom.pcounter(aom_dc_on)
        ch_aom.ocounter(aom_dc_off)
        ch_aom.wcounter(aom_wait_count)
        ch_aom.sync('T0')
        self.pulser.multiplex([aom_channel], aom_channel)
        ch_aom.state(1)

        ch_clock = self.pulser.channel(clock_channel)
        ch_clock.width(clock_width)
        ch_clock.sync('T0')
        self.pulser.multiplex([clock_channel], clock_channel)
        ch_clock.state(1)

        ch_trig = self.pulser.channel(trigger_channel)
        ch_trig.width(trigger_width)
        ch_trig.cmode('dcycle')
        ch_trig.pcounter(1)
        ch_trig.ocounter(2*aom_dc_on + 2*aom_dc_off - 1)
        ch_trig.wcounter(0)
        ch_trig.delay(0)
        ch_trig.sync('T0')
        self.pulser.multiplex([trigger_channel], trigger_channel)
        ch_trig.state(1)

    def _stop_and_close_daq_tasks(self):
        try:
            self.edge_counter_config.counter_task.stop()
        except:
            pass
        try:
            self.edge_counter_config.counter_task.close()
        except:
            pass

    def run(self, N_cycles = 20000,
                  post_process_function = aggregate_data):
        '''
        Performs the scan over the specificed range of RF widths.

        For each AOM/laser delay with, some number of cycles of data are acquired. A cycle
        is one full sequence of the pulse train used in the experiment.
        For Rabi, a cycle is {AOM/laser on, AOM/laser off}.

        The N_cycles specifies the total number of these cycles to
        acquire. Your choice depends on your desired resolution or signal-to-noise
        ratio, your post-data acquisition processing choices, and the amount of memory
        available on your computer.

        For each width, the number of data read from the NI DAQ will be
        N_clock_ticks_per_cycle * N_cycles, where N_clock_ticks_per_cycle
        is the value returned by self.set_pulser_state(laser_delay).

        Given the way our pulser is configured, N_clock_ticks_per_cycle will
        grow linearly by laser_delay.

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

        The return from this function is a list. Each element of the list
        is a list of the following values
            laser_delay,
            N_clock_ticks_per_cycle,
            data_post_processing_output (or raw data trace)

        The remaining (fixed) values for analysis can be obtained from the
        self.experimental_conditions function.

        '''

        self.N_cycles = int(N_cycles)


        data = []

        for laser_delay in np.arange(self.laser_delay_low, self.laser_delay_high + self.laser_delay_step, self.laser_delay_step):

            self.current_laser_delay = np.round(laser_delay, 9)

            self.N_clock_ticks_per_cycle = self.set_pulser_state(self.current_laser_delay)
            self.pulser.system.state(1) #start the pulser

            # compute the total number of samples to be acquired and the DAQ time
            # these will be the same for each RF frequency through the scan
            self.N_clock_ticks_per_frequency = int(self.N_clock_ticks_per_cycle * self.N_cycles)
            self.daq_time = self.N_clock_ticks_per_frequency * self.clock_period

            self._stop_and_close_daq_tasks() #be sure tasks are closed

            self.edge_counter_config.configure_counter_period_measure(
                source_terminal = self.photon_counter_nidaq_terminal,
                N_samples_to_acquire_or_buffer_size = self.N_clock_ticks_per_frequency,
                clock_terminal = self.clock_nidaq_terminal,
                trigger_terminal = self.trigger_nidaq_terminal)

            self.edge_counter_config.create_counter_reader()

            logger.info(f'Laser Delay: {self.current_laser_delay*1e-6} microseconds')
            logger.info(f'Acquiring {self.N_clock_ticks_per_frequency} samples')
            logger.info(f'   Sample period of {self.clock_period} seconds')
            logger.info(f'   acquisition time of {daq_time} seconds')

            data_buffer = np.zeros(self.N_clock_ticks_per_frequency)

            self.edge_counter_config.counter_task.wait_until_done()
            self.edge_counter_config.counter_task.start()
            time.sleep(daq_time*1.1) #pause for acquisition

            read_samples = self.edge_counter_config.counter_reader.read_many_sample_double(
                                    data_buffer,
                                    number_of_samples_per_channel=self.N_clock_ticks_per_frequency,
                                    timeout=5)

            #should we assert that we read all samples? read_samples == self.N_clock_ticks_per_frequency

            self._stop_and_close_daq_tasks()

            if post_process_function:
                data_buffer = post_process_function(data_buffer, self)

            #should we make this a dictionary with self.current_laser_delay as the key?
            data.append([self.current_laser_delay,
                         self.N_clock_ticks_per_cycle,
                         data_buffer])

        return data


def aggregate_data(data_buffer, rabi):
    '''
    Calls qt3utils.analysis.aggregation.reshape_sum_trace, where
        cwodmr.N_cycles = N_rows
        cwodmr.N_clock_ticks_per_cycle = N_samples_per_row

    '''
    return qt3utils.analysis.aggregation.reshape_sum_trace(data_buffer,
                                                           rabi.N_cycles,
                                                           rabi.N_clock_ticks_per_cycle)
