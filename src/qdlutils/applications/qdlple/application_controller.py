import logging
import time

import numpy as np

from qdlutils.hardware.nidaq.counters.nidaqtimedratecounter import NidaqTimedRateCounter
from qdlutils.hardware.nidaq.analogoutputs.nidaqvoltage import NidaqVoltageController

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class PleScanner:
    '''
    Base class with basic scanning PLE functionality. 

    Current PLE implementation consists of sequential "fast" scans by sweeping
    the laser frequency via the `wavelength_controller` agrument while simultaneously
    reading in data via the DAQ (or other generic input source) via the initialization
    argument `readers`.
        Currently only a basic DAQ reader is implemented. Additional readers for 
        simultaneous processing will require additional development at this time.
    '''

    def __init__(self, 
                 readers: dict, 
                 wavelength_controller: NidaqVoltageController,
                 auxiliary_controllers: dict = {}) -> None:
        '''
        Args:
            readers                 :   Dictionary of data generators, class can be arbitrary
                                        but should be used to collect data on each scan.
                                        Later implementations may split this into a principal
                                        reader (to control timing) and sub-readers for
                                        additional data collection.
            wavelength_controller   :   Wavelength controller class inheriting from
                                        qdlutils.nidaq.customcontrollers.WavelengthControlBase
            auxiliary_controllers   :   A dictionary of additional controllers of arbitrary
                                        class. Use this to pass additional controllers for
                                        intermidiate steps such as pulse sequencing.
                                        A basic form of unconditional repump is implemented here.
        
        '''
        # Store the readers and wavelength controller
        self.readers = readers
        self.wavelength_controller = wavelength_controller
        self.auxiliary_controllers = auxiliary_controllers
        
        # Control variables for system state
        self.running = False
        self.stop_scan = False
        self.current_frame = 0

        # Scan parameters
        # Base parameters
        self.min = None                     # Minimum voltage for sweep
        self.max = None                     # Maximum voltage for sweep
        self.n_pixels_up = None             # Number of pixels on upsweep
        self.n_pixels_down = None           # Number of pixels on downsweep
        self.n_subpixels = None             # Number of subpixels
        self.time_up = None                 # Time for upsweep in seconds
        self.time_down = None               # Time for downsweep in seconds
        self.n_scans = None                 # Max number of scans to perform
        self.time_repump = None             # Time for repump in miliseconds
        # Calculated parameters 
        self.pixel_step_size_up = None      # Voltage per pixel on upsweep
        self.pixel_step_size_down = None    # Voltage per pixel on downsweep
        self.sample_step_size_up = None     # Voltage per sample on upsweep
        self.sample_step_size_down = None   # Voltage per sample on downsweep
        self.pixel_voltages_up = None       # Voltages at pixels on upsweep
        self.pixel_voltages_down = None     # Voltages at pixels on downsweep
        self.sample_voltages_up = None      # Votlages at samples on upsweep
        self.sample_voltages_down = None    # Voltages at samples on downsweep
        self.pixel_time_up = None           # Time per pixel on upsweep
        self.pixel_time_down = None         # time per pixel on downsweep
        self.sample_time_up = None          # Time per sample on upsweep
        self.sample_time_down = None        # Time per sample on downsweep
        
        # Ouptuts
        self.outputs = []
        # If you want additional data to be stored you can include new variables
        # here and then ensure that the self.single_scan() method writes the results
        # to the attributes.

    def start(self) -> None:
        '''
        Start up the readers
        '''
        self.running = True
        for reader in self.readers:
            self.readers[reader].start()
            logger.info(f'Starting reader {reader}')

    def stop(self) -> None:
        '''
        Stop running scan
        '''
        self.running = False
        for reader in self.readers:
            self.readers[reader].stop()
            logger.info(f'Stopping reader {reader}')

    def still_scanning(self) -> bool:
        '''
        Return boolean to determine of the scan should continue.
        Returning True means the scan should continue.
        Returning False means the scan should stop.
        '''
        if self.running == False:  # this allows external process to stop scan
            return False

        if self.current_frame < self.n_scans:  # stops scan when reaches final position
            return True
        else:
            self.running = False
            return False

    def go_to(self, wl_point: float) -> None:
        # This is probably redundant beyond simply being a wrapper for the wavelength controller method....
        '''
        Set the wavelength controller to desired point
        '''
        try:
            self.wavelength_controller.go_to_voltage(voltage = wl_point)
        except ValueError as e:
            logger.info(f'Out of range\n\n{e}')

    def configure_scan(self, 
                       min: float, 
                       max: float, 
                       n_pixels_up: int, 
                       n_pixels_down: int, 
                       n_subpixels: int,
                       time_up: float,
                       time_down: float,
                       n_scans: int,
                       time_repump: float) -> list:
        '''
        This function configures the PleScanner scan properties.

        A single scan consists of sweeping the voltage from `min` -> `max` 
        -> `min` collecting data at `n_pixels_up` points on the `min` -> `max`
        upsweep and then `n_pixels_down` points on the `max` -> `min` downsweep.
        The upsweep and downsweep are performed in `time_up` and `time_down`
        seconds respectively which need not be equal nor correspond to the same
        voltage-per-pixel rate.
        Scans are repeated up to `n_scans` times.

        Within each pixel, the voltage is swept over `n_subpixels` intermidate
        points to ensure roughly continuous scanning of the voltage frequency.
        Data at the intermediate points are binned (summed together) and the
        resulting value is representative of the corresponding point at the start
        of the bin window.
        By convention, `n_subpixels` = 1 corresponds to no sub-pixel scanning
        because the number of samples per pixel is 1.

        Step sizes (going both up or down) are calculated

            step_size = (end - start) / n_pixels

        And the voltages are swept along points defined by

            >> np.arange(start, end, step_size)

        When the number of subpixels `n_subpixels` is greater than 1, the voltage 
        is swept in step sizes

            sub_step_size = (end - start) / (n_pixels * n_subpixels)

        with counts integrated in `n_subpixels` sized bins.


        
        As an example, suppose we have the following inputs
                min: 0, 
                max: 1, 
                n_pixels_up: 4, 
                n_pixels_down: 2, 
                n_subpixels: 2
        The data ont he upsweep is associated to points spaced by 

            step_size = (1 - 0) / 4 = 0.25

        and is taken at the subpixels with voltages spaced by

            sub_step_size = (1 - 0) / (4 * 2) = 0.125
            
        Thus, we have on the upsweep:
            Data associated to: [0,        0.25,         0.50, 0.75]
                                |          |             |
            Data recorded at  : [0, 0.125, 0.250, 0.375, ...]       
                ^ 
                (Note: these are the subpixel samples)
            
        A similar set of calcuations for the down sweep yield
            Data associated to: [1,       0.5       ]
                                |         |            
            Data recorded at  : [1, 0.75, 0.50, 0.25]
            


        Why is data taken this way?
            Ideally, the subpixels should be centered around the associated voltage value, 
            however when the voltages are at the extrema this would cause values to be probed
            outside of the allowable voltage ranges. Sampling data in this manner allows one
            the sub-pixel scanning to be done in a self-consistent manner.

            One could attempt to "re-center" the pixels by shifting their associated voltages
            to the center of the subpixel (i.e. by adding `step_size/2`) but this will not 
            change the actual shape of the curve. This shift might be confusing to an
            unfamiliar user, and would be incorrect for `n_subpixels` = 0, so we opt for
            the current sampling method.
            Note that "re-centering" of the pixel may be important in cases where the voltage
            samples are replaced by frequencies (e.g. in wavemeter-assisted PLE) but in such
            cases sub-pixel scanning should probably be disabled.

            While it would appear that the voltage never actually reaches the "end" value on
            either the up/down sweep, the start of the next down/up will move the voltage to
            that value so that the overall voltage curve is continuous and has no duplicates.
            Note that, in practice, the number of pixels on a scan should be sufficient to
            resolve the signal features independent of the subpixel scanning.

        '''
        # First step is to validate the inputs
        # Check if the voltage limits are valid
        if max > min:
            self.wavelength_controller.validate_value(voltage=min)
            self.wavelength_controller.validate_value(voltage=max)
        else:
            raise ValueError(f'Requested max {max:.3f} is less than min {min:.3f}.')
        # Check if pixel numbers are valid
        # There must be at least one pixel and it must be integer valued
        if type(n_pixels_up) is not int or n_pixels_up < 1:
            raise ValueError(f'Requested # pixels up {n_pixels_up} is invalid (must be at least 1).')
        if type(n_pixels_down) is not int or n_pixels_down < 1:
            raise ValueError(f'Requested # pixels down {n_pixels_down} is invalid (must be at least 1).')
        if type(n_subpixels) is not int or n_subpixels < 1:
            raise ValueError(f'Requested # subpixels {n_subpixels} is invalid (must be at least 1).')
        # Check if upsweep and downsweep times are valid
        # Sweep times must be larger than zero (can be made small if desired)
        if not (time_up > 0):
            raise ValueError(f'Requested upsweep time {time_up}s is invalid (must be > 0).')
        if not (time_down > 0):
            raise ValueError(f'Requested downsweep time {time_down}s is invalid (must be > 0).')
        # Check if the number of scans is valid
        if type(n_scans) is not int or n_scans < 1:
            raise ValueError(f'Requested # of scans {n_scans} is invalid (must be at least 1).')
        # Check if repump time is valid
        if time_repump < 0:
            raise ValueError(f'Requested repump time {time_repump} is invalid (must be non-negative).')

        # If all valid, set the class instance variables
        self.min = min
        self.max = max
        self.n_pixels_up = n_pixels_up
        self.n_pixels_down = n_pixels_down
        self.n_subpixels = n_subpixels
        self.time_up = time_up
        self.time_down = time_down
        self.n_scans = n_scans
        self.time_repump = time_repump

        # Calculate and save the secondary class instance variables
        # Calculate the step sizes for output value readings
        self.pixel_step_size_up = (max - min) / n_pixels_up
        self.pixel_step_size_down = (min - max) / n_pixels_down  # Should be negative
        # Calculate step sizes for sub-pixel scans
        self.sample_step_size_up = (max - min) / (n_pixels_up * n_subpixels)
        self.sample_step_size_down = (min - max) / (n_pixels_down * n_subpixels)  # Should be negative
        
        # Calculate the output voltage readings
        #self.pixel_voltages_up = np.arange(min, max, self.pixel_step_size_up)
        #self.pixel_voltages_down = np.arange(max, min, self.pixel_step_size_down)
        self.pixel_voltages_up = np.linspace(min, max - self.pixel_step_size_up, n_pixels_up)
        self.pixel_voltages_down = np.linspace(max, min + self.pixel_step_size_down, n_pixels_down)
        # Calculate the sample voltage readings
        #self.sample_voltages_up = np.arange(min, max, self.sample_step_size_up)
        #self.sample_voltages_down = np.arange(max, min, self.sample_step_size_down)
        self.sample_voltages_up = np.linspace(min, max - self.sample_step_size_up, n_pixels_up * n_subpixels)
        self.sample_voltages_down = np.linspace(max, min - self.sample_step_size_down, n_pixels_down * n_subpixels)

        # Calculate time per pixel
        self.pixel_time_up = time_up / n_pixels_up
        self.pixel_time_down = time_down / n_pixels_down
        # Calculate time per sample
        self.sample_time_up = time_up / (n_pixels_up * n_subpixels)
        self.sample_time_down = time_down / (n_pixels_down * n_subpixels)

        # Send data to logger
        logger.debug('Configuring the scan')
        logger.debug(f'pixel_step_size_up    = {self.pixel_step_size_up}')
        logger.debug(f'pixel_step_size_down  = {self.pixel_step_size_down}')
        logger.debug(f'sample_step_size_up   = {self.sample_step_size_up}')
        logger.debug(f'sample_step_size_down = {self.sample_step_size_down}')
        logger.debug(f'pixel_time_up    = {self.pixel_time_up}')
        logger.debug(f'pixel_time_down  = {self.pixel_time_down}')
        logger.debug(f'sample_time_up   = {self.sample_time_up}')
        logger.debug(f'sample_time_down = {self.sample_time_down}')
        logger.debug(f'pixel_voltages_up    = {self.pixel_voltages_up}')
        logger.debug(f'pixel_voltages_down  = {self.pixel_voltages_down}')
        logger.debug(f'sample_voltages_up   = {self.sample_voltages_up}')
        logger.debug(f'sample_voltages_down = {self.sample_voltages_down}')
        


    def scan_wavelengths(self) -> None:
        """
        Scans the wavelengths from v_start to v_end in steps of step_size.
        Records the output from the readers into a list of dictionaries
        """

        self.outputs.append(self.single_scan())
        self.current_frame = self.current_frame + 1

    
    def single_scan(self) -> list:
        '''
        Performs a single scan as described in the the header for 
        self.configure_scan() defined above.

        PleScanner instance must be configured via self.configure_scan() 
        before running this method.

        Using the scan configuration stored in the instance, this function
        scans each of the voltages in `self.sample_voltages_up` sampling data via
        the `self.readers` with a sample time given by `self.sample_time_up`.
        Then scans `self.sample_voltages_down` sampling data via
        the `self.readers` with a sample time given by `self.sample_time_down`.
        The data is then binned into sequential, non-overlapping groups of size 
        `n_subpixels`.

        The resulting output is a list of counts corresponding to each
        `self.pixel_voltages_up` concatenated with a corresponding list of counts
        corresponding to `self.pixel_voltages_down`.

        TODO: Implementing other readers simultaneously can cause some problems
        need to do some threading to handle this case. Ideally we can set a so-called
        principal reader which handles the timing and then use that to end daemonized
        threads for the other readers. Logic for the readouts and processing for each
        of the specific readers needs to be handeled in this class, probably by defining
        additional thread target functions below.
        '''

        # Check if not yet configured
        if self.n_scans is None:
            raise ValueError('Instance variable n_scans is None; have you run configure_scan()?')

        # Create a dict for the ouptuts
        # The keys are the names of the readers and the values are empty lists
        output = {key: [] for key in self.readers.keys()}
        
        # Set the wavelength to the start position
        self.wavelength_controller.go_to_voltage(voltage=self.min)

        # Define a dictionary to store the raw outputs at each voltage sample.
        raw_output_at_samples_up = {key: [] for key in self.readers.keys()}
        raw_output_at_samples_down = {key: [] for key in self.readers.keys()}

        # Perform the repump (checking at 0.01 us to avoid floating point error)
        # If operating with faster switches for repump, limit can be modified
        if self.time_repump > 0.00001:
            # Perform the repump
            self.repump()

        # Log start of upsweep
        logger.info(f'Starting upsweep on scan {self.current_frame+1}.')

        # Configure the DAQ counter for the upsweep
        for reader in self.readers:
            if isinstance(self.readers[reader], NidaqTimedRateCounter):
                self.readers[reader].configure_sample_time(sample_time=self.sample_time_up)

        # Scan the upsweep over all sample voltages
        for voltage in self.sample_voltages_up:

            # Go to the voltage
            self.wavelength_controller.go_to_voltage(voltage=voltage)
            logger.debug(f'Move to voltage: {voltage}')

            # We want to eventually handle multiple readers simultaneously
            # However in the current setup this is not straightforward
            # For now we will have a simplifed fix that only performs readout when
            # the reader is of the specified QT3ScanNIDAQEdgeCounterController class
            # In all other cases nothing happens.
            # However since we need to check each reader this will cause extraneous 
            # if statements causing some lag.
            for reader in self.readers:

                # Check if reader is the desired class.
                # Everything in here probably needs to be in a separate thread target
                # function and additional threads need to be launched for other readers
                if isinstance(self.readers[reader], NidaqTimedRateCounter):

                    # This samples one batch consisting of N clock cycles on the DAQ
                    # where N = self.sample_time_up * clock_frequency (which is set
                    # by the YAML configuration file). Note that this results in a
                    # truncation of the actual sample time to the resolution of the
                    # clock rate, but we can more or less ignore these errors since
                    # they are generally very small (< 1 microsecond).
                    # The output counts_at_sample is an array [[counts, N]] where,
                    # again, N is the number of clock cycles per batch.

                    # New update: get a single batch raw output
                    # Code currently expects the 2d output so reshape it for now
                    raw_counts_at_sample = self.readers[reader].sample_batch_raw().reshape(1,2) 

                    # Write raw counts to outputs dictionary
                    # The dictionary value at the desired reader will take the form
                    # [[[counts at voltage[i], clock_cycles at voltage[i]]], for i in samples]
                    raw_output_at_samples_up[reader].append(raw_counts_at_sample)

        # Log start of downsweep
        logger.info(f'Finished upsweep on scan {self.current_frame+1}')
        logger.info(f'Starting downsweep on scan {self.current_frame+1}')

        # Configure the DAQ counter for the downsweep
        for reader in self.readers:
            if isinstance(self.readers[reader], NidaqTimedRateCounter):
                self.readers[reader].configure_sample_time(sample_time=self.sample_time_down)

        # Now scan the voltages down
        for voltage in self.sample_voltages_down:
            # Go to the voltage
            self.wavelength_controller.go_to_voltage(voltage=voltage)
            logger.debug(f'Move to voltage: {voltage}')
            # Same as before; must be modified accordingly to handle multiple readers.
            for reader in self.readers:
                if isinstance(self.readers[reader], NidaqTimedRateCounter):
                    # New update: get a single batch raw output
                    # reshaping for now since output is expected to be weird.
                    raw_counts_at_sample = self.readers[reader].sample_batch_raw().reshape(1,2) 
                    # Now saving to downsweep dictionary
                    raw_output_at_samples_down[reader].append(raw_counts_at_sample)

        # Log end of downsweep
        logger.info(f'Finished downsweep on scan {self.current_frame+1}')
        # Return to start position
        self.wavelength_controller.go_to_voltage(voltage=self.min)
        logger.debug(f'Move to voltage: {voltage}')

        # Write the raw data to the class instance?

        # Process the data from the scan
        for reader in self.readers:
            # Logic for processing each type of reader will depend on the output structure
            # of the corresponding reader. Thus, each type should be implemented separately
            if isinstance(self.readers[reader], NidaqTimedRateCounter):

                # Remove the extra dimension(s)
                raw_output_up = np.array(raw_output_at_samples_up[reader]).squeeze()
                # Get the raw counts and number of clock cycles
                raw_counts_up = raw_output_up[:,0]  # Raw counts at each sample voltage
                num_cycles_up = raw_output_up[:,1]  # Number of cycles at each sample voltage

                # Bin the counts into pixels
                # Reshape into array of size (n_pixels_up, n_subpixels)
                pre_binned_raw_counts_up = raw_counts_up.reshape(self.n_pixels_up, self.n_subpixels)
                # Then sum over the first axis (end array is of length n_pixels_up)
                binned_raw_counts_up = np.sum(pre_binned_raw_counts_up, axis=1)
                # Now rescale by pixel_time_up to get counts/s at each pixel
                counts_per_second_up = binned_raw_counts_up / self.pixel_time_up

                # Repeat for downscan
                raw_output_down = np.array(raw_output_at_samples_down[reader]).squeeze()
                raw_counts_down = raw_output_down[:,0]  # Raw counts at each sample voltage
                num_cycles_down = raw_output_down[:,1]  # Number of cycles at each sample voltage
                pre_binned_raw_counts_down = raw_counts_down.reshape(self.n_pixels_down, self.n_subpixels)
                binned_raw_counts_down = np.sum(pre_binned_raw_counts_down, axis=1)
                counts_per_second_down = binned_raw_counts_down / self.pixel_time_down

                # Probably want to write some of the local variables to the PleScanner instance for debug

                # Concatenate the result
                output[reader] = np.concatenate([counts_per_second_up, counts_per_second_down])

        if self.stop_scan:
            logger.info('Scan stop acknowledged. Exiting thread.')
            self.stop()

        return output

    def repump(self):
        '''
        Basic implementation of a repump pulse using the analog voltage output
        of nidaq to switch a laser through an AOM.

        Current implementation expects an entry in the `self.auxiliary_controllers`
        dictionary with key 'repump' that is of class 
        `qt3ple.nidaq.customcontrollers.ArbitraryDAQVoltageController`

        The `min_voltage` and `max_voltage` attributes define the off/on voltages
        of the repump laser respectively. Polarity can be swapped by modifying 
        the code directly. Timing is controlled by the imprecise time module.

        Generic modifications to the PLE code should implement functions of this
        type with reference to specific entries in the `auxiliary_controllers` dict.
        '''
        # Get the repump controller
        repump_controller = self.auxiliary_controllers['RepumpController']
        # Log repump
        logger.info(f'Repump for {self.time_repump} ms')
        # Turn on the pump laser
        repump_controller.go_to_voltage(voltage=repump_controller.max_voltage)
        # Wait for repump time
        time.sleep(self.time_repump * 0.001)
        # Turn off the pump laser
        repump_controller.go_to_voltage(voltage=repump_controller.min_voltage)


    def __del__(self):
        '''
        This function is called by Python when the application_controller instance
        is terminated by the automatic garbage collection.
        It logs these events for debug purposes in the event that multiple controller
        instances are used simultaneously.
        '''
        logger.debug('Terminating application_controller instance.')