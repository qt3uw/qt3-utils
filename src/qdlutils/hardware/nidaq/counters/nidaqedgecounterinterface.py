import nidaqmx
import nidaqmx._lib
import nidaqmx.stream_readers
import ctypes

class NidaqEdgeCounterInterface:
    '''
    This class implements the lowest-level configuration of the DAQ for edge counting of
    TTL signals at the counter input of an NIDAQ board (e.g. for SPCM output).

    This implemention is primarily based off of the `qt3utils` implemention which can
    be found at
        https://github.com/qt3uw/qt3-utils/blob/main/src/qt3utils/nidaq/config.py
    As a fork of `qt3utils`, this information is also retained in our early commit
    history and can be found at the same location.

    This class acts as a simplifed interface for the NIDAQ edge counter and contains
    methods for initializing and configuring the clock and DAQ to queue a measurement.

    Attributes
    ----------
    device_name : Str
        The name of the DAQ board which is being used for the edge counter
    clock_task : nidaqmx.Task
        The NIDAQ task for the internal clock
    clock_task_config : Dict
        A dictionary of the clock task configuration.
    counter_task : nidaqmx.Task
        The NIDAQ task for the edge counter.
    counter_task_config : Dict
        A dictionary of the counter task configuration.
    counter_reader : nidaqmx.stream_readers.CounterReader
        This is an `nidaqmx.stream_reader` for reading in the counter.


    Methods
    -------
    reset_daq() -> None
        Resets the current DAQ device.

    configure_di_clock(**kargs) -> None
        Configures an internal clock task for timing the edge counter events.

    configure_counter_period_measure(**kargs) -> None
        Configures the counter task for reading data from the coutner.

    create_counter_reader() -> None
        Creates an `nidaqmx.stream_readers.CounterReader` to read the counts.


    Notes
    -----
    To use this class perform the following steps to read out data from the counter.
    In general, it is desirable to wrap this process in another class which has easier
    to use attributes and configuration (see `NidaqBatchedRateCounter`).

        ```
        # Instantiate the edge counter interface
        edge_counter = NidaqEdgeCounterInterface()

        # Creates a clock task on an internal channel then configures the
        # clock to cycle at `clock_rate`
        edge_counter.configure_di_clock(clock_rate = clock_rate)

        # Creates a counter task on the specified channel and configures
        # it to count the number of rising edges from the SPCM TTL signal
        # between each clock cycle
        edge_counter.configure_counter_period_measure(
            clock_terminal = edge_counter.clock_task_config['clock_terminal']
        )

        # Creates the counter reader which actually reads the counts
        edge_counter.create_counter_reader()

        # Start the clock task
        edge_counter.clock_task.start()

        # Flag the counter task to wait until it finishes
        edge_counter.counter_task.wait_until_done()
        
        # Start the counter task
        edge_counter.counter_task.start()

        # Create a buffer to store the count data between each clock cycle
        # the length corresponds to how many cycles are recorded.
        data_buffer = np.array(N_samples)

        # This starts reading from the counter, storing data in the 
        # `data_buffer` and returning `samples_read` which is the number of
        # samples read (i.e. number of clock cycles).
        # On rare occasion this can differ from `N_samples`.
        samples_read = edge_config.counter_reader.read_many_sample_double(
                            data_buffer,
                            number_of_samples_per_channel=N_samples,
                            timeout=5)

        # Stop the counter and clock tasks
        edge_counter.counter_task.stop()
        edge_counter.clock_task.stop()
        ```

    '''

    def __init__(self, device_name: str='Dev1') -> None:

        self.device_name = device_name      # DAQ device name
        self.clock_task = None              # An NIDAQ task used for timing the readout
        self.clock_task_config = None
        self.counter_task = None            # An NIDAQ task used for 
        self.counter_task_config = None
        self.counter_reader = None          # An NIDAQ reader for the counter

    def reset_daq(self):
        '''
        Resets the DAQ associated to this counter.
        '''
        nidaqmx.system.Device(self.device_name).reset_device()

    def configure_di_clock(self, 
                           internal_clock_di_line='port0',
                           clock_rate=1e6,
                           sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS) -> None:

        '''
        This method creates and configures a clock task using a dummy channel. 
        
        A clock task using an internal clock source appears to be needed for edge 
        counting tasks (documentation is unclear) if you do not supply your own 
        exernal clock.

        This configuration follows a recipe found on the nspyre documentation site.
        https://nspyre.readthedocs.io/en/latest/guides/ni-daqmx.html

        This method generates the class attributes `clock_task` and `clock_task_config`
        and stores them in the `NidaqEdgeCounterInterface`. The `clock_task_confic`
        is a `dict` which contains the information used to configure the clock from which
        the `clock_task_config['clock_terminal']` is to be used as an input clock 
        terminal for the edge counting task. See `self.configure_counter_period_measure()`
        for more information.

        Parameters
        ----------
        internal_clock_di_line : str
            The name of the digital input channel line for the clock signal. By default
            set to `'port0'` and should generlly not be changed.
        clock_rate : int
            The clock rate of the internal clock in Hertz. By default it is set to 1 MHz.
            You can adjust the clock rate if higher precision is needed in the timing of
            samples (note that the length of a given sample will be truncated to some 
            integer number of clock cycles).
        sample_mode : int
            An integer which defines the aquisition type. By default it is chosen to be
            `nidaqmx.constants.AcquisitionType.CONTINUOUS` which has value 10123. See
            https://nidaqmx-python.readthedocs.io/en/stable/constants.html#nidaqmx.constants.AcquisitionType
            for alternatives. In general you will not need to set this value.

        Returns
        -------
            (indirect) self.clock_task : nidaqmx.Task
                A `nidaqmx` task for the clock.
            (indirect) self.clock_task_config : Dict
                A dictionary containing the configuration information for the clock task.
        '''
        # Cast the clock rate as an integer 
        clock_rate = int(clock_rate)
        # Create the clock task
        self.clock_task = nidaqmx.Task()
        # Get the digital input channel for the clock task
        di_channel = self.clock_task.di_channels.add_di_chan(f'{self.device_name}/{internal_clock_di_line}')
        # Configure the clock rate and timing
        self.clock_task.timing.cfg_samp_clk_timing(clock_rate, sample_mode = sample_mode)
        # Generate the configuration dictionary and save to instance
        self.clock_task_config = {
            'di_channel_name':internal_clock_di_line,
            'clock_rate':clock_rate,
            'clock_terminal':'di/SampleClock',
            'sample_mode':sample_mode,
            'di_channel':di_channel
        }

    def configure_counter_period_measure(self, 
                                         daq_counter = 'ctr2',
                                         source_terminal = 'PFI12',
                                         N_samples_to_acquire_or_buffer_size = 1e6,
                                         clock_terminal = 'PFI0',
                                         sampling_mode = nidaqmx.constants.AcquisitionType.FINITE,
                                         trigger_terminal = None) -> None:

        '''
        This method creates and configures a counter task to measure the counts
        on the `source_terminal` between each clock cycle rising edge on the
        `clock_terminal`.

        The TTL signal of interest for counting (e.g. from the SPCM) should be connected
        to the `source_terminal` input channel. While an external clock or the internal
        clock configured by `self.configure_di_cock()` should connect to the
        `clock_terminal` input channel (in the latter case you must provide the digital
        clock terminal from the `self.clock_task_config` dictionary).


        Parameters
        ----------
        daq_counter : Str
            Name of the NIDAQ card counter to be used. Must not be in use by another task
        source_terminal: Str
            The source terminal of the SPCM or TTL signal to be counted.
        N_samples_to_acquire_or_buffer_size : int
            The number of samples (clock cycles) to acquire counts for. Must be equal to 
            the size of the buffer.
        clock_terminal : Str
            The terminal for the external/internal clock used to time the meaurements.
        sampling_mode : Int
            The acquisition type of the counter task, by default it is chosen to be
            `nidaqmx.constants.AcquisitionType.FINITE` which has value 10178. See
            https://nidaqmx-python.readthedocs.io/en/stable/constants.html#nidaqmx.constants.AcquisitionType
            for more information.
        trigger_terminal : Str
            By default `None`. If provided the task will begin on the rising edge of
            a TTL pulse ariving at this terminal. If it is not provided then the task
            will begin once the `task.start()` function is called.

        Returns
        -------
            (indirect) self.counter_task : nidaqmx.Task
                A `nidaqmx` task for counting.
            (indirect) self.counter_task_config : Dict
                A dictionary containing the configuration information for the counter task.

        Notes
        -----
        This configuration follow's the qudi configuration for edge counting.

        In this setup, a counter task is configured to measure the period of the signal
        that is attached to its gate terminal. In the code below, you will see that 
        signal from the `clock_terminal` is routed to be the input signal to the 
        counter's gate terminal, while the signal on the `source_terminal` is routed to
        bethe counter's source terminal and configured to measure the period of the 
        input signal.

        This is a reversal of the description of the nidaqmx.add_ci_period_chan function.
        The original intention was to use a known clock signal connected to the counter's
        source terminal to count the number of ticks observed (edge counting) between two
        rising edges of unknown input signal, which was to be connected to the counter's 
        gate terminal. This is useful to count the amount of time between two input 
        event signals.

        In this configuration we reverse the roles: the unknown signal from the SPCM is 
        connected to the source terminal and the clock signal is connected to the gate 
        terminal. As a result, the NI-DAQ card will return the number of edges 
        encountered during one period of the clock signal, thus providing a measure of 
        the count rate for each clock cycle. This is more convenient than the standard 
        monotonically increasing value from a standard edge counter, which requires 
        post-processing to recover the count rate, and is ultimately limited by the max
        value of `2**32` counts.

        '''

        # Get the names for the different channels
        counter_name = f'/{self.device_name}/{daq_counter}'
        terminal_name = f'/{self.device_name}/{source_terminal}'
        clock_channel_name = f'/{self.device_name}/{clock_terminal}'
        # Cast the number of samples to an integer
        N_samples_to_acquire_or_buffer_size = int(N_samples_to_acquire_or_buffer_size)
        # Launch the counter task
        self.counter_task = nidaqmx.Task()
        # Create a counter input channel on the desired channel
        ci_channel = self.counter_task.ci_channels.add_ci_period_chan(
                            counter_name,
                            min_val=0,
                            max_val=100000000,
                            units=nidaqmx.constants.TimeUnits.TICKS,
                            edge=nidaqmx.constants.Edge.RISING)
        # Get the driver
        # This works around a known bug with the nidaqmx python wrapper
        try:
            driver = nidaqmx._lib.lib_importer.windll
        except:
            driver = nidaqmx._lib.lib_importer.cdll
        # Set the terminals of the counter task
        driver.DAQmxSetCIPeriodTerm(
            self.counter_task._handle,
            ctypes.c_char_p(counter_name.encode('ascii')),
            ctypes.c_char_p(clock_channel_name.encode('ascii')))
        driver.DAQmxSetCICtrTimebaseSrc(
            self.counter_task._handle,
            ctypes.c_char_p(counter_name.encode('ascii')),
            ctypes.c_char_p(terminal_name.encode('ascii')))
        # Set the number of samples to aqcuire and the sampling mode
        self.counter_task.timing.cfg_implicit_timing(sample_mode=sampling_mode,
                                                     samps_per_chan=N_samples_to_acquire_or_buffer_size)
        # If a trigger terminal is provided set up the trigger
        if trigger_terminal is not None:
                self.counter_task.triggers.arm_start_trigger.trig_type =  nidaqmx.constants.TriggerType.DIGITAL_EDGE
                self.counter_task.triggers.arm_start_trigger.dig_edge_edge =  nidaqmx.constants.Edge.RISING
                self.counter_task.triggers.arm_start_trigger.dig_edge_src = f'/{self.device_name}/{trigger_terminal}'
        # Get the counter task configuration
        self.counter_task_config = {
            'clock_terminal':clock_terminal,
            'daq_counter': daq_counter,
            'source_terminal':source_terminal,
            'N_samples_to_acquire_or_buffer_size':N_samples_to_acquire_or_buffer_size,
            'ci_channel':ci_channel,
            'trigger_terminal':trigger_terminal
        }

    def create_counter_reader(self):
        '''
        Creates an `nidaqmx.stream_readers.CounterReader` to access the counter
        '''
        self.counter_reader = nidaqmx.stream_readers.CounterReader(self.counter_task.in_stream)
