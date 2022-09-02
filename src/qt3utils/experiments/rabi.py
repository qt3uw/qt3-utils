import logging
import time
import numpy as np
import qt3utils.analysis.aggregation
import nidaqmx.errors

logger = logging.getLogger(__name__)

#must define this function before class Rabi
def aggregate_data(data_buffer, rabi):
    '''
    Calls qt3utils.analysis.aggregation.reshape_sum_trace, where
        cwodmr.N_cycles = N_rows
        cwodmr.N_clock_ticks_per_cycle = N_samples_per_row

    '''
    return qt3utils.analysis.aggregation.reshape_sum_trace(data_buffer,
                                                           rabi.N_cycles,
                                                           rabi.N_clock_ticks_per_cycle)

class Rabi:

    def __init__(self, pulser, rfsynth, edge_counter_config,
                       aom_pulser_channel = 'A',
                       rf_pulser_channel = 'B',
                       photon_counter_nidaq_terminal = 'PFI12',
                       clock_pulser_channel = 'C',
                       clock_nidaq_terminal = 'PFI0',
                       trigger_pulser_channel = 'D',
                       trigger_nidaq_terminal = 'PFI1',
                       rf_width_low = 100e-9,
                       rf_width_high = 10e-6,
                       rf_width_step = 50e-9,
                       rf_power = -20,
                       rf_frequency = 2870e6,
                       aom_width = 3e-6,
                       aom_response_time = 800e-9,
                       rf_response_time = 200e-9,
                       pre_rf_pad = 100e-9,
                       post_rf_pad = 100e-9,
                       full_cycle_width = 20e-6,
                       rfsynth_channel = 0,
                       rf_pulse_justify = 'center',
                       t1_measurement = False):
        '''
        The input parameters to this object specify the conditions
        of an experiment and the hardware system setup.

        Hardware Settings
            pulser - a qcsapphire.Pulser object (future: support for PulseBlaster)
            rfsynth - a qt3rfsynthcontrol.Pulser object
            edge_counter_config - a qt3utils.nidaq.config.EdgeCounter object

            External Pulser Connections
            * aom_pulser_channel output controls the AOM to provide laser pulses
            * rf_pulser_channel output controls an RF switch
            * clock_pulser_channel output provides a clock input to the NI DAQ card
            * trigger_pulser_channel output provides a rising edge trigger for the NI DAQ card

            NI DAQ Connections
            * photon_counter_nidaq_terminal - terminal connected to TTL pulses that indicate a photon
            * clock_nidaq_terminal - terminal connected to the clock_pulser_channel
            * trigger_nidaq_terminal - terminal connected to the trigger_pulser_channel

        Experimental parameters

            The rf width parameters define the range and step size of the scan.
                The scan is inclusive of rf_width_low and rf_width_high.
            The rf_power specifices the power of the MW source in units of dB mWatt.

            IMPORTANT: when using the QCSapphire pulser, the minimum resolution is 10e-9
            seconds. Thus, all pulse times are rounded to the nearest 10 ns.
            For example, if you specify aom_response_time = 875e-9, this class will
            round that to 880e-9.

        Ancillary parameters

            The rf_frequency specifies the amount of time the RF / MW signal is on
            during each data acquisition cycle. A cycle is one full sequence
            of the pulse train used in the experiment.  For Rabi, a cycle is
            {AOM on, AOM off/RF on, AOM on, AOM off/RF off}.

            The rfsynth_channel specifies which output channel from the Windfreak
            RF SynthHD is used to provde the RF signal (either 0 or 1)

            full_cycle_width must be an integer multiple of self.clock_period, which
            is hardcoded as 200e-9

        The user is responsible for analyzing the data. However, during acquisition,
        a callback function can be supplied in order to perform an analysis
        during the scan. The default callback function is defined in this module,
        qt3utils.experiments.cwodmr.aggregate_data.

        Without a callback function the raw data will be stored and could require
        prohibitive amounts of memory.

        '''

        ## TODO: assert conditions on rf width low, high and step sizes
        # to be compatible with pulser.

        self.rf_width_low = np.round(rf_width_low, 9)
        self.rf_width_high = np.round(rf_width_high, 9)
        self.rf_width_step = np.round(rf_width_step, 9)
        self.rf_power = rf_power
        self.rf_frequency = rf_frequency
        self.aom_width = np.round(aom_width, 8)
        self.aom_response_time = np.round(aom_response_time, 8)
        self.rf_response_time = np.round(rf_response_time, 8)
        self.post_rf_pad = np.round(post_rf_pad, 8)
        self.pre_rf_pad = np.round(pre_rf_pad, 8)
        self.full_cycle_width = np.round(full_cycle_width, 8)
        self.rf_pulse_justify = rf_pulse_justify

        self.t1_measurement = t1_measurement
        self.pulser = pulser
        #assert (type(self.pulser) = qcsapphire.Pulser) or (type(self.pulser) = pulseblaster.Pulser)
        self.rfsynth = rfsynth
        self.rfsynth_channel = rfsynth_channel
        #assert(type(self.rfsynth) = qt3rfsynthcontrol.QT3SynthHD)
        self.aom_pulser_channel = aom_pulser_channel
        self.rf_pulser_channel = rf_pulser_channel
        self.clock_pulser_channel = clock_pulser_channel
        self.trigger_pulser_channel = trigger_pulser_channel

        self.photon_counter_nidaq_terminal = photon_counter_nidaq_terminal
        self.clock_nidaq_terminal = clock_nidaq_terminal
        self.trigger_nidaq_terminal  = trigger_nidaq_terminal

        self.clock_period = 200e-9
        self.trigger_width = 500e-9
        self.edge_counter_config = edge_counter_config

    def experimental_conditions(self):
        '''
        Returns a dictionary that captures the essential experimental conditions.
        '''
        return {
            'rf_width_low':self.rf_width_low,
            'rf_width_high':self.rf_width_high,
            'rf_width_step':self.rf_width_step,
            'rf_power':self.rf_power,
            'rf_frequency':self.rf_frequency,
            'aom_width':self.aom_width,
            'aom_response_time':self.aom_response_time,
            'rf_response_time':self.rf_response_time,
            'post_rf_pad':self.post_rf_pad,
            'pre_rf_pad':self.pre_rf_pad,
            'full_cycle_width':self.full_cycle_width,
            'clock_period':self.clock_period
        }

    def reset_pulser(self, num_resets = 2):

        # the QC Sapphire can enter weird states sometimes.
        # Observation shows that multiple resets, followed by some delay
        # results in a steady state for the pulser
        for i in range(num_resets):
            self.pulser.set_all_state_off()
            time.sleep(1)
        self.pulser.query('*RST')
        self.pulser.system.mode('normal')

    def set_pulser_state(self, rf_width):
        '''
        Sets the pulser to generate a signals on all channels -- AOM channel,
        RF channel, clock channel and trigger channel.

        Allows the user to set a different rf_width after object instantiation.

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
        assert self.rf_pulse_justify in ['left', 'center', 'right']

        self.reset_pulser() # based on experience, we have to do this in order for the system to behave correctly... :(
        self.pulser.system.period(self.clock_period)

        on_count_aom_channel = 1
        off_count_aom_channel = np.round(self.full_cycle_width/self.clock_period,8).astype(int) - on_count_aom_channel
        channel = self.pulser.channel(self.aom_pulser_channel)
        channel.mode('dcycle')
        channel.width(self.aom_width)
        channel.pcounter(on_count_aom_channel)
        channel.ocounter(off_count_aom_channel)

        rf_width = np.round(rf_width,8)

        if self.rf_pulse_justify == 'center':
            delay_rf_channel = self.aom_width + (self.full_cycle_width - self.aom_width)/2 - rf_width/2 - self.rf_response_time
        if self.rf_pulse_justify == 'left':
            delay_rf_channel = self.aom_width + self.aom_response_time + self.pre_rf_pad - self.rf_response_time
        if self.rf_pulse_justify == 'right':
            delay_rf_channel = self.full_cycle_width - self.post_rf_pad - rf_width - self.rf_response_time + self.aom_response_time

        #todo: check to be sure the RF pulse is fully outside of the aom response + pad time, raise exception if violated

        delay_rf_channel = np.round(delay_rf_channel,8)
        on_count_rf_channel = 1
        off_count_rf_channel = np.round(2*self.full_cycle_width/self.clock_period).astype(int) - on_count_rf_channel
        channel = self.pulser.channel(self.rf_pulser_channel)
        channel.mode('dcycle')
        channel.width(rf_width)
        channel.delay(delay_rf_channel)
        channel.pcounter(on_count_rf_channel)
        channel.ocounter(off_count_rf_channel)

        channel = self.pulser.channel(self.clock_pulser_channel)
        channel.mode('normal')
        channel.width(np.round(self.clock_period/2, 8))
        channel.delay(0)

        channel = self.pulser.channel(self.trigger_pulser_channel)
        channel.mode('dcycle')
        channel.width(np.round(self.trigger_width,8))
        channel.delay(0)
        channel.pcounter(1)
        channel.ocounter(np.round(2*self.full_cycle_width/self.clock_period).astype(int) - 1)

        self.pulser.channel(self.aom_pulser_channel).state(1)
        self.pulser.channel(self.rf_pulser_channel).state(1)
        self.pulser.channel(self.clock_pulser_channel).state(1)
        self.pulser.channel(self.trigger_pulser_channel).state(1)

        return np.round(self.full_cycle_width / self.clock_period).astype(int)

    def set_pulser_state_old(self, rf_width):
        '''
        Sets the pulser to generate a signals on all channels -- AOM channel,
        RF channel, clock channel and trigger channel.

        Allows the user to set a different rf_width after object instantiation.

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
        rf_width = np.round(rf_width, 9)

        # assert np.isclose(rf_width % self.clock_period, 0)
        # assert np.isclose(self.aom_width % self.clock_period, 0)
        # fails in some cases due to machine errors... TODO fix this

        # assert rf_width >= self.clock_period
        # assert self.aom_width >= self.clock_period


        clock_width = self.clock_period / 2
        aom_dc_on = int(self.aom_width / self.clock_period)
        rf_dc_on = int(rf_width / self.clock_period)
        aom_delay = 0
        rf_post_pad = int(self.post_rf_pad / self.clock_period)
        N_clock_ticks_per_cycle = 2*aom_dc_on + 2*rf_dc_on + 2*rf_post_pad
        rf_delay = self.aom_width + self.aom_response_time + self.pre_rf_pad

        rf_dc_off = N_clock_ticks_per_cycle - rf_dc_on
        rf_wait_count = 0
        aom_wait_count = 0
        aom_dc_off = rf_dc_on + rf_post_pad

        self._setup_qcsapphire_pulser(  self.clock_period,
                                        self.aom_pulser_channel,
                                        self.aom_width,
                                        aom_delay,
                                        aom_dc_on,
                                        aom_dc_off,
                                        aom_wait_count,
                                        self.rf_pulser_channel,
                                        rf_width ,
                                        rf_delay,
                                        rf_dc_on,
                                        rf_dc_off,
                                        rf_wait_count,
                                        self.clock_pulser_channel,
                                        clock_width,
                                        self.trigger_pulser_channel,
                                        clock_width)

        return int(N_clock_ticks_per_cycle)


    def _setup_qcsapphire_pulser(self, period = 200e-9,
                                      aom_channel = 'A',
                                      aom_width = 1e-6,
                                      aom_delay = 0,
                                      aom_dc_on = 5,
                                      aom_dc_off = 2,
                                      aom_wait_count = 0,
                                      rf_channel = 'B',
                                      rf_width = 400e-9,
                                      rf_delay = 1000e-9,
                                      rf_dc_on = 1,
                                      rf_dc_off = 13,
                                      rf_wait_count = 0,
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
        rf_width = np.round(rf_width, 9)
        rf_delay = np.round(rf_delay, 9)
        clock_width = np.round(clock_width, 9)

        ch_aom = self.pulser.channel(aom_channel)
        ch_aom.cmode('dcycle')
        ch_aom.width(aom_width)
        ch_aom.delay(aom_delay)
        ch_aom.output.amplitude(5.0)
        ch_aom.pcounter(aom_dc_on)
        ch_aom.ocounter(aom_dc_off)
        ch_aom.wcounter(aom_wait_count)
        ch_aom.sync('T0')
        self.pulser.multiplex([aom_channel], aom_channel)
        ch_aom.state(1)

        ch_rf = self.pulser.channel(rf_channel)
        ch_rf.cmode('dcycle')
        ch_rf.width(rf_width)
        ch_rf.delay(rf_delay)
        ch_rf.output.amplitude(5.0)
        ch_rf.pcounter(rf_dc_on)
        ch_rf.ocounter(rf_dc_off)
        ch_rf.wcounter(rf_wait_count)
        ch_rf.sync('T0')
        self.pulser.multiplex([rf_channel], rf_channel)
        ch_rf.state(1)

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

    def run(self, N_cycles = 100000,
                  post_process_function = aggregate_data,
                  reverse=False):
        '''
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
        is the value returned by self.set_pulser_state(rf_width).

        Given the way our pulser is configured, N_clock_ticks_per_cycle will
        grow linearly by rf_width.

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
            RF width,
            data_post_processing_output (or raw data trace)

        The remaining (fixed) values for analysis can be obtained from the
        self.experimental_conditions function.

        The 'reverse' option runs the scan in order of high frequency to low.
        This might be useful for debugging. There was some suspicion that the DAQ configuration
        contained a delay that caused errors in the data acquisition. Running in
        reverse would allow one to see the effects.

        '''

        self.N_cycles = int(N_cycles)

        self.rfsynth.stop_sweep()
        self.rfsynth.trigger_mode('disabled')
        self.rfsynth.set_power(self.rfsynth_channel, self.rf_power)
        self.rfsynth.set_frequency(self.rfsynth_channel, self.rf_frequency)

        if self.t1_measurement is False:
            self.rfsynth.rf_on(self.rfsynth_channel)
        else:
            self.rfsynth.rf_off(self.rfsynth_channel)
        time.sleep(1.0) #wait for RF box


        data = []
        rf_width_list = np.arange(self.rf_width_low, self.rf_width_high + self.rf_width_step, self.rf_width_step)
        if reverse:
            rf_width_list = list(reversed(rf_width_list))

        for rf_width in rf_width_list:
            try:
                self.current_rf_width = np.round(rf_width, 9)
                logger.info(f'RF Width: {self.current_rf_width} seconds')

                self.N_clock_ticks_per_cycle = self.set_pulser_state(self.current_rf_width)

                self.pulser.system.state(1) #start the pulser

                # compute the total number of samples to be acquired and the DAQ time
                # these will be the same for each RF frequency through the scan
                self.N_clock_ticks_per_frequency = int(self.N_clock_ticks_per_cycle * self.N_cycles)
                self.daq_time = self.N_clock_ticks_per_frequency * self.clock_period
                logger.debug(f'Acquiring {self.N_clock_ticks_per_frequency} total samples')
                logger.debug(f'  sample period of {self.clock_period} seconds')
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

                self._stop_and_close_daq_tasks()

                if post_process_function:
                    data_buffer = post_process_function(data_buffer, self)

                #should we make this a dictionary with self.current_rf_width as the key?
                data.append([self.current_rf_width, data_buffer])

            except nidaqmx.errors.Error as e:
                logger.warning(e)
                logger.warning(f'Skipping {self.current_rf_width}')
        #self.rfsynth.rf_off(self.rfsynth_channel)

        return data
