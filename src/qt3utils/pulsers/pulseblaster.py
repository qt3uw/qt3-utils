import numpy as np

try:
    from pulseblaster.PBInd import PBInd
    import pulseblaster.spinapi
except NameError as e:
    #handling this error allows for development of pulse sequences without need to interact with hardware
    print(e)
    print('Pulse Blaster software has not been properly installed.')

from qt3utils.pulsers.interface import ExperimentPulser
from qt3utils.errors import PulseBlasterInitError, PulseBlasterError, PulseTrainWidthError

class PulseBlaster(ExperimentPulser):

    def start(self):
        self.open()
        ret = pulseblaster.spinapi.pb_start()
        if ret != 0:
            raise PulseBlasterError(f'{ret}: {pulseblaster.spinapi.pb_get_error()}')
        self.close()

    def stop(self):
        self.open()
        ret = pulseblaster.spinapi.pb_stop()
        if ret != 0:
            raise PulseBlasterError(f'{ret}: {pulseblaster.spinapi.pb_get_error()}')
        self.close()

    def reset(self):
        self.open()
        ret = pulseblaster.spinapi.pb_reset()
        if ret != 0:
            raise PulseBlasterError(f'{ret}: {pulseblaster.spinapi.pb_get_error()}')
        self.close()

    def close(self):
        ret = pulseblaster.spinapi.pb_close()
        if ret != 0:
            raise PulseBlasterError(f'{ret}: {pulseblaster.spinapi.pb_get_error()}')

    def stop_programming(self):
        if pulseblaster.spinapi.pb_stop_programming() != 0:
            raise PulseBlasterError(pulseblaster.spinapi.pb_get_error())

    def start_programming(self):
        if pulseblaster.spinapi.pb_start_programming(0) != 0:
            raise PulseBlasterError(pulseblaster.spinapi.pb_get_error())

    def open(self):
        pulseblaster.spinapi.pb_select_board(self.pb_board_number)
        ret = pulseblaster.spinapi.pb_init()
        if ret != 0:
            self.close() #if opening fails, attempt to close before raising error
            raise PulseBlasterInitError(f'{ret}: {pulseblaster.spinapi.pb_get_error()}')
        pulseblaster.spinapi.pb_core_clock(100*pulseblaster.spinapi.MHz)

class PulseBlasterArb(PulseBlaster):

    def __init__(self, pb_board_number = 1):

        self.pb_board_number = pb_board_number
        self.reset()

    def reset(self):
        self.clock_channels = []
        self.clock_period = None
        self.channel_settings = []
        self.full_cycle_width = 0

    def set_clock_channels(self, pulse_blaster_channels, clock_period):
        '''
        pulse_blaster_channel can be an int or a list of ints
        '''
        if type(pulse_blaster_channels) == int:
            pulse_blaster_channels = [pulse_blaster_channels]

        self.clock_channels = pulse_blaster_channels
        self.clock_period = np.round(clock_period,8)

    def add_channels(self, pulse_blaster_channels, start_time, pulse_width):
        '''
        pulse_blaster_channel can be an int or a list of ints
        start_time and pulse_width are in seconds (and will be rounded
        to the nearest 10ns)

        One side-effect of this function is that it will increase the object's
        self.full_cycle_width value if a requested channel's start_time + pulse_width
        exceeds the current full_cycle_width value.

        Otherwise, one may also set the full cycle width manually with set_full_cycle_length.
        '''
        if type(pulse_blaster_channels) == int:
            pulse_blaster_channels = [pulse_blaster_channels]

        for pulse_blaster_channel in pulse_blaster_channels:
            self.channel_settings.append({
                'channel':pulse_blaster_channel,
                'start':np.round(start_time, 8),
                'width':np.round(pulse_width, 8)
                })
            if np.round(start_time, 8) + np.round(pulse_width, 8) > self.full_cycle_width:
                self.full_cycle_width = np.round(start_time, 8) + np.round(pulse_width, 8)

    def set_full_cycle_length(self, cycle_width):
        '''
        cycle_width is in units of seconds and will be rounded to the nearest 10ns.

        Be sure to set this to a value greater than or equal to the time you need
        for your individual channels.
        '''
        self.full_cycle_width = np.round(cycle_width, 8)

    def program_pulser_state(self, *args, **kwargs):
        '''
        Programs the pulser based on the state of the object, as instructed
        by calls to set_clock_channels, set_channels and set_full_cycle_length

        If a clock channel has been specified, will return full_cycle_length / clock_period,
        which is the number of clock "ticks" for each full pulse sequence cycle.
        This useful for a data acquisition device that utilizes the clock signal.

        If no clock channel has been specified, will return 0. 

        '''
        hardware_pins = self.clock_channels + [s['channel'] for s in self.channel_settings]

        self.open()
        pb = PBInd(pins = hardware_pins, on_time = int(self.full_cycle_width*1e9))
        self.start_programming()

        for clock_channel in self.clock_channels:
            pb.make_clock(clock_channel, int(self.clock_period*1e9))

        for a_chan_setting in self.channel_settings:
            pb.on(a_chan_setting['channel'], int(a_chan_setting['start']*1e9), int(a_chan_setting['width']*1e9))

        pb.program([],float('inf'))
        self.stop_programming()
        self.close()

        if self.clock_period:
            return np.round(self.full_cycle_width / self.clock_period).astype(int)
        else:
            return 0

    def experimental_conditions(self):
        '''
        Returns a dictionary of paramters that are pertinent for the relevant experiment
        '''
        return {
            'full_cycle_width':self.full_cycle_width,
            'clock_channels':self.clock_channels,
            'clock_period':self.clock_period,
            'channel_settings':self.channel_settings
        }

class PulseBlasterHoldAOM(PulseBlasterArb):
    '''
    Holds the AOM channel open indefinitely by programming it
    to output a constant positive voltage.
    Useful for confocal scanning.
    '''
    def __init__(self, pb_board_number = 1,
                       aom_channel = 0,
                       cycle_width = 10e-3):
        """
        pb_board_number - the board number (0, 1, ...)
        aom_channel output controls the AOM by holding a positive voltage
        cycle_width - the length of the programmed pulse. Since aom channel is held on, this value is arbitrary
        """
        super().__init__(pb_board_number)
        self.add_channels(aom_channel, 0, cycle_width)

class PulseBlasterCWODMR(PulseBlaster):
    '''
    Programs the pulse sequences needed for CWODMR.

    Provides an
      * always ON channel for an AOM.
      * 50% duty cycle pulse for RF switch
      * clock signal for use with a data acquisition card
      * trigger signal for use with a data acquisition card
    '''
    def __init__(self, pb_board_number = 1,
                       aom_channel = 0,
                       rf_channel = 1,
                       clock_channel = 2,
                       trigger_channel = 3,
                       rf_pulse_duration = 5e-6,
                       clock_period = 200e-9,
                       trigger_width = 500e-9):
        """
        pb_board_number - the board number (0, 1, ...)
        aom_channel output controls the AOM by holding a positive voltage
        rf_channel output controls a RF switch
        clock_channel output provides a clock input to the NI DAQ card
        trigger_channel output provides a rising edge trigger for the NI DAQ card
        """
        self.pb_board_number = pb_board_number
        self.aom_channel = aom_channel
        self.rf_channel = rf_channel
        self.clock_channel = clock_channel
        self.trigger_channel = trigger_channel
        self.rf_pulse_duration = np.round(rf_pulse_duration, 8)
        self.clock_period = np.round(clock_period, 8)
        self.trigger_width = np.round(trigger_width, 8)


    def program_pulser_state(self, rf_pulse_duration = None, *args, **kwargs):
        '''
        rf_pulse_duration is in seconds
        '''
        if rf_pulse_duration:
            self.raise_for_pulse_width(rf_pulse_duration)
            self.rf_pulse_duration = np.round(rf_pulse_duration,8)
        else:
            self.raise_for_pulse_width(self.rf_pulse_duration)

        cycle_length = 2*self.rf_pulse_duration

        hardware_pins = [self.aom_channel, self.rf_channel,
                         self.clock_channel, self.trigger_channel]

        self.open()
        pb = PBInd(pins = hardware_pins, on_time = int(cycle_length*1e9))
        self.start_programming()

        pb.on(self.trigger_channel, 0, int(self.trigger_width*1e9))
        pb.make_clock(self.clock_channel, int(self.clock_period*1e9))
        pb.on(self.aom_channel, 0, int(cycle_length*1e9))
        pb.on(self.rf_channel, 0, int(self.rf_pulse_duration*1e9))

        pb.program([],float('inf'))
        self.stop_programming()

        self.close()
        return np.round(cycle_length / self.clock_period).astype(int)


    def experimental_conditions(self):
        '''
        Returns a dictionary of paramters that are pertinent for the relevant experiment
        '''
        return {
            'rf_pulse_duration':self.rf_pulse_duration,
            'clock_period':self.clock_period
        }

    def raise_for_pulse_width(self, rf_pulse_duration, *args, **kwargs):
        if rf_pulse_duration < 50e-9:
            raise PulseTrainWidthError(f'RF width too small {int(rf_pulse_duration)} < 50 ns')

class PulseBlasterPulsedODMR(PulseBlaster):
    '''
    Programs the pulse sequences needed for pulsed ODMR.

    AOM on / RF off , AOM off / RF on , AOM on / RF off , AOM off / RF off

    Provides
      * AOM channel with user-specified width
      * RF channel with user-specified width
      * RF pulse left, center, or right justified pulse
      * padding between the AOM and RF pulses
      * support for specifying AOM/RF hardware response times in order to fine-tune position of pulses
      * control of the full cycle width
      * clock signal for use with a data acquisition card
      * trigger signal for use with a data acquisition card
    '''
    def __init__(self, pb_board_number = 1,
                       aom_channel = 0,
                       rf_channel = 1,
                       clock_channel = 2,
                       trigger_channel = 3,
                       clock_period = 200e-9,
                       trigger_width = 500e-9,
                       rf_pulse_duration = 5e-6,
                       aom_width = 5e-6,
                       aom_response_time = 800e-9,
                       rf_response_time = 200e-9,
                       pre_rf_pad = 100e-9,
                       post_rf_pad = 100e-9,
                       full_cycle_width = 30e-6,
                       rf_pulse_justify = 'center'):
        """
        pb_board_number - the board number (0, 1, ...)
        rf_channel output controls a RF switch
        clock_channel output provides a clock input to the NI DAQ card
        trigger_channel output provides a rising edge trigger for the NI DAQ card
        """
        self.pb_board_number = pb_board_number
        self.aom_channel = aom_channel
        self.rf_channel = rf_channel
        self.clock_channel = clock_channel
        self.trigger_channel = trigger_channel

        self.aom_width = np.round(aom_width, 8)
        self.rf_pulse_duration = np.round(rf_pulse_duration, 8)
        self.aom_response_time = np.round(aom_response_time, 8)
        self.rf_response_time = np.round(rf_response_time, 8)
        self.post_rf_pad = np.round(post_rf_pad, 8)
        self.pre_rf_pad = np.round(pre_rf_pad, 8)
        self.full_cycle_width = np.round(full_cycle_width, 8)
        self.rf_pulse_justify = rf_pulse_justify

        self.clock_period = np.round(clock_period, 8)
        self.trigger_width = np.round(trigger_width, 8)

#TODO  add def compute_rf_pulse_sequence(rf_pulse_duration)

    def program_pulser_state(self, rf_pulse_duration = None, *args, **kwargs):
        '''
        rf_pulse_duration is in seconds
        '''
        if rf_pulse_duration:
            self.raise_for_pulse_width(rf_pulse_duration)
            self.rf_pulse_duration = np.round(rf_pulse_duration,8)
        else:
            self.raise_for_pulse_width(self.rf_pulse_duration)

        assert self.rf_pulse_justify in ['left', 'center', 'right', 'start_center']
        half_cycle_width = self.full_cycle_width / 2

        if self.rf_pulse_justify == 'center':
            delay_rf_channel = self.aom_width + (half_cycle_width - self.aom_width)/2 - self.rf_pulse_duration/2 - self.rf_response_time
        if self.rf_pulse_justify == 'start_center':
            delay_rf_channel = self.aom_width + (half_cycle_width - self.aom_width)/2 - self.rf_response_time
        if self.rf_pulse_justify == 'left':
            delay_rf_channel = self.aom_width + self.aom_response_time + self.pre_rf_pad - self.rf_response_time
        if self.rf_pulse_justify == 'right':
            delay_rf_channel = half_cycle_width - self.post_rf_pad - self.rf_pulse_duration - self.rf_response_time + self.aom_response_time

        hardware_pins = [self.aom_channel, self.rf_channel,
                         self.clock_channel, self.trigger_channel]
        self.open()

        pb = PBInd(pins = hardware_pins, on_time = int(self.full_cycle_width*1e9))
        self.start_programming()

        pb.on(self.trigger_channel, 0, int(self.trigger_width*1e9))
        pb.make_clock(self.clock_channel, int(self.clock_period*1e9))
        pb.on(self.aom_channel, 0, int(self.aom_width*1e9))
        pb.on(self.rf_channel, int(delay_rf_channel*1e9), int(self.rf_pulse_duration*1e9))
        pb.on(self.aom_channel, int(half_cycle_width*1e9), int(self.aom_width*1e9))
        pb.program([],float('inf'))

        self.stop_programming()
        self.close()
        return np.round(self.full_cycle_width / self.clock_period).astype(int)

    def experimental_conditions(self):
        '''
        Returns a dictionary of paramters that are pertinent for the relevant experiment
        '''
        return {
            'rf_pulse_duration':self.rf_pulse_duration,
            'aom_width':self.aom_width,
            'aom_response_time':self.aom_response_time,
            'post_rf_pad':self.post_rf_pad,
            'pre_rf_pad':self.pre_rf_pad,
            'full_cycle_width':self.full_cycle_width,
            'rf_pulse_justify':self.rf_pulse_justify,
            'clock_period':self.clock_period
        }

    def raise_for_pulse_width(self, rf_pulse_duration):
        #the following enforces that the full cycle width is large enough
        requested_total_width = self.aom_width
        requested_total_width += self.aom_response_time
        requested_total_width += self.pre_rf_pad
        requested_total_width += rf_pulse_duration
        requested_total_width += self.post_rf_pad

        if requested_total_width >= self.full_cycle_width / 2:
            raise PulseTrainWidthError(f"half cycle width, {self.full_cycle_width / 2}, is not large enough to support requested pulse sequence, {requested_total_width}.")


class PulseBlasterRamHahnDD(PulseBlaster):
    '''
    Programs the pulse sequences needed for Ramsey, Hahn Echo and Dynamical Decoupling.

    AOM on / RF off , AOM off / RF pi/2 , free precession time with N refocusing pi pulses, AOM off / RF pi/2 , AOM on / RF off , AOM off / RF off for reset.

    Provides
      * AOM channel with user-specified width
      * RF channel with user-specified width
      * RF pulse left, center, or right justified pulse
      * padding between the AOM and RF pulses
      * support for specifying AOM/RF hardware response times in order to fine-tune position of pulses
      * control of the full cycle width
      * clock signal for use with a data acquisition card
      * trigger signal for use with a data acquisition card
    '''
    def __init__(self, pb_board_number = 1,
                       aom_channel = 0,
                       rf_channel = 1,
                       clock_channel = 2,
                       trigger_channel = 3,
                       clock_period = 200e-9,
                       trigger_width = 500e-9,
                       rf_pi_pulse_width = 1e-6,
                       aom_width = 5e-6,
                       aom_response_time = 800e-9,
                       rf_response_time = 200e-9,
                       pre_rf_pad = 100e-9,
                       post_rf_pad = 100e-9,
                       free_precession_time = 5e-6,
                       n_refocussing_pi_pulses = 0):
        """
        Hardware configuration

            pb_board_number - the board number (0, 1, ...)
            rf_channel output controls a RF switch
            clock_channel output provides a clock input to the NI DAQ card
            trigger_channel output provides a rising edge trigger for the NI DAQ card

        The hardware response times should be measured accurately for your setup.
        These values will affect your measurement as the response times are built
        into the calculation of when to start TTL pulses and the actual free precession time
        experience by your system.

            aom_response_time - the delay between the TTL pulse and the actual laser signal. Should be measured for each experimental setup.
            rf_response_time - the delay between the TTL pulse and the RF signal. Should be measured for each experimental setup.

        Fixed parameters during an experiment

            rf_pi_pulse_width -- pi pulse length
            pre_rf_pad - pad time between initialization laser pulse and left-most pi/2 pulse
            post_rf_pad - pad time between right-most pi/2 pulse and readout laser pulse
            aom_width - width of the initialization and readout laser pulse

        Variable parameters during an experiment

        free_precession_time - will likely be changed via calls program_pulser_state method.
        n_refocussing_pi_pulses - will likely be changed via calls program_pulser_state method.

        """
        self.pb_board_number = pb_board_number
        self.aom_channel = aom_channel
        self.rf_channel = rf_channel
        self.clock_channel = clock_channel
        self.trigger_channel = trigger_channel

        self.aom_width = np.round(aom_width, 8)
        self.rf_pi_pulse_width = np.round(rf_pi_pulse_width, 8)
        self.aom_response_time = np.round(aom_response_time, 8)
        self.rf_response_time = np.round(rf_response_time, 8)
        self.post_rf_pad = np.round(post_rf_pad, 8)
        self.pre_rf_pad = np.round(pre_rf_pad, 8)
        self.full_cycle_width = None
        self.free_precession_time = free_precession_time
        self.n_refocussing_pi_pulses = n_refocussing_pi_pulses

        #retained values that may be useful for examining pulse sequence
        #will be populated after call to 'program_pulser_state'
        self.pi_pulse_start_times = []
        self.left_pi_over_2_pulse_start = None
        self.right_pi_over_2_pulse_start = None

        self.clock_period = np.round(clock_period, 8)
        self.trigger_width = np.round(trigger_width, 8)

    def compute_rf_pulse_sequence(self, free_precession_time, n_refocussing_pi_pulses):
        '''
        Computes the start time and duration of the RF pulses given the
        desired free_precession_time and number of pi pulses.

        This does not program the hardware.

        returns a list of tuples (rf_start_time, pulse_duration), and half_cycle_width

        The half_cycle_width is 1/2 of full cycle width. The full cycle is one cycle where
        RF pulses are applied, follwed by a second cycle where only the initializing laser pulse exists
        (NB: this may need to be changed such that another initializing pulse is performed during
        the second half of the full cycle)
        '''
        self.raise_for_pulse_width(free_precession_time, n_refocussing_pi_pulses)
        rf_start_and_duration = []

        half_cycle_width = self.aom_width + self.aom_response_time
        half_cycle_width += self.pre_rf_pad
        half_cycle_width += self.rf_pi_pulse_width/2
        half_cycle_width += free_precession_time
        half_cycle_width += self.rf_pi_pulse_width/2
        half_cycle_width += self.post_rf_pad

        left_pi_over_2_pulse_start = self.aom_width + self.aom_response_time + self.pre_rf_pad - self.rf_response_time
        rf_start_and_duration.append((left_pi_over_2_pulse_start, self.rf_pi_pulse_width/2))

        n_free_precession_segments = n_refocussing_pi_pulses + 1
        delta_t_between_pi_pulses = free_precession_time / n_free_precession_segments

        refocussing_sequence_start_time = left_pi_over_2_pulse_start + self.rf_pi_pulse_width/2

        for i in range(n_refocussing_pi_pulses):
            start_time = refocussing_sequence_start_time + (i+1)*delta_t_between_pi_pulses - self.rf_pi_pulse_width/2
            duration = self.rf_pi_pulse_width
            rf_start_and_duration.append((start_time, duration))

        right_pi_over_2_pulse_start = left_pi_over_2_pulse_start  + free_precession_time + self.rf_pi_pulse_width/2

        rf_start_and_duration.append((right_pi_over_2_pulse_start, self.rf_pi_pulse_width/2))

        return rf_start_and_duration, half_cycle_width

    def program_pulser_state(self, free_precession_time = None,
                                   n_refocussing_pi_pulses = None, *args, **kwargs):
        '''
        free_precession_time is in seconds
        '''
        if free_precession_time is not None:
            _prev_free_precession_time = self.free_precession_time
            self.free_precession_time = np.round(free_precession_time,8)
        if n_refocussing_pi_pulses is not None:
            _prev_n_refocussing_pi_pulses = self.n_refocussing_pi_pulses
            self.n_refocussing_pi_pulses = n_refocussing_pi_pulses

        try:
            self.raise_for_pulse_width(self.free_precession_time, self.n_refocussing_pi_pulses)
        except Exception as e:
            #restore prior values
            self.free_precession_time = _prev_free_precession_time
            self.n_refocussing_pi_pulses = _prev_n_refocussing_pi_pulses
            raise e

        self.rf_start_and_duration, half_cycle_width = self.compute_rf_pulse_sequence(self.free_precession_time,
                                                                                 self.n_refocussing_pi_pulses)

        self.full_cycle_width  = half_cycle_width * 2

        hardware_pins = [self.aom_channel, self.rf_channel,
                         self.clock_channel, self.trigger_channel]
        self.open()

        pb = PBInd(pins = hardware_pins, on_time = int(self.full_cycle_width*1e9))

        self.start_programming()

        pb.on(self.trigger_channel, 0, int(self.trigger_width*1e9))
        pb.make_clock(self.clock_channel, int(self.clock_period*1e9))

        pb.on(self.aom_channel, 0, int(self.aom_width*1e9))
        for t, duration in self.rf_start_and_duration:
            pb.on(self.rf_channel, int(t*1e9), int(duration*1e9))
        pb.on(self.aom_channel, int(half_cycle_width*1e9), int(self.aom_width*1e9))

        pb.program([],float('inf'))

        self.stop_programming()

        self.close()
        return np.round(self.full_cycle_width / self.clock_period).astype(int)

    def experimental_conditions(self):
        '''
        Returns a dictionary of paramters that are pertinent for the relevant experiment
        '''
        return {
            'rf_pi_pulse_width':self.rf_pi_pulse_width,
            'aom_width':self.aom_width,
            'aom_response_time':self.aom_response_time,
            'post_rf_pad':self.post_rf_pad,
            'pre_rf_pad':self.pre_rf_pad,
            'full_cycle_width':self.full_cycle_width,
            'free_precession_time':self.free_precession_time,
            'clock_period':self.clock_period
        }

    def raise_for_pulse_width(self, free_precession_time, n_refocussing_pi_pulses = 0):

        if free_precession_time < n_refocussing_pi_pulses * self.rf_pi_pulse_width:
            raise PulseTrainWidthError(f"""free precession time, {free_precession_time}, is not
large enough to support requested number of refocusing pulses, {n_refocussing_pi_pulses},
of total duration {n_refocussing_pi_pulses * self.rf_pi_pulse_width}.""")
