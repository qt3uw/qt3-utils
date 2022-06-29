
import nidaqmx
import nidaqmx._lib  # Due to NIDAQmx C-API bug needed to bypass property getter (according to qudi)
import nidaqmx.stream_readers
import ctypes

'''

https://www.ni.com/docs/en-US/bundle/pcie-pxie-usb-63xx-features/resource/370784k.pdf

'''

def reset_daq(device_name):
    nidaqmx.system.Device(device_name).reset_device()

class EdgeCounter:
    '''
    Class to encapsulate and retain references to clock and digital edge counters
    needed for reading the SPCM.

    https://www.ni.com/docs/en-US/bundle/pcie-pxie-usb-63xx-features/resource/370784k.pdf
    '''

    def __init__(self,  device_name = 'Dev1'):

        self.device_name = device_name
        self.clock_task = None
        self.counter_task = None
        self.counter_reader = None

    # Q -- create __enter__ and __exit__ context functions to ensure proper cleanup?
    ## Create separate objects for Dummy Clock task creator and Counter task creator
    ## in Usage, do a nested loop
    #
    # with DummyClockTask() as clock_task:
    #     clock_terminal = clock_task.clock_terminal
    #     with EdgeConterTask(clock_terminal) as counter task:
    #
    #         # perform setup of pulser
    #         clock_task.start()
    #         counter_task.start()
    #
    #
    # DummyClockTask and EdgeCounterTask could inherit nidaqmx.Task?

    # def __del__(self):
    #     #cleanup
    #     if self.clock_task:
    #         try:
    #             self.clock_task.stop()
    #         except:
    #             pass
    #
    #         try:
    #             self.clock_task.close()
    #         except:
    #             pass
    #
    #     if self.counter_task:
    #         try:
    #             self.counter_task.stop()
    #         except:
    #             pass
    #
    #         try:
    #             self.counter_task.close()
    #         except:
    #             pass

    def reset_daq(self):
        reset_daq(self.device_name)

    def configure_di_clock(self, internal_clock_di_line = 'port0',
                                 clock_rate = 1e6,
                                 sample_mode = nidaqmx.constants.AcquisitionType.CONTINUOUS):

        '''
        Creates and configures a clock task using a dummy channel. A clock task
        using an internal clock surce is needed
        for edge counting tasks (maybe -- documentation is confusing) if you do not
        supply your own exernal clock.

        This configuration follows a recipe found on the nspyre documentation site.
        https://nspyre.readthedocs.io/en/latest/guides/ni-daqmx.html

        After calling this method, an EdgeCounter object contains a dictionary
        `clock_task_config` which
        contains the information used to configure the clock. You should
        use the EdgeCounter.clock_task_config['clock_terminal'] as the
        input clock terminal for your edge counting task.

        You also need to start the clock task explicitly before you start the edge counter task.

           ```
           nidaq_edge = EdgeCounter()
           nidaq_edge.configure_di_clock()
           nidaq_edge.configure_counter_period_measure(
             clock_terminal = nidaq_edge.clock_task_config['clock_terminal']
           )
           nidaq_edge.create_counter_reader()

           nidaq_edge.clock_task.start()

           nidaq_edge.counter_task.start()

           time.sleep( wait_to_acquire_all_samples )

           data_buffer = np.array(N_samples)

           read_samples = edge_config.counter_reader.read_many_sample_double(
                                data_buffer,
                                number_of_samples_per_channel=N_samples,
                                timeout=5)

           nidaq_edge.counter_task.stop()
           nidaq_edge.clock_task.stop()

        '''

        clock_rate = int(clock_rate)
        self.clock_task = nidaqmx.Task()
        di_channel = self.clock_task.di_channels.add_di_chan(f'{self.device_name}/{internal_clock_di_line}')
        self.clock_task.timing.cfg_samp_clk_timing(clock_rate, sample_mode = sample_mode)

        self.clock_task_config = {
            'di_channel_name':internal_clock_di_line,
            'clock_rate':clock_rate,
            'clock_terminal':'di/SampleClock',
            'sample_mode':sample_mode,
            'di_channel':di_channel
        }

    def configure_counter_period_measure(self, daq_counter = 'ctr2',
                                               source_terminal = 'PFI12',
                                               N_samples_to_acquire_or_buffer_size = 1e6,
                                               clock_terminal = 'PFI0',
                                               sampling_mode = nidaqmx.constants.AcquisitionType.FINITE,
                                               trigger_terminal = None):

        '''
        Configures an edge counter task to measure the count rate on the
        `source_terimanl` per clock sample found on the `clock_terminal`.

        Connect the SPCM output to the `source_terminal` input channel.
        Connect a clock to the `clock_terminal` input channel, or use
        the configure_di_clock to configure an internal clock and provide
        the clock terminal name.

        You can choose the particular NI card counter using the `daq_counter` parameter,
        though it doesn't matter which counter you choose as long as its not being
        used by another task.

        If supplied, the task will begin counting on the rising edge of a digital
        TTL pulse supplied at the `trigger_terminal`. Without a trigger terminal,
        the task will begin to acquire data as soon as the task.start() function is called.

        This configuration follow's the qudi configuration for edge counting.

        Details:
        In this setup, a counter task is configured to measure the period of the signal that is attached
        to its gate terminal. In the code below, you will see that signal from the `clock_terminal`
        is routed to be the input signal to the counter's gate terminal, while the signal on the `source_terminal`
        is routed to be the counter's source terminal and configured to measure the period of the input signal.

        This is a reversal of the description of the nidaqmx.add_ci_period_chan function.
        The original intention was to use a known clock signal connected to the counter's source terminal
        to count the number of ticks observed (edge counting) between two rising edges of unknown input signal,
        which was to be connected to the counter's gate terminal.

        In this configuration we reverse the roles: the unknown signal from the SPCM is connected
        to the source terminal and the clock signal is connected to the gate terminal.

        Reversing this configuration turns out to be a useful trick because the NI-DAQ card will return the number of
        edges encountered during one period of the clock signal, thus providing a measure of the
        count rate for each clock cycle. This is more convenient than the standard monotonically
        increasing value from a standard edge counter, which requires post-processing to recover the
        count rate per data point, and is ultimately limited by the max value of 2**32 counts.

        '''

        counter_name = f'/{self.device_name}/{daq_counter}'
        terminal_name = f'/{self.device_name}/{source_terminal}'
        clock_channel_name = f'/{self.device_name}/{clock_terminal}'

        N_samples_to_acquire_or_buffer_size = int(N_samples_to_acquire_or_buffer_size)

        self.counter_task = nidaqmx.Task()

        ci_channel = self.counter_task.ci_channels.add_ci_period_chan(
                            counter_name,
                            min_val=0,
                            max_val=100000000,
                            units=nidaqmx.constants.TimeUnits.TICKS,
                            edge=nidaqmx.constants.Edge.RISING)

        #this works around a known bug with the nidaqmx python wrapper
        try:
            driver = nidaqmx._lib.lib_importer.windll
        except:
            driver = nidaqmx._lib.lib_importer.cdll

        driver.DAQmxSetCIPeriodTerm(
            self.counter_task._handle,
            ctypes.c_char_p(counter_name.encode('ascii')),
            ctypes.c_char_p(clock_channel_name.encode('ascii')))

        driver.DAQmxSetCICtrTimebaseSrc(
            self.counter_task._handle,
            ctypes.c_char_p(counter_name.encode('ascii')),
            ctypes.c_char_p(terminal_name.encode('ascii')))


        self.counter_task.timing.cfg_implicit_timing(sample_mode=sampling_mode,
                                                     samps_per_chan=N_samples_to_acquire_or_buffer_size)

        if trigger_terminal:
                self.counter_task.triggers.arm_start_trigger.trig_type =  nidaqmx.constants.TriggerType.DIGITAL_EDGE
                self.counter_task.triggers.arm_start_trigger.dig_edge_edge =  nidaqmx.constants.Edge.RISING
                self.counter_task.triggers.arm_start_trigger.dig_edge_src = f'/{self.device_name}/{trigger_terminal}'

        self.counter_task_config = {
            'clock_terminal':clock_terminal,
            'daq_counter': daq_counter,
            'source_terminal':source_terminal,
            'N_samples_to_acquire_or_buffer_size':N_samples_to_acquire_or_buffer_size,
            'ci_channel':ci_channel,
            'trigger_terminal':trigger_terminal
        }

    def create_counter_reader(self):
        self.counter_reader = nidaqmx.stream_readers.CounterReader(self.counter_task.in_stream)
