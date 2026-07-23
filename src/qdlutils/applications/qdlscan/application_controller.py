import logging
import time

import numpy as np

from qdlutils.hardware.nidaq.counters.nidaqtimedratecounter import NidaqTimedRateCounter
from qdlutils.hardware.nidaq.analogoutputs.nidaqposition import NidaqPositionController

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ScanController:
    '''
    This is the main class which coordinates the scaning and collection of data.
    '''

    def __init__(self,
                 x_axis_controller: NidaqPositionController,
                 y_axis_controller: NidaqPositionController,
                 z_axis_controller: NidaqPositionController,
                 counter_controller: NidaqTimedRateCounter,
                 inter_scan_settle_time: float=0.01):

        self.x_axis_controller = x_axis_controller
        self.y_axis_controller = y_axis_controller
        self.z_axis_controller = z_axis_controller
        self.counter_controller = counter_controller
        self.inter_scan_settle_time = inter_scan_settle_time

        # On initialization move all position controllers to zero.
        # WARNING: it is assumed that the zero is a valid position of the DAQ
        try:
            # Set the positions to zero on start up, this is necessary as it establishes
            # a `last_write_value` for the controllers so that the position is defined.
            self._set_axis(axis_controller=self.x_axis_controller, position=0)
            self._set_axis(axis_controller=self.y_axis_controller, position=0)
            self._set_axis(axis_controller=self.z_axis_controller, position=0)
        except Exception as e:
            logger.warning(f'Could not zero axes on startup: {e}')


        # This is a flag to keep track of if the controller is currently busy
        # Must turn on whenever a scan is being performed and remain on until
        # the scanner is free to perform another operation.
        # The external applications are required to flag this when in use.
        self.busy = False
        
        # This is a flag to keep track of if a scan is currently in progress
        # Must turn on whenever a scan is actively running (via the class
        # method `self.scan_axis()`).
        # Use this flag to tell the controller to stop in the middle of a scan
        self.scanning = False

        # This is a flag set by external applications to request the application
        # controller to stop scanning.
        self.stop_scan = False

    def get_position(self):
        '''
        Returns the position based off of the last write values of the controllers
        '''
        x = self.x_axis_controller.last_write_value
        y = self.y_axis_controller.last_write_value
        z = self.z_axis_controller.last_write_value
        return x,y,z

    def set_axis(self, axis: str, position: float):
        '''
        Outward facing method for moving the position of an axis specified
        by a string `axis`.
        '''
        # Block action if busy
        if self.busy:
            raise RuntimeError('Application controller is currently in use.')
        # Reserve the controller
        self.busy = True

        # Get the axis controller depending on which axis is requested
        if axis == 'x':
            axis_controller = self.x_axis_controller
        elif axis == 'y':
            axis_controller = self.y_axis_controller
        elif axis == 'z':
            axis_controller = self.z_axis_controller
        else:
            raise ValueError(f'Requested axis {axis} is invalid.')
        
        # Call the internal movement function
        try:
            self._set_axis(axis_controller=axis_controller, position=position)
        except Exception as e:
            logger.warning(f'Movement of axis {axis} failed due to exception: {e}')
        # Free up the controller
        self.busy = False

    def _set_axis(self, axis_controller: NidaqPositionController, position: float):
        '''
        Internal function for moving the axis controlled by the given controller.
        This avoids logic required to determine which axis is to be moved, for example
        in the case of scans where only one axis is used repeatedly.
        '''
        logger.debug(f'Attempting to move to position {position}.')
        # Move the axis 
        axis_controller.go_to_position(position=position)
    
    def scan_axis(self, 
                  axis: str,
                  start: float,
                  stop: float,
                  n_pixels: int,
                  scan_time: float):
        '''
        Outward facing scan function.
        Scans the designated axis between the `start` and `stop` positions in 
        `n_pixels` over `scan_time` seconds. Returns the counts at each pixel
        not normalized to time.
        '''
        # Block action if busy
        if self.busy:
            raise RuntimeError('Application controller is currently in use.')
        # Block the controller from additional external commands
        self.busy=True

        # MIRROR STATE PRESERVATION: Save current digital output states BEFORE counter starts
        mirror_states = self._save_mirror_states()

        # Start the counter (this resets the DAQ and digital outputs)
        logger.info('Starting counter task on DAQ.')
        self.counter_controller.start()

        # MIRROR STATE PRESERVATION: Restore mirror states AFTER counter initialization
        if mirror_states is not None:
            self._restore_mirror_states(mirror_states)
            time.sleep(0.1)  # Give DAQ time to settle

        # Get the axis controller depending on which axis is requested
        if axis == 'x':
            axis_controller = self.x_axis_controller
        elif axis == 'y':
            axis_controller = self.y_axis_controller
        elif axis == 'z':
            axis_controller = self.z_axis_controller
        else:
            raise ValueError(f'Requested axis {axis} is invalid.')

        # Go to start position
        self._set_axis(axis_controller=axis_controller, position=start)
        # Let the axis settle before next scan
        time.sleep(self.inter_scan_settle_time)

        data = self._scan_axis(axis_controller=axis_controller,
                               start=start,
                               stop=stop,
                               n_pixels=n_pixels,
                               scan_time=scan_time)

        # Free up the controller
        self.stop()
        return data

    def _scan_axis(self,
                   axis_controller: str,
                   start: float,
                   stop: float,
                   n_pixels: int,
                   scan_time: float):
        '''
        Internal scanning function
        '''
        # Set the scanning flag
        self.scanning = True

        # Calculate the time per pixel
        sample_time = scan_time / n_pixels
        # Configure the counter controller
        self.counter_controller.configure_sample_time(sample_time=sample_time)

        # Generate the positions to scan according to the usual 
        # numpy.linspace implementation.
        # Note that this means that `stop` > `start` is technically valid and
        # will scan from large to small, however the output datastream will be
        # ordered accordingly and thus resulting images might be flipped.
        # It is on the calling functions to manage these nuances.
        positions = np.linspace(start=start, stop=stop, num=n_pixels)

        # Create a buffer for the data
        output = np.zeros(shape=n_pixels)

        # Then iterate through the positions
        for index, position in enumerate(positions):
            # Move to the desired position
            self._set_axis(axis_controller=axis_controller, position=position)
            # Get the counts
            counts = self.counter_controller.sample_batch_counts()
            # Store in the buffer
            output[index] = counts

        # Set the scanning flag
        self.scanning = False

        # Return the buffered output
        return output

    def _save_mirror_states(self):
        '''
        Save the current state of the mirror digital output lines before DAQ reinit.
        Returns a list of boolean states (True=high/up, False=low/down) or None if read fails.
        '''
        try:
            import nidaqmx
            # Create a temporary read task for the mirror lines
            task = nidaqmx.Task()
            task.di_channels.add_di_chan("Dev1/port1/line2:5")
            states = task.read(number_of_samples_per_channel=1)
            task.close()
            # Flatten and return
            if states:
                logger.info(f'Saved mirror states: {states[0]}')
                return list(states[0])
            return None
        except Exception as e:
            logger.warning(f'Could not save mirror states: {e}')
            return None

    def _restore_mirror_states(self, states):
        '''
        Restore mirror digital output states after DAQ reinit.
        '''
        try:
            import nidaqmx
            if not states or len(states) != 4:
                logger.warning('Invalid mirror states to restore')
                return
            # Create a temporary write task for the mirror lines
            task = nidaqmx.Task()
            task.do_channels.add_do_chan("Dev1/port1/line2:5")
            task.write(states, auto_start=True)
            task.close()
            logger.info(f'Restored mirror states: {states}')
        except Exception as e:
            logger.warning(f'Could not restore mirror states: {e}')

    def scan_image(self,
                   axis_1: str,
                   start_1: float,
                   stop_1: float,
                   n_pixels_1: int,
                   axis_2: str,
                   start_2: float,
                   stop_2: float,
                   n_pixels_2: int,
                   scan_time: float):
        '''
        This is an experimental implementation of the scanning function using the 
        `yield` keyword in Python. The method implements a generator which can be
        queried like

            >>> for line in scan_image(**kwargs): # do stuff with line

        where each line is one scan along the `axis_1` defined by the start, stop,
        and number of pixels. For each line the `axis_2` is moved to the next
        pixels also defined by its start, stop, and step size. The speed of a scan
        over each axis is determined by the scan time.
        '''

        # Block action if busy
        if self.busy:
            raise RuntimeError('Application controller is currently in use.')
        # Reserve the controller
        self.busy = True
        

        # Get the axis controller depending on which axis is requested
        if axis_1 == 'x':
            axis_controller_1 = self.x_axis_controller
        elif axis_1 == 'y':
            axis_controller_1 = self.y_axis_controller
        elif axis_1 == 'z':
            axis_controller_1 = self.z_axis_controller
        else:
            raise ValueError(f'Requested axis_1 {axis_1} is invalid.')
        # Get the axis controller depending on which axis is requested
        if axis_2 == 'x':
            axis_controller_2 = self.x_axis_controller
        elif axis_2 == 'y':
            axis_controller_2 = self.y_axis_controller
        elif axis_2 == 'z':
            axis_controller_2 = self.z_axis_controller
        else:
            raise ValueError(f'Requested axis_2 {axis_2} is invalid.')
        
        # Start the counter
        logger.info('Starting counter task on DAQ.')
        self.counter_controller.start()

        # Get the positions for the slow scan axis
        positions_2 = np.linspace(start=start_2, stop=stop_2, num=n_pixels_2)

        # Then iterate through the positions
        for index, position in enumerate(positions_2):
            # Move axis 2 to the desired position
            self._set_axis(axis_controller=axis_controller_2, position=position)
            # Let the axis settle before next scan
            time.sleep(self.inter_scan_settle_time)
            # Scan axis 1
            single_scan =  self._scan_axis(axis_controller=axis_controller_1,
                                           start=start_1,
                                           stop=stop_1,
                                           n_pixels=n_pixels_1, 
                                           scan_time=scan_time)
            # Update the buffer
            #output[index] = single_scan

            # Set back to original position on fast scan axis
            #self._set_axis(axis_controller=axis_controller_1, position=start_1)
            # Slow scan back to start for smooth scanning?
            self._scan_axis(axis_controller=axis_controller_1,
                            start=stop_1,
                            stop=start_1,
                            n_pixels=n_pixels_1, 
                            scan_time=self.inter_scan_settle_time)

            # Yield a single scan
            yield single_scan

            # If the stop is requested then terminate and return the final scan
            if self.stop_scan:
                logger.info('Stopping scan.')
                self.stop()
                return single_scan
            
        logger.info('Scan complete.')
        self.stop()

    def stop(self) -> None:
        '''
        Stop running scan
        '''
        self.scanning = False
        # Stop the DAQ
        self.counter_controller.stop()
        logger.info(f'Stopping counter task on DAQ.')
        # Free up the controller
        self.busy = False
        # Reset the stop scan flag
        self.stop_scan = False