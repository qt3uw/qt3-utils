import time
import numpy as np
from qt3utils.pulsers.interface import ExperimentPulser
from qt3utils.errors import PulseTrainWidthError

class QCSapphCWODMRPulser(ExperimentPulser):
    '''
    Programs the pulse sequences needed for CWODMR.

    Provides an
      * always ON channel for an AOM.
      * 50% duty cycle pulse for RF switch
      * clock signal for use with a data acquisition card
      * trigger signal for use with a data acquisition card
    '''
    def __init__(self, qcsapphire_pulser_controller,
                       rf_channel = 'B',
                       clock_channel = 'C',
                       trigger_channel = 'D',
                       rf_pulse_duration = 5e-6,
                       clock_period = 200e-9,
                       trigger_width = 500e-9):
        """
        qcsapphire_pulser_controller - a qcsapphire.Pulser object
        rf_channel output controls a RF switch
        clock_channel output provides a clock input to the NI DAQ card
        trigger_channel output provides a rising edge trigger for the NI DAQ card
        """
        self.pulser = qcsapphire_pulser_controller
        self.rf_channel = rf_channel
        self.clock_channel = clock_channel
        self.trigger_channel = trigger_channel
        self.rf_pulse_duration = np.round(rf_pulse_duration, 8)
        self.clock_period = np.round(clock_period, 8)
        self.trigger_width = np.round(trigger_width, 8)

    def experimental_conditions(self):
        '''
        Returns a dictionary of paramters that are pertinent for the relevant experiment
        '''
        return {
            'rf_pulse_duration':self.rf_pulse_duration,
            'clock_period':self.clock_period
        }

    def raise_for_pulse_width(self, rf_pulse_duration, *args, **kwargs):
        if rf_pulse_duration < 10e-9:
            raise PulseTrainWidthError(f'RF width too small {int(rf_pulse_duration)} < 10 ns')

    def reset_pulser(self, num_resets = 2):

        # the QC Sapphire can enter weird states sometimes.
        # Observation shows that multiple resets, followed by some delay
        # results in a steady state for the pulser
        for i in range(num_resets):
            self.pulser.set_all_state_off()
            time.sleep(1)
        self.pulser.query('*RST')
        self.pulser.system.mode('normal')

    def program_pulser_state(self, rf_pulse_duration = None, *args, **kwargs):
        '''
        Program the pulser to generate a signals on all channels --
        RF channel, clock channel and trigger channel.

        Allows the user to set a different rf_pulse_duration after object instantiation.

        Note that, in this current implementation, the rf width is half the
        full cycle width of the pulser. That is, one full cycle is RF on for
        time 'rf_pulse_duration', followed by RF off for time 'rf_pulse_duration'.

        For CWODMR with the QCSapphire Pulser, the optical pumping laser must
        be on continuously through external means (typically, this is achieved
        either by removing the AOM or by holding 3.3V on the AOM switch).

        Note that the pulser will be in the OFF state after calling this function.
        Call self.start() for the QCSapphire to start generating signals.

        returns
            int: N_clock_ticks_per_cycle

        '''

        self.reset_pulser() # based on experience, we have to do this in order for the system to behave correctly... :(
        self.pulser.system.period(self.clock_period)

        #set up the clock pulse, which is normally here 1/2 the pulser's cycle period
        clock_channel = self.pulser.channel(self.clock_channel)
        clock_channel.mode('normal')
        clock_channel.width(np.round(self.clock_period/2, 8))
        clock_channel.delay(0)

        #set up the RF pulse
        if rf_pulse_duration:
            self.raise_for_pulse_width(rf_pulse_duration)
            self.rf_pulse_duration = np.round(rf_pulse_duration,8)
        else:
            self.raise_for_pulse_width(self.rf_pulse_duration)

        on_count_rf_channel = 1
        #if we support CWODMR setup where RF on duty cycle != 50%, would allow for user
        #to specify full_cycle_width and rf_pulse_duration separately.
        #but currently, we only support 50% duty cycle
        self.full_cycle_width = np.round(2 * self.rf_pulse_duration, 8)
        off_count_rf_channel = np.round(self.full_cycle_width/self.clock_period).astype(int) - on_count_rf_channel

        rf_channel = self.pulser.channel(self.rf_channel)
        rf_channel.mode('dcycle')
        rf_channel.width(self.rf_pulse_duration)
        rf_channel.delay(0)
        rf_channel.pcounter(on_count_rf_channel)
        rf_channel.ocounter(off_count_rf_channel)

        #trigger pulse is set up similarly, but we use a smaller width
        trigger_channel = self.pulser.channel(self.trigger_channel)
        trigger_channel.mode('dcycle')
        trigger_channel.width(np.round(self.trigger_width,8))
        trigger_channel.delay(0)
        trigger_channel.pcounter(on_count_rf_channel)
        trigger_channel.ocounter(off_count_rf_channel)

        return np.round(self.full_cycle_width / self.clock_period).astype(int)

    def _set_state(self, state = 1):
        self.pulser.channel(self.rf_channel).state(state)
        self.pulser.channel(self.clock_channel).state(state)
        self.pulser.channel(self.trigger_channel).state(state)
        self.pulser.system.state(state)

    def start(self):
        self._set_state(1)

    def stop(self):
        self._set_state(0)


class QCSapphPulsedODMRPulser(ExperimentPulser):
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
    def __init__(self, qcsapphire_pulser_controller,
                       aom_channel = 'A',
                       rf_channel = 'B',
                       clock_channel = 'C',
                       trigger_channel = 'D',
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
        qcsapphire_pulser_controller - a qcsapphire.Pulser object
        rf_channel output controls a RF switch
        clock_channel output provides a clock input to the NI DAQ card
        trigger_channel output provides a rising edge trigger for the NI DAQ card
        """
        self.pulser = qcsapphire_pulser_controller
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

    def reset_pulser(self, num_resets = 2):

        # the QC Sapphire can enter weird states sometimes.
        # Observation shows that multiple resets, followed by some delay
        # results in a steady state for the pulser
        for i in range(num_resets):
            self.pulser.set_all_state_off()
            time.sleep(1)
        self.pulser.query('*RST')
        self.pulser.system.mode('normal')

    def raise_for_pulse_width(self, rf_pulse_duration):
        #the following enforces that the full cycle width is large enough
        requested_total_width = self.aom_width
        requested_total_width += self.aom_response_time
        requested_total_width += self.pre_rf_pad
        requested_total_width += rf_pulse_duration
        requested_total_width += self.post_rf_pad

        if requested_total_width >= self.full_cycle_width / 2:
            raise PulseTrainWidthError(f"full cycle width, {self.full_cycle_width / 2}, is not large enough to support requested pulse sequence, {requested_total_width}.")

    def program_pulser_state(self, rf_pulse_duration = None, *args, **kwargs):
        '''
        Sets the pulser to generate a signals on all channels -- AOM channel,
        RF channel, clock channel and trigger channel.

        Allows the user to set a different rf_pulse_duration after object instantiation.

        Note that the pulser will be in the OFF state after calling this function.
        Call self.start() for the QCSapphire to start the pulser.

        A cycle is one full sequence of the pulse train used in the experiment.
        For pulsed ODMR, a cycle is {AOM on, AOM off/RF on, AOM on, AOM off/RF off}.

        returns
            int: N_clock_ticks_per_cycle

        '''
        if rf_pulse_duration: #update to a different rf_pulse_duration
            self.raise_for_pulse_width(rf_pulse_duration)
            self.rf_pulse_duration = np.round(rf_pulse_duration,8)
        else:
            self.raise_for_pulse_width(self.rf_pulse_duration)

        assert self.rf_pulse_justify in ['left', 'center', 'right', 'start_center']
        half_cycle_width = self.full_cycle_width / 2

        self.reset_pulser() # based on experience, we have to do this in order for the system to behave correctly... :(
        self.pulser.system.period(self.clock_period)

        on_count_aom_channel = 1
        off_count_aom_channel = np.round(half_cycle_width/self.clock_period,8).astype(int) - on_count_aom_channel
        channel = self.pulser.channel(self.aom_channel)
        channel.mode('dcycle')
        channel.width(self.aom_width)
        channel.pcounter(on_count_aom_channel)
        channel.ocounter(off_count_aom_channel)

        if self.rf_pulse_justify == 'center':
            delay_rf_channel = self.aom_width + (half_cycle_width - self.aom_width)/2 - self.rf_pulse_duration/2 - self.rf_response_time
        if self.rf_pulse_justify == 'start_center':
            delay_rf_channel = self.aom_width + (half_cycle_width - self.aom_width)/2 - self.rf_response_time
        if self.rf_pulse_justify == 'left':
            delay_rf_channel = self.aom_width + self.aom_response_time + self.pre_rf_pad - self.rf_response_time
        if self.rf_pulse_justify == 'right':
            delay_rf_channel = half_cycle_width - self.post_rf_pad - self.rf_pulse_duration - self.rf_response_time + self.aom_response_time

        #todo: check to be sure the RF pulse is fully outside of the aom response + pad time, raise exception if violated

        delay_rf_channel = np.round(delay_rf_channel,8)
        self.delay_rf_channel = delay_rf_channel #retain value for analysis

        on_count_rf_channel = 1
        off_count_rf_channel = np.round(self.full_cycle_width/self.clock_period).astype(int) - on_count_rf_channel
        channel = self.pulser.channel(self.rf_channel)
        channel.mode('dcycle')
        channel.width(self.rf_pulse_duration)
        channel.delay(delay_rf_channel)
        channel.pcounter(on_count_rf_channel)
        channel.ocounter(off_count_rf_channel)

        channel = self.pulser.channel(self.clock_channel)
        channel.mode('normal')
        channel.width(np.round(self.clock_period/2, 8))
        channel.delay(0)

        channel = self.pulser.channel(self.trigger_channel)
        channel.mode('dcycle')
        channel.width(np.round(self.trigger_width,8))
        channel.delay(0)
        channel.pcounter(1)
        channel.ocounter(np.round(self.full_cycle_width/self.clock_period).astype(int) - 1)

        return np.round(self.full_cycle_width / self.clock_period).astype(int)

    def _set_state(self, state = 1):
        self.pulser.channel(self.aom_channel).state(state)
        self.pulser.channel(self.rf_channel).state(state)
        self.pulser.channel(self.clock_channel).state(state)
        self.pulser.channel(self.trigger_channel).state(state)
        self.pulser.system.state(state)

    def start(self):
        self._set_state(1)

    def stop(self):
        self._set_state(0)
