import logging
import time
import tkinter as tk
from typing import Type

import numpy as np

from qt3utils.applications.controllers.nidaqedgecounter import QT3ScopeNIDAQEdgeCounterController
from qt3utils.applications.controllers.wavemeter_controller import WavemeterController
from qt3utils.nidaq.customcontrollers import VControl

logger = logging.getLogger(__name__)

class PleScanner:
    """
    Base class with function methods which any PLE experiment will need to operate
    Override this class for specific types of PLE experiments
    """

    def __init__(self, wavelength_controller: Type[VControl]):
        """
        self.running: boolean true when scan thread is running
        self.current_frame: current pixel (or time) number in sweep
        self.v_start: minimum allowed voltage for voltage controlling the laser wavelength
        self.v_end: maximum allowe voltage for voltage controlling the laser wavelength
        self.tmax: maximum number of pixels (or time) for sweep
        self._step_size: size between voltage steps as it is swept
        self.wavelength_controller: the voltage controller class instance
        """
        self.running = False
        self.current_frame = 0
        self.v_start = float(wavelength_controller.minimum_allowed_position)
        self.v_end= float(wavelength_controller.maximum_allowed_position)
        self.tmax = None
        self._step_size = None
        self.wavelength_controller = wavelength_controller

    def stop(self) -> None:
        """
        stop running scan
        """
        self.running = False

    def start(self) -> None:
        """
        start running scan
        """
        self.running = True

    def set_to_starting_voltage(self) -> None:
        """
        Set the voltage to the original voltage start value
        Does nothing if the wavelength controller is not initialized.
        """
        self.current_v = self.v_start
        if self.wavelength_controller:
            self.wavelength_controller.go_to_voltage(v=self.v_start)

    def close(self) -> None:
        """
        close connection to daq.
        """
        pass

    def set_scan_range(self, v_start: float, v_end: float) -> None:
        """
        Set the voltage minimum and maximum for the PLE scan
        """
        if self.wavelength_controller:
            self.wavelength_controller.check_allowed_voltage(v_start)
            self.wavelength_controller.check_allowed_voltage(v_end)
        self.v_start = v_start
        self.v_end = v_end

    def get_scan_range(self) -> tuple[float, float]:
        """
        Returns a tuple of the full scan range
        :return: v_start, v_end
        """
        return self.v_start, self.v_end,

    def get_completed_scan_range(self) -> tuple[float, float, float]:
        """
        Returns a tuple of the scan range that has been completed
        :return: starting voltage, ending voltage, voltage set at daq
        """
        return self.v_start, self.v_end, self.current_v

    def still_scanning(self) -> None:
        """
        Return boolean to determine of the scan should continue
        returning True means the scan should continue
        returning False means the scan should stop
        """
        if self.running == False:  # this allows external process to stop scan
            return False

        if self.current_frame <= self.tmax:  # stops scan when reaches final position
            return True
        else:
            self.running = False
            return False

    def move_v(self) -> None:
        """
        Move the voltage one _step_size from current voltage towards maximum voltage
        """
        self.current_v += self._step_size
        if self.wavelength_controller and self.current_v <= self.v_end:
            try:
                self.wavelength_controller.go_to_position(v=self.current_v)
            except ValueError as e:
                logger.info(f'out of range\n\n{e}')

    def go_to_voltage(self, desired_voltage: float) -> None:
        """
        Set the wavelength controller to set the daq to a desired voltage
        """
        if self.wavelength_controller and desired_voltage <= self.v_end and desired_voltage >= self.v_start:
            try:
                self.wavelength_controller.go_to_voltage(voltage=desired_voltage)
            except ValueError as e:
                logger.info(f'out of range\n\n{e}')

    def scan_voltage(self) -> None:
        """
        Scans the wavelengths from v_start to v_end in steps of step_size.
        """
        pass

    def scan_axis(self, axis: str, min: float, max: float, step_size: float) -> list:
        """
        Moves the voltage from min to max in steps of step_size.
        Returns data
        """
        pass

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

    @property
    def step_size(self):
        return self._step_size

    @step_size.setter
    def step_size(self, value: float):
        self._step_size = value


class CounterAndScanner(PleScanner):
    """
    Inherits from PleScanner base class
    Adds a rate counter for the SPCM and correlates counts with scans
    """
    def __init__(self, rate_counter: Type[QT3ScopeNIDAQEdgeCounterController], wavelength_controller: Type[VControl]) -> None:
        """
        self.scanned_raw_counts: raw counts in scan
        selfscanned_count_rate: counts summed according to number of counts per batch
        self.rate_counter: class instance for counting from the SPCM
        """
        super(CounterAndScanner, self).__init__(wavelength_controller)
        self.scanned_raw_counts = []
        self.scanned_count_rate = []
        self.rate_counter = rate_counter

    def stop(self) -> None:
        """
        stop scan
        """
        super().stop()
        self.rate_counter.stop()

    def start(self) -> None:
        """
        start scan
        """
        super().start()
        self.rate_counter.start()

    def close(self) -> None:
        """
        close connection to daq
        """
        self.rate_counter.close()

    def set_num_data_samples_per_batch(self, N: int) -> None:
        """
        Set the number of data samples per batch
        """
        self.rate_counter.num_data_samples_per_batch = N

    def sample_counts(self) -> np.ndarray:
        """
        Get the counts for a batch by sampling the counts from the rate_counter class
        """
        return self.rate_counter.sample_counts(self.rate_counter.num_data_samples_per_batch)

    def sample_count_rate(self, data_counts=None) -> np.floating:
        """
        Sum the counts in a batch
        """
        if data_counts is None:
            data_counts = self.sample_counts()
        return self.rate_counter.sample_count_rate(data_counts)

    def scan_voltage(self) -> None:
        """
        Scans the wavelengths from v_start to v_end in steps of step_size.

        Stores results in self.scanned_raw_counts and self.scanned_count_rate.
        """
        raw_counts_for_axis = self.scan_axis('voltage', self.v_start, self.v_end, self._step_size)
        self.scanned_raw_counts.append(raw_counts_for_axis)
        self.scanned_count_rate.append([self.sample_count_rate(raw_counts) for raw_counts in raw_counts_for_axis])
        self.current_frame = self.current_frame + 1

    def scan_axis(self, axis, min, max, step_size) -> list:
        """
        Moves the voltage from min to max in steps of step_size.
        Returns a list of raw counts from the scan
        """
        raw_counts = []
        self.wavelength_controller.go_to_voltage(**{axis: min})
        for val in np.arange(min, max, step_size):
            if self.wavelength_controller:
                logger.info(f'go to voltage {axis}: {val:.2f}')
                self.wavelength_controller.go_to_voltage(**{axis: val})
            _raw_counts = self.sample_counts()
            raw_counts.append(_raw_counts)
            logger.info(f'raw counts, total clock samples: {_raw_counts}')
            if self.wavelength_controller:
                logger.info(f'current voltage: {self.wavelength_controller.get_current_voltage()}')

        return raw_counts

    def reset(self) -> None:
        self.scanned_raw_counts = []
        self.scanned_count_rate = []


class WavemeterAndScanner(PleScanner):
    """
    Inherits from PleScanner base class
    Adds a wavemeter and daq readings to the correlated voltage sweeps
    """
    def __init__(self, wm_reader: Type[WavemeterController], v_readers: Type[VControl], wavelength_controller: Type[VControl]):
        """
        self.wm_reader: Wavemeter Controller instance
        self.v_readers: instances of voltage readers from the daq
        self.scanned_count_rate: data from voltage readers per pause per scan
        self.scanned_wm: data from wavemeter per pause per scan
        """
        super(WavemeterAndScanner, self).__init__(wavelength_controller)
        self.wm_reader = wm_reader
        self.v_readers = v_readers
        self.scanned_count_rate = []
        self.scanned_wm = []

    def scan_voltage(self) -> None:
        """
        Scans the wavelengths from v_start to v_end in steps of step_size.
        """
        _wm_scan, _vs_scan = self.scan_axis('v', self.v_start, self.v_end, self._step_size)
        self.scanned_wm.append(_wm_scan)
        self.scanned_count_rate.append(_vs_scan)
        self.current_frame = self.current_frame + 1

    def read_wavemeter(self) -> float:
        """
        Returns the reading from the wavemeter
        """
        return self.wm_reader.read_wavemeter()

    def scan_axis(self, axis: str, min: float, max: float, step_size: float) -> tuple[list[float], list[float]]:
        """
        Moves the voltage from min to max in steps of step_size.
        Returns a list of readings from the wave meter and DAQ for each scan
        """
        wm_scan = []
        vs_scans = {}
        for v_reader in self.v_readers:
            vs_scans[v_reader.read_channel] = []
        self.wavelength_controller.go_to_voltage(**{axis: min})
        for val in np.arange(min, max, step_size):
            if self.wavelength_controller:
                log_sigfig = str(step_size)[::-1].find('.')
                logger.info(f'go to voltage {axis}: {val:.{log_sigfig}f}')
                self.wavelength_controller.go_to_voltage(**{axis: val})
            _wm_reading = self.read_wavemeter()
            wm_scan.append(_wm_reading)
            if self.wavelength_controller:
                logger.info(f'current voltage: {self.wavelength_controller.get_current_voltage()}')
            for v_reader in self.v_readers:
                v_reading = v_reader.get_current_voltage()
                vs_scans[v_reader.read_channel].append(v_reading)
        return wm_scan, vs_scans


def GetApplicationControllerInstance(classtype, readers: dict, controllers: dict):
    """
    Create an instance of the application controller depending on the type
    classtype : class
        - either WavemeterAndScanner or CounterAndScanner
    readers : dict
        - dict of readers this class uses. For WaveMeterAndScanner, wavemeter is first, then DAQs
    controllers : dict
        - dict of controllers this class uses. This will always be a VControl class
    """
    if issubclass(classtype, WavemeterAndScanner):
        return classtype(list(readers.values())[-1], list(readers.values())[0:-1], list(controllers.values())[0])
    elif classtype == CounterAndScanner:
        return classtype(list(readers.values())[0], list(controllers.values())[0])
