import logging
import numpy as np
import time
import qt3utils.analysis.aggregation

logger = logging.getLogger(__name__)


def aggregate_data(data_buffer, cwodmr):
    '''
    Calls qt3utils.analysis.aggregation.reshape_sum_trace, where
        cwodmr.N_cycles = N_rows
        cwodmr.N_clock_ticks_per_cycle = N_samples_per_row

    '''
    return qt3utils.analysis.aggregation.reshape_sum_trace(data_buffer,
                                                           cwodmr.N_cycles,
                                                           cwodmr.N_clock_ticks_per_cycle)

class CWODMR:

    def __init__(self, pulser, rfsynth, edge_counter_config,
                       rf_pulser_channel = 'B',
                       photon_counter_nidaq_terminal = 'PFI12',
                       clock_pulser_channel = 'C',
                       clock_nidaq_terminal = 'PFI0',
                       trigger_pulser_channel = 'D',
                       trigger_nidaq_terminal = 'PFI1',
                       freq_low = 2820e6,
                       freq_high = 2920e6,
                       freq_step = 1e6,
                       rf_power = -20,
                       rf_width = 5e-6,
                       rfsynth_channel = 0):
        '''
        The input parameters to this object specify the conditions
        of an experiment and the hardware system setup.

        Hardware Settings
            pulser - a qcsapphire.Pulser object (future: support for PulseBlaster)
            rfsynth - a qt3rfsynthcontrol.Pulser object
            edge_counter_config - a qt3utils.nidaq.config.EdgeCounter object

            External Pulser Connections
            * rf_pulser_channel output controls a RF switch
            * clock_pulser_channel output provides a clock input to the NI DAQ card
            * trigger_pulser_channel output provides a rising edge trigger for the NI DAQ card

            NI DAQ Connections
            * photon_counter_nidaq_terminal - terminal connected to TTL pulses that indicate a photon
            * clock_nidaq_terminal - terminal connected to the clock_pulser_channel
            * trigger_nidaq_terminal - terminal connected to the trigger_pulser_channel

        Experimental parameters

            The frequency parameters define the range and step size of the scan.
                The scan is inclusive of freq_low and freq_high.
            The rf_power specifices the power of the MW source in units of dB mWatt.

        Ancillary parameters

            The rf_width specifies the amount of time the RF / MW signal is on
            during each data acquisition cycle. A cycle is one full sequence
            of the pulse train used in the experiment. For CWODMR, a cycle is
            RF on for rf_width time and RF off for rf_width time.

            The rfsynth_channel specifies which output channel from the Windfreak
            RF SynthHD is used to provde the RF signal (either 0 or 1)

        Additionally, it is assumed that a 532 nm laser is continuously on. If you have
        an AOM in your setup, you'll need to hold that on using an external power supply.

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
        self.rf_width = rf_width
        self.pulser = pulser
        #assert (type(self.pulser) = qcsapphire.Pulser) or (type(self.pulser) = pulseblaster.Pulser)
        self.rfsynth = rfsynth
        self.rfsynth_channel = rfsynth_channel
        #assert(type(self.rfsynth) = qt3rfsynthcontrol.QT3SynthHD)
        self.rf_pulser_channel = rf_pulser_channel
        self.clock_pulser_channel = clock_pulser_channel
        self.trigger_pulser_channel = trigger_pulser_channel

        self.photon_counter_nidaq_terminal = photon_counter_nidaq_terminal
        self.clock_nidaq_terminal = clock_nidaq_terminal
        self.trigger_nidaq_terminal  = trigger_nidaq_terminal

        self.clock_period = 200e-9
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
            'rf_width':self.rf_width,
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
        Sets the pulser to generate a signals on all channels -- RF channel,
        clock channel and trigger channel.

        Allows the user to set a different rf_width after object instantiation.

        This method is used during the data aquisition phase (see self.run()),
        but it "public" to allow the user to setup the pulser and observe
        the output signals before starting acquisition.

        Note that the pulser will be in the OFF state after calling this function.
        Call pulser.system.state(1) for the QCSapphire to start the pulser.

        A cycle is one full sequence of the pulse train used in the experiment.
        For CWODMR, a cycle is {RF on for rf_width time, RF off for rf_width time}.

        returns
            int: N_clock_ticks_per_cycle

        '''
        rf_width = np.round(rf_width, 9)

        assert np.isclose(self.rf_width % self.clock_period, 0)
        assert rf_width >= self.clock_period

        self.rf_width = rf_width

        clock_width = self.clock_period / 2
        #TODO -- check pulser output. I don't totally trust this logic
        #If I have set rf pulse with to 1 mu s  with a clock period of 200 ns and channel duty cycle mode, with 5 on, 5 off
        #I expect that for each of the first 5 200 ns system pulses, a new 1 mu s pulse will be emitted
        #thus, a total of 2 mu s of high, followed by (5 x 200 ns) 1 mu s low
        #but maybe the duty cycle forces the output low at the start of the 6th 200 ns period.
        rf_dc_on = rf_width / self.clock_period
        N_clock_ticks_per_cycle = 2*rf_dc_on
        rf_dc_off = rf_dc_on
        self.reset_pulser()

        self._setup_qcsapphire_pulser(self.clock_period,
                                        self.rf_pulser_channel,
                                        self.rf_width,
                                        rf_dc_on,
                                        rf_dc_off,
                                        self.clock_pulser_channel,
                                        clock_width,
                                        self.trigger_pulser_channel,
                                        trigger_width = self.clock_period)

        return int(N_clock_ticks_per_cycle)


    def _setup_qcsapphire_pulser(self, period,
                                        rf_pulser_channel,
                                        rf_width,
                                        rf_dc_on = 5,
                                        rf_dc_off = 5,
                                        clock_pulser_channel = 'C',
                                        clock_width = 100e-9,
                                        trigger_pulser_channel = 'D',
                                        trigger_width = 200e-9
                                        ):
        self.pulser.system.period(period)
        self.pulser.system.mode('normal')

        # force inputs not to exceed resolution of pulser
        # should this be done inside the qcsapphire object?
        rf_width = np.round(rf_width, 9)
        clock_width = np.round(clock_width, 9)

        ch_rf = self.pulser.channel(rf_pulser_channel)
        ch_rf.cmode('dcycle')
        ch_rf.width(rf_width)
        ch_rf.output.amplitude(5.0)
        ch_rf.pcounter(rf_dc_on)
        ch_rf.ocounter(rf_dc_off)
        ch_rf.sync('T0')
        self.pulser.multiplex([rf_pulser_channel], rf_pulser_channel)
        ch_rf.state(1)

        ch_clock = self.pulser.channel(clock_pulser_channel)
        ch_clock.cmode('normal')
        ch_clock.width(clock_width)
        ch_clock.sync('T0')
        self.pulser.multiplex([clock_pulser_channel], clock_pulser_channel)
        ch_clock.state(1)

        ch_trig = self.pulser.channel(trigger_pulser_channel)
        ch_trig.width(trigger_width)
        ch_trig.cmode('dcycle')
        ch_trig.pcounter(1)
        ch_trig.ocounter(rf_dc_on + rf_dc_off - 1)
        ch_trig.wcounter(0)
        ch_trig.delay(0)
        ch_trig.sync('T0')
        self.pulser.multiplex([trigger_pulser_channel], trigger_pulser_channel)
        ch_trig.state(1)

    def run(self, N_cycles = 500000,
                  post_process_function = aggregate_data):
        '''
        Performs the CWODMR scan over the specificed range of frequencies.

        For each frequency, some number of cycles of data are acquired. A cycle
        is one full sequence of the pulse train used in the experiment. For CWODMR,
        a cycle is {RF on for rf_width time, RF off for rf_width time}.

        The N_cycles specifies the total number of these cycles to
        acquire at each frequency. The choice depends on the desired resolution or signal-to-noise
        ratio, the post-data acquisition processing function, and the amount of memory
        available on the computer.

        For each frequency, the number of data points read from the NI DAQ will be
        N_clock_ticks_per_cycle * N_cycles, where N_clock_ticks_per_cycle
        is the value returned by self.set_pulser_state(self.rf_width).

        These data are found in a data_buffer within this method. They
        may be analyzed with a function passed to post_process_function,
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

        self.edge_counter_config.reset_daq()
        self.N_cycles = int(N_cycles)

        self.rfsynth.stop_sweep()
        self.rfsynth.trigger_mode('disabled')
        self.rfsynth.rf_on(self.rfsynth_channel)
        time.sleep(0.05) #wait for RF box to fully turn on

        self.N_clock_ticks_per_cycle = self.set_pulser_state(self.rf_width)
        self.pulser.system.state(1) #start the pulser

        # compute the total number of samples to be acquired and the DAQ time
        # these will be the same for each RF frequency through the scan
        self.N_clock_ticks_per_frequency = int(self.N_clock_ticks_per_cycle * self.N_cycles)
        self.daq_time = self.N_clock_ticks_per_frequency * self.clock_period

        self.edge_counter_config.configure_counter_period_measure(
            source_terminal = self.photon_counter_nidaq_terminal,
            N_samples_to_acquire_or_buffer_size = self.N_clock_ticks_per_frequency,
            clock_terminal = self.clock_nidaq_terminal,
            trigger_terminal = self.trigger_nidaq_terminal)

        self.edge_counter_config.create_counter_reader()

        data = []

        for rf_freq in np.arange(self.freq_low, self.freq_high + self.freq_step, self.freq_step):

            self.current_rf_freq = np.round(rf_freq, 9)
            self.rfsynth.set_power(self.rfsynth_channel, self.rf_power)
            self.rfsynth.set_frequency(self.rfsynth_channel, self.current_rf_freq)

            logger.info(f'RF frequency: {self.current_rf_freq} Hz')
            logger.debug(f'Acquiring {self.N_clock_ticks_per_frequency} samples')
            logger.debug(f'   Sample period of {self.clock_period} seconds')
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

        try:
            self.edge_counter_config.counter_task.close()
        except: #add catch for NIDAQError and log message
            pass

        self.rfsynth.rf_off(self.rfsynth_channel)

        return data
