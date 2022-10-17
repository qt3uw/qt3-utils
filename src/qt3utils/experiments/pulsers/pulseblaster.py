import numpy as np

from pulseblaster.PBInd import PBInd
import pulseblaster.spinapi

from qt3utils.experiments.pulsers.interface import ExperimentPulser
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

class PulseBlasterHoldAOM(PulseBlaster):
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
        self.pb_board_number = pb_board_number
        self.aom_channel = aom_channel
        self.cycle_width = np.round(cycle_width, 8)

        # #should this all go inside the program_pulser_state method?
        # #and we can always ensure that the board program is closed
        # #if we did that, we would need to initialize and close
        # #communication around each call to start and stop
        # pulseblaster.spinapi.pb_select_board(self.pb_board_number)
        # if pulseblaster.spinapi.pb_init() != 0:
        #     self.close()
        #     if pulseblaster.spinapi.pb_init() != 0:
        #         raise PulseBlasterInitError(pulseblaster.spinapi.pb_get_error())
        # pulseblaster.spinapi.pb_core_clock(100*pulseblaster.spinapi.MHz)

    def program_pulser_state(self, *args, **kwargs):
        '''
        '''
        hardware_pins = [self.aom_channel]
        self.open()
        pb = PBInd(pins = hardware_pins, on_time = int(self.cycle_width*1e9))
        self.start_programming()

        pb.on(self.aom_channel, 0, int(self.cycle_width*1e9))
        pb.program([],float('inf'))
        self.stop_programming()

        self.close()
        return np.round(elf.cycle_width / self.clock_period).astype(int)

    def experimental_conditions(self):
        '''
        Returns an empty dictionary
        '''
        return {}

    def raise_for_pulse_width(self, *args, **kwargs):
        pass


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
                       rf_width = 5e-6,
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
        self.rf_width = np.round(rf_width, 8)
        self.clock_period = np.round(clock_period, 8)
        self.trigger_width = np.round(trigger_width, 8)

        # #should this all go inside the program_pulser_state method?
        # #and we can always ensure that the board program is closed
        # #if we did that, we would need to initialize and close
        # #communication around each call to start and stop
        # pulseblaster.spinapi.pb_select_board(self.pb_board_number)
        # if pulseblaster.spinapi.pb_init() != 0:
        #     self.close()
        #     if pulseblaster.spinapi.pb_init() != 0:
        #         raise PulseBlasterInitError(pulseblaster.spinapi.pb_get_error())
        # pulseblaster.spinapi.pb_core_clock(100*pulseblaster.spinapi.MHz)

    def program_pulser_state(self, rf_width = None, *args, **kwargs):
        '''
        rf_width is in seconds
        '''
        if rf_width:
            self.raise_for_pulse_width(rf_width)
            self.rf_width = np.round(rf_width,8)
        else:
            self.raise_for_pulse_width(self.rf_width)

        cycle_length = 2*self.rf_width

        hardware_pins = [self.aom_channel, self.rf_channel,
                         self.clock_channel, self.trigger_channel]

        self.open()
        pb = PBInd(pins = hardware_pins, on_time = int(cycle_length*1e9))
        self.start_programming()

        pb.on(self.trigger_channel, 0, int(self.trigger_width*1e9))
        pb.make_clock(self.clock_channel, int(self.clock_period*1e9))
        pb.on(self.aom_channel, 0, int(cycle_length*1e9))
        pb.on(self.rf_channel, 0, int(self.rf_width*1e9))

        pb.program([],float('inf'))
        self.stop_programming()

        self.close()
        return np.round(cycle_length / self.clock_period).astype(int)


    def experimental_conditions(self):
        '''
        Returns a dictionary of paramters that are pertinent for the relevant experiment
        '''
        return {
            'rf_width':self.rf_width,
            'clock_period':self.clock_period
        }

    def raise_for_pulse_width(self, rf_width, *args, **kwargs):
        if rf_width < 50e-9:
            raise PulseTrainWidthError(f'RF width too small {int(rf_width)} < 50 ns')

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
                       rf_width = 5e-6,
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
        self.rf_width = np.round(rf_width, 8)
        self.aom_response_time = np.round(aom_response_time, 8)
        self.rf_response_time = np.round(rf_response_time, 8)
        self.post_rf_pad = np.round(post_rf_pad, 8)
        self.pre_rf_pad = np.round(pre_rf_pad, 8)
        self.full_cycle_width = np.round(full_cycle_width, 8)
        self.rf_pulse_justify = rf_pulse_justify

        self.clock_period = np.round(clock_period, 8)
        self.trigger_width = np.round(trigger_width, 8)

    def program_pulser_state(self, rf_width = None, *args, **kwargs):
        '''
        rf_width is in seconds
        '''
        if rf_width:
            self.raise_for_pulse_width(rf_width)
            self.rf_width = np.round(rf_width,8)
        else:
            self.raise_for_pulse_width(self.rf_width)

        assert self.rf_pulse_justify in ['left', 'center', 'right', 'start_center']
        half_cycle_width = self.full_cycle_width / 2

        if self.rf_pulse_justify == 'center':
            delay_rf_channel = self.aom_width + (half_cycle_width - self.aom_width)/2 - self.rf_width/2 - self.rf_response_time
        if self.rf_pulse_justify == 'start_center':
            delay_rf_channel = self.aom_width + (half_cycle_width - self.aom_width)/2 - self.rf_response_time
        if self.rf_pulse_justify == 'left':
            delay_rf_channel = self.aom_width + self.aom_response_time + self.pre_rf_pad - self.rf_response_time
        if self.rf_pulse_justify == 'right':
            delay_rf_channel = half_cycle_width - self.post_rf_pad - self.rf_width - self.rf_response_time + self.aom_response_time

        hardware_pins = [self.aom_channel, self.rf_channel,
                         self.clock_channel, self.trigger_channel]
        self.open()

        pb = PBInd(pins = hardware_pins, on_time = int(self.full_cycle_width*1e9))
        self.start_programming()

        pb.on(self.trigger_channel, 0, int(self.trigger_width*1e9))
        pb.make_clock(self.clock_channel, int(self.clock_period*1e9))
        pb.on(self.aom_channel, 0, int(self.aom_width*1e9))
        pb.on(self.rf_channel, int(delay_rf_channel*1e9), int(self.rf_width*1e9))
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
            'rf_width':self.rf_width,
            'aom_width':self.aom_width,
            'aom_response_time':self.aom_response_time,
            'post_rf_pad':self.post_rf_pad,
            'pre_rf_pad':self.pre_rf_pad,
            'full_cycle_width':self.full_cycle_width,
            'rf_pulse_justify':self.rf_pulse_justify,
            'clock_period':self.clock_period
        }

    def raise_for_pulse_width(self, rf_width):
        #the following enforces that the full cycle width is large enough
        requested_total_width = self.aom_width
        requested_total_width += self.aom_response_time
        requested_total_width += self.pre_rf_pad
        requested_total_width += rf_width
        requested_total_width += self.post_rf_pad

        if requested_total_width >= self.full_cycle_width / 2:
            raise PulseTrainWidthError(f"full cycle width, {self.full_cycle_width / 2}, is not large enough to support requested pulse sequence, {requested_total_width}.")
