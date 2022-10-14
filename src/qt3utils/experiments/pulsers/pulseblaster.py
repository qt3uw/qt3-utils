import numpy as np

from pulseblaster.PBInd import PBInd
import pulseblaster.spinapi

from qt3utils.experiments.pulsers.interface import ExperimentPulser
from qt3utils.errors import PulseBlasterInitError

class PulseBlasterCWODMRPulser(ExperimentPulser):
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
        #all times are converted to nanoseconds
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

        pb=PBInd(pins = hardware_pins, on_time = int(cycle_length*1e9))

        if pulseblaster.spinapi.pb_start_programming(self.pb_board_number) != 0:
            raise PulseBlasterError(pulseblaster.spinapi.pb_get_error())

        pb.on(self.trigger_channel, 0, int(self.trigger_width*1e9))
        pb.make_clock(self.clock_channel, int(self.clock_period*1e9))
        pb.on(self.aom_channel, 0, int(cycle_length*1e9))
        pb.on(self.rf_channel, 0, int(self.rf_width*1e9))

        pb.program([],float('inf'))

        if pulseblaster.spinapi.pb_stop_programming() != 0:
            raise PulseBlasterError(pulseblaster.spinapi.pb_get_error())

        self.close()
        return np.round(cycle_length / self.clock_period).astype(int)

    def start(self):
        self.open()
        if pulseblaster.spinapi.pb_start() != 0:
            raise PulseBlasterError(pulseblaster.spinapi.pb_get_error())
        self.close()

    def stop(self):
        self.open()
        if pulseblaster.spinapi.pb_stop() != 0:
            raise PulseBlasterError(pulseblaster.spinapi.pb_get_error())
        self.close()

    def close(self):
        if pulseblaster.spinapi.pb_close() != 0:
            raise PulseBlasterError(pulseblaster.spinapi.pb_get_error())

    def open(self):
        pulseblaster.spinapi.pb_select_board(self.pb_board_number)
        if pulseblaster.spinapi.pb_init() != 0:
            self.close() #if opening fails, attempt to close before raising error
            raise PulseBlasterInitError(pulseblaster.spinapi.pb_get_error())
        pulseblaster.spinapi.pb_core_clock(100*pulseblaster.spinapi.MHz)

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
