import numpy as np
from dpg11_pylib import waveforms
from qt3utils.pulsers.interface import ExperimentPulser
from qt3utils.errors import PulseTrainWidthError

# Create the dpg11 pulser class
class DPG11Pulser(ExperimentPulser):
    '''
    This is the base class for the DPG11 pulser. It provides the basic functionality for the DPG11.
    This includes starting the output of the dpg11 and stopping the output of the dpg11.
    ''' 
    
    def start(self):
        '''
        Start the DPG11 output.
        '''
        self.pulser.run(execute=True)
        
    def stop(self):
        '''
        Stop the DPG11 output.
        '''
        self.pulser.stop(execute=True)
        
# Create the cwodmr class for the dpg11
class DPG11CWODMRPulser(DPG11Pulser):
    '''
    Programs the pulse sequences needed for CWODMR.

    Provides an
      * always ON channel for an AOM.
      * 50% duty cycle pulse for RF switch
      * clock signal for use with a data acquisition card
      * trigger signal for use with a data acquisition card
    '''
    def __init__(self, dpg11_driver,
                 rf_channel=1,
                 aom_channel=2,
                 clock_channel=3,
                 trigger_channel=4,
                 rf_pulse_duration=5e-6,
                 clock_period=200e-9,
                 trigger_width=500e-9):
        '''
        Parameters
        ----------
        dpg11_driver : DPG11Device
            DPG11Device object from the dpg11_pylib.driver package.
        rf_channel : int
            Channel to use for the RF switch. Default is 1.
        aom_channel : int
            Channel to use for the AOM. Controls the postive voltage on the AOM Default is 2.
        clock_channel : int
            Channel to use for the clock signal on the NI DAQ card. Default is 3.
        trigger_channel : int
            Channel to use for the trigger signal. Provides a rising edge trigger for the NI DAQ card Default is 4.
        rf_pulse_duration : float
            Duration of the RF pulse in seconds. Default is 5e-6.
        clock_period : float
            Period of the clock signal in seconds. Default is 200e-9.
        trigger_width : float
            Width of the trigger signal in seconds. Default is 500e-9.
        '''
        self.pulser = dpg11_driver
        self.rf_channel = rf_channel
        self.aom_channel = aom_channel
        self.clock_channel = clock_channel
        self.trigger_channel = trigger_channel
        self.rf_pulse_duration = rf_pulse_duration
        self.clock_period = clock_period
        self.trigger_width = trigger_width
        
        # add the limits of the dpg11, this is set by default in the dpg11_pylib. the lowest sample rate is 50 MHz
        self.clock_limits = self.pulser.internal_clock_rate_limits_in_hz

    def experimental_conditions(self):
        '''
        Returns a dictionary of paramters that are pertinent for the relevant experiment
        '''
        return {
            'rf_pulse_duration':self.rf_pulse_duration,
            'clock_period':self.clock_period
        }
    
    # Create the function to raise an error if the pulse width is too small
    # TODO: Update to the limits of our devices
    def raise_for_pulse_width(self, rf_pulse_duration, *args, **kwargs):
        if rf_pulse_duration < 10e-9:
            raise PulseTrainWidthError(f'RF width too small {int(rf_pulse_duration)} < 10 ns')
    
    # Create error function for checking if the clock rate is too small or too high
    def raise_for_clock_rate(self, clock_rate, *args, **kwargs):
        if clock_rate > self.clock_limits[1]:
            raise ValueError(f'Clock rate too large {clock_rate} > {self.clock_limits[1]}')
        if clock_rate < self.clock_limits[0]:
            raise ValueError(f'Clock rate too small {clock_rate} < {self.clock_limits[0]}')
    
    # create function to reset the pulser. This may be needed for the dpg11
    # TODO: Populate this function if we determine it is necessary
    def reset_pulser(self, num_resets = 2):

        # the QC Sapphire can enter weird states sometimes.
        # Observation shows that multiple resets, followed by some delay
        # results in a steady state for the pulser
        print("reset :)")
        # for i in range(num_resets):
        #     self.pulser.set_all_state_off()
        

    # Create the function to program the pulse sequence
    def program_pulser_state(self, rf_pulse_duration = None, *args, **kwargs):
        '''
        Program the pulser to generate a signals on all channels --
        RF channel, clock channel and trigger channel.

        Allows the user to set a different rf_pulse_duration after object instantiation.

        Note that, in this current implementation, the rf width is half the
        full cycle width of the pulser. That is, one full cycle is RF on for
        time 'rf_pulse_duration', followed by RF off for time 'rf_pulse_duration'.

        For CWODMR with the DPG11 right now, the optical pumping laser must
        be on continuously through external means (typically, this is achieved
        either by removing the AOM or by holding 3.3V on the AOM switch).

        Note that the pulser will be in the OFF state after calling this function.
        Call self.start() for the DPG11 to start generating signals.

        returns
            int: N_clock_ticks_per_cycle
        '''
        # Reset device, see if this is necessary in the future.
        # self.reset_pulser() # based on experience, we have to do this in order for the system to behave correctly... :(
        
        # Set the pulser clock cycle
        # get the clock rate
        self.clock_rate = 1/self.clock_period
        
        # check if the clock rate is within the limits of the dpg11
        # the dpg11 has a rather high min freq (25 MHz) which is larger than the max freq of the ni daq card
        # so we need to emulate the clock rate. This will lead to a self.freq_multiplier that will 
        # need to be carried through all of the waveform arrays. I will create the functions 
        # to create these arrays to accomodate for this multiplier. If not too small, then freq_multiplier = 1
        # check if too small
        if self.clock_rate < self.clock_limits[0]:
            # emulate the frequency until it hits the proper limits
            self.sample_rate, self.freq_multiplier = waveforms.downconvert_clock_frequency(self.clock_rate, 
                                                                                           self.clock_limits[0])
        else:
            # Check if the clock rate is too large
            self.raise_for_clock_rate(self.clock_rate)
            self.sample_rate = self.clock_rate
            
            
        # stop any output of the dpg11 and set the sample_rate
        self.pulser.stop_ouput_set_clk(self.sample_rate)

        
        # setup the rf pulse 
        if rf_pulse_duration:
            self.raise_for_pulse_width(rf_pulse_duration)
            self.rf_pulse_duration = np.round(rf_pulse_duration, 8)
        # Make sure that the rf_pulse_duration is not too small
        else:
            self.raise_for_pulse_width(self.rf_pulse_duration)
        # get mod 64 samples and duration for rf pulse
        self.rf_pulse_samples, self.rf_pulse_duration = waveforms.length_mod_64(self.rf_pulse_duration,
                                                                                self.sample_rate)
        
        # Set the cycle in terms of the number of samples  and time
        cycle_samples = self.rf_pulse_samples*2
        cycle_time = self.rf_pulse_duration*2
        trigger_samples = int(self.trigger_width*self.sample_rate)
        
        
        # Create all of the waveforms for the different channels
        # rf waveform that is on for the rf_pulse_duration and off for the rest of the cycle
        rf_waveform = waveforms.pad_waveform(waveform = np.ones(self.rf_pulse_samples),
                                             length = cycle_samples)
        # aom waveform that is on for the whole time
        aom_waveform = np.ones(cycle_samples).astype(int)
        # clock waveform for the while cycle
        clock_waveform = waveforms.offOnArray(size=self.freq_multiplier,
                                              length=cycle_samples)
        # trigger waveform that is on for the trigger_width and off for the rest of the cycle?
        trigger_waveform = waveforms.pad_waveform(waveform = np.ones(trigger_samples),
                                                  length=cycle_samples)
        
        # Create the waveform dictionary to create the full waveform on all channels
        waveform_dict = {self.rf_channel:rf_waveform,
                         self.aom_channel:aom_waveform,
                         self.clock_channel:clock_waveform,
                         self.trigger_channel:trigger_waveform}
        
        # print(waveform_dict)
        # Create the wavefile
        self.wavefile_name = self.pulser.create_wave_file(wave_name='cwodmr_wave',
                                                          wave_dict=waveform_dict)
        # Load the wavefile onto the dpg11. It won't execute until the user calls the run function
        self.pulser.create_single_segment(self.wavefile_name,
                                          execute = True)