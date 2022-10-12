import time
import numpy as np
from qt3utils.experiments.pulsers.interface import ODMRPulser, RabiPulser, Pulser

class QCSapphCWODMRPulser(ODMRPulser):

    def __init__(self, qcsapphire_pulser_controller,
                       rf_channel = 'B',
                       clock_channel = 'C',
                       trigger_channel = 'D',
                       clock_period = 200e-9,
                       trigger_width = 300e-9):
        """
        qcsapphire_pulser_controller - a qcsapphire.Pulser object
        rf_channel output controls a RF switch
        clock_channel output provides a clock input to the NI DAQ card
        trigger_channel output provides a rising edge trigger for the NI DAQ card
        """
        self.rf_channel = rf_channel
        self.clock_channel = clock_channel
        self.trigger_channel = trigger_channel
        self.pulser = qcsapphire_pulser_controller
        self.clock_period = clock_period
        self.trigger_width = trigger_width

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
        Sets the pulser to generate a signals on all channels --
        RF channel, clock channel and trigger channel.

        Allows the user to set a different rf_width after object instantiation.

        Note that, in this current implementation, the rf width is half the
        full cycle width of the pulser. That is, one full cycle is RF on for
        time 'rf_width', followed by RF off for time 'rf_width'.

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
        rf_width = np.round(rf_width,8)
        self.rf_width = rf_width

        on_count_rf_channel = 1
        #if we support CWODMR setup where RF on duty cycle != 50%, would allow for user
        #to specify full_cycle_width and rf_width separately.
        #but currently, we only support 50% duty cycle
        self.full_cycle_width = np.round(2 * self.rf_width, 8)
        off_count_rf_channel = np.round(self.full_cycle_width/self.clock_period).astype(int) - on_count_rf_channel

        rf_channel = self.pulser.channel(self.rf_channel)
        rf_channel.mode('dcycle')
        rf_channel.width(rf_width)
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
