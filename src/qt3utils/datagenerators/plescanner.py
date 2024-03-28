import logging
import time
import tkinter as tk
from typing import Type

import numpy as np

from qt3utils.applications.controllers.nidaqedgecounter import QT3ScanNIDAQEdgeCounterController
from qt3utils.applications.controllers.wavemeter_controller import WavemeterController
from qt3utils.applications.controllers.lockin_controller import Lockin
from qt3utils.nidaq.customcontrollers import WavelengthControlBase, VControl

logger = logging.getLogger(__name__)

class PleScanner:
    """
    Base class with function methods which any PLE experiment will need to operate
    Override this class for specific types of PLE experiments
    """

    def __init__(self, readers: dict, wavelength_controller: WavelengthControlBase) -> None:
        """
        self.running: boolean true when scan thread is running
        self.current_frame: current pixel (or time) number in sweep
        self._start: minimum allowed point for hardware controlling the laser wavelength
        self._end: maximum allowed point for hardware controlling the laser wavelength
        self.tmax: maximum number of pixels (or time) for sweep
        self._step_size: size between steps controlling wavelength as it is swept
        self.wavelength_controller: the wavelength controller class instance
        """
        self.running = False
        self.current_frame = 0
        self._start = float(wavelength_controller.minimum_allowed_position)
        self._end= float(wavelength_controller.maximum_allowed_position)
        self.tmax = None
        self._step_size = None
        self.wavelength_controller = wavelength_controller
        self.readers = readers
        self.outputs = []
        self.rate_counters = []
        self.scanned_control = []
        self.scan_mode = ""
        self._discrete_batch_size = 1
        if isinstance(self.wavelength_controller, VControl):
            self.axis_name = "Voltage"
        else:
            self.axis_name = "Wavelength"

    def stop(self) -> None:
        """
        stop running scan
        """
        self.running = False
        for rate_counter in self.rate_counters:
            rate_counter.stop()

    def start(self) -> None:
        """
        start running scan
        """
        self.running = True
        for rate_counter in self.rate_counters:
            rate_counter.start()

    def set_to_start(self) -> None:
        """
        Set the wavelength control to the original start value
        Does nothing if the wavelength controller is not initialized.
        """
        self.current_wl_point = self._start
        if self.wavelength_controller:
            self.go_to(wl_point=self._start)

    def close(self) -> None:
        """
        close connection to daq.
        """
        pass

    def set_scan_range(self, _start: float, _end: float) -> None:
        """
        Set the wavelength controller's minimum and maximum for the PLE scan
        """
        if self.wavelength_controller:
            self.wavelength_controller.check_allowed_limits(_start)
            self.wavelength_controller.check_allowed_limits(_end)
        self._start = _start
        self._end = _end

    def get_scan_range(self) -> tuple[float, float]:
        """
        Returns a tuple of the full scan range
        :return: _start, _end
        """
        return self._start, self._end,

    def get_completed_scan_range(self) -> tuple[float, float, float]:
        """
        Returns a tuple of the scan range that has been completed
        :return: starting and ending points of wavelength contrl, as well as current point in run
        """
        return self._start, self._end, self.current_wl_point

    def still_scanning(self) -> bool:
        """
        Return boolean to determine of the scan should continue
        returning True means the scan should continue
        returning False means the scan should stop
        """
        if self.running == False:  # this allows external process to stop scan
            return False

        if self.current_frame < self.tmax:  # stops scan when reaches final position
            return True
        else:
            self.running = False
            return False

    def increment_wl(self) -> None:
        """
        Move the wavelength control one _step_size towards maximum
        """
        self.current_wl_point += self._step_size
        if self.wavelength_controller and self.current_wl_point <= self._end:
            try:
                self.wavelength_controller.go_to(wl_point=self.current_wl_point)
            except ValueError as e:
                logger.info(f'out of range\n\n{e}')

    def go_to(self, wl_point: float) -> None:
        """
        Set the wavelength controller to desired point
        """
        if self.wavelength_controller and wl_point <= self._end and wl_point >= self._start:
            try:
                self.wavelength_controller.go_to(wl_point=wl_point)
            except ValueError as e:
                logger.info(f'out of range\n\n{e}')

    def scan_wavelengths(self) -> None:
        """
        Scans the wavelengths from v_start to v_end in steps of step_size.
        Records the output from the readers into a list of dictionaries
        """
        self.outputs.append(self.scan_axis(self.axis_name, self._start, self._end, self._step_size))
        self.current_frame = self.current_frame + 1

    def scan_axis(self, axis: str, min: float, max: float, step_size: float) -> list:
        """
        Moves the wavelength controller from min to max in steps of step_size.
        Returns data in the form of a dictionary with
            keys = name of reader defined in YAML file
            values = output of scan
        As well as an array of the points associated with the scan
        If scan_mode is Discrete, each point will represent average values of batch between points instead
        """
        output = {key: [] for key in self.readers.keys()}
        scanned_control = []
        self.set_to_start()
        val_array = np.arange(min, max + step_size, step_size)
        for ii, val in enumerate(val_array):
            if self.scan_mode == "Discrete":
                batch_vals = [val]
            elif self.scan_mode == "Batches":
                self.wavelength_controller.speed = "fast"
                time.sleep(self.wavelength_controller.settling_time_in_seconds)
                if ii < len(val_array)-1:
                    batch_vals = np.arange(val, val_array[ii+1])
                else:
                    continue
            for batch_val in batch_vals:
                logger.info(f'go to {axis}: {val:.2f}')
                self.go_to(wl_point=batch_val)
                scanned_control.append(self.wavelength_controller.get_current_wl_point())
                batch_output = {key: [] for key in self.readers.keys()}
                for reader in self.readers:
                    if isinstance(self.readers[reader], QT3ScanNIDAQEdgeCounterController ):
                        self.rate_counters.append(self.readers[reader])
                        raw_counts = []
                        _raw_counts = self.sample_counts(self.readers[reader])
                        raw_counts.append(_raw_counts)
                        logger.info(f'raw counts, total clock samples: {_raw_counts}')
                        if self.wavelength_controller:
                            logger.info(f'current {self.axis_name}: {self.wavelength_controller.get_current_wl_point()}')
                        raw_counts.append(_raw_counts)
                        batch_output[reader].append(self.sample_count_rate(raw_counts))
                    if isinstance(self.readers[reader], WavemeterController):
                        _wm_reading = self.read_wavemeter(self.readers[reader])
                        batch_output[reader].append(_wm_reading)
                        if self.wavelength_controller:
                            logger.info(f'current {self.axis_name}: {self.wavelength_controller.get_current_wl_point()}')
                    if isinstance(self.readers[reader], VControl):
                        v_reading = self.readers[reader].get_current_wl_point()
                        batch_output[reader].append(v_reading)
                    if isinstance(self.readers[reader], Lockin):
                        signal_reading = self.readers[reader].read()
                        batch_output[reader].append(signal_reading)
            for reader in self.readers:
                reader_batch = np.array(batch_output[reader])
                if len(reader_batch.shape) == 1:
                    output[reader].append(np.mean(batch_output[reader]))
                else:
                    output[reader].append(batch_output[reader][-1])
        self.scanned_control.append(scanned_control)
        return output

    def sample_counts(self, reader) -> np.ndarray:
        """
        Get the counts for a batch by sampling the counts from the rate_counter class
        """
        return reader.sample_counts(reader.num_data_samples_per_batch)

    def reset(self) -> None:
        """
        Reset all data from scans
        """
        pass

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the controller.
        """
        pass

    def sample_count_rate(self, rate_counter, data_counts=None) -> np.floating:
        """
        Sum the counts in a batch
        """
        if data_counts is None:
            data_counts = self.sample_counts()
        return rate_counter.sample_count_rate(data_counts)

    def read_wavemeter(self, wm_reader) -> float:
        """
        Returns the reading from the wavemeter
        """
        return wm_reader.read()

    def set_scan_mode(self, scan_mode: str) ->None:
        self.scan_mode = scan_mode

    @property
    def discrete_batch_size(self):
        return self._discrete_batch_size
    @discrete_batch_size.setter
    def discrete_batch_size(self, batch_size: int) -> None:
        self._discrete_batch_size = batch_size

    @property
    def step_size(self):
        return self._step_size

    @step_size.setter
    def step_size(self, value: float):
        self._step_size = value

    @property
    def get_start(self):
        return self._start

    @property
    def get_end(self):
        return self._end



