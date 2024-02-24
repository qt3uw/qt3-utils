import tkinter as Tk
import numpy as np
from typing import Tuple, Optional, Protocol, runtime_checkable
from matplotlib.backend_bases import MouseEvent


@runtime_checkable
class QT3ScanPositionControllerInterface(Protocol):

    def __init__(self, logger_level: int):
        pass

    @property
    def maximum_allowed_position(self) -> float:
        """Abstract property: maximum_allowed_position"""
        pass

    @property
    def minimum_allowed_position(self) -> float:
        """Abstract property: minimum_allowed_position"""
        pass

    def go_to_position(self,
                       x: Optional[float] = None,
                       y: Optional[float] = None,
                       z: Optional[float] = None) -> None:
        """
        This method is used to move the stage or objective to a position.
        """
        pass

    def get_current_position(self) -> Tuple[float, float, float]:
        """
        This method is used to get the current position of the stage or objective.
        """
        pass

    def check_allowed_position(self,
                               x: Optional[float] = None,
                               y: Optional[float] = None,
                               z: Optional[float] = None) -> None:
        """
        This method checks if the position is within the allowed range.

        If the position is not within the allowed range, a ValueError should be raised.
        """
        pass

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the controller.
        """
        pass

    def configure_view(self, gui_root: Tk.Toplevel) -> None:
        """
        This method should launch a GUI window to configure the controller.
        """
        pass


@runtime_checkable
class QT3ScanDAQControllerInterface(Protocol):

    def __init__(self, logger_level: int):
        pass

    @property
    def clock_rate(self) -> float:
        pass

    def start(self) -> None:
        """
        Implementations should do necessary steps to prepare DAQ hardware to acquire data.
        """
        pass

    def stop(self) -> None:
        """
        Implementations should do necessary steps to stop acquiring data.
        """
        pass

    def close(self) -> None:
        """
        Implementations should do necessary steps to close the DAQ
        """
        pass

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the controller.
        """
        pass

    def configure_view(self, gui_root: Tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the controller.
        """
        pass


@runtime_checkable
class QT3ScanCounterDAQControllerInterface(QT3ScanDAQControllerInterface, Protocol):
    """
    Extends the base DAQ Controller interface to require two functions
    to return single measured counts and count rates.
    """

    def sample_counts(self, num_batches: int) -> np.ndarray:
        """
        Implementations should return a new data set on each call to this method.

        Implementations should return a numpy array of shape (1,2)

        The first element of the array should be the total number of counts
        The second element of the array should be the total number of clock ticks.
        For example, see daqsamplers.RateCounterBase.sample_counts(), which
        returns a numpy array of shape (1,2) when sum_counts = True.
        """
        pass

    def sample_count_rate(self, data_counts: np.ndarray) -> np.floating:
        """
        Implementations should return a numpy floating point number

        The returned value should be the count rate in counts per second.
        The input of data_counts should be of shape (1, 2) where the first
        element is the number of counts, the second element is the number of clock ticks.
        Using the clock_rate, this method should compute the count rate, which is
        counts / (clock_ticks / clock_rate).
        """
        pass


@runtime_checkable
class QT3ScanSpectrometerDAQControllerInterface(QT3ScanDAQControllerInterface, Protocol):
    """
    Extends the base DAQ Controller interface to require a functions to return a measured spectrum.
    """

    def sample_spectrum(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns a list of two numpy arrays. The first array contains
        the photon counts for each wavelength bin in the spectrum.
        The second array contains the list of wavelength bin center values.
        """
        pass


@runtime_checkable
class QT3ScanApplicationControllerInterface(Protocol):

    def __init__(self,
                 position_controller: QT3ScanPositionControllerInterface,
                 daq_controller: QT3ScanDAQControllerInterface,
                 logger_level) -> None:
        pass

    # TODO -- should step size be a property of the position controller?
    @property
    def step_size(self) -> float:
        pass

    @step_size.setter
    def step_size(self, value: float):
        pass

    @property
    def scanned_count_rate(self) -> np.ndarray:
        """
        This property should return a 2D numpy array of the count rate at each position in the scan.
        The shape of the array should be (num_y_positions, num_x_positions)

        It can also return a list or array-like object of length zero (len(scanned_count_tate) == 0)
        to indicate no data.
        """
        pass

    @property
    def scanned_raw_counts(self) -> np.ndarray:
        """
        This property should return a 2D numpy array of the total number of counts at each position in the scan.
        The shape of the array should be (num_y_positions, num_x_positions)

        It can also return a list or array-like object of length zero (len(scanned_count_tate) == 0)
        to indicate no data.
        """
        pass

    @property
    def position_controller(self) -> QT3ScanPositionControllerInterface:
        pass

    @property
    def daq_controller(self) -> QT3ScanDAQControllerInterface:
        pass

    @property
    def xmin(self) -> float:
        """
        This property should return the minimum x position of the scan
        """
        pass

    @property
    def xmax(self) -> float:
        """
        This property should return the maximum x position of the scan
        """
        pass

    @property
    def ymin(self) -> float:
        """
        This property should return the minimum y position of the scan
        """
        pass

    @property
    def ymax(self) -> float:
        """
        This property should return the maximum y position of the scan
        """
        pass

    @property
    def current_y(self) -> float:
        """
        This property should return the current y position of the scan
        """
        pass

    def start(self) -> None:
        """
        This method is used to start the scan over the scan range. It should prepare the hardware to
        begin acquistion of data.

        TODO: Consider renaming this to 'prepare_for_start'
        """
        pass

    def stop(self) -> None:
        """
        This method is used to stop the scan. It should stop the hardware from acquiring data.

        TODO: Consider renaming this to 'stop_and_cleanup'
        """
        pass

    def reset(self) -> None:
        """
        This method is used to reset any internal state of the scan,
        such as the current position, data arrays, hardware conditions, etc.
        """
        pass

    def set_to_starting_position(self) -> None:
        """
        This method is used to set the stage or objective to the starting position of the scan.
        """
        pass

    def still_scanning(self) -> bool:
        """
        This method is used to determine if the scan is still running.
        """
        pass

    def scan_x(self) -> None:
        """
        This method is used to scan along the x axis.

        Scans are performed along the x-axis first at each y position before moving to the next y position.
        The implmementation of this method should take and store data at each x position in range. The
        implementation is responsible for moving the stage or objective to each x position in range.
        """
        pass

    def move_y(self) -> None:
        """
        This method is used to move the stage or objective along the y axis.
        """
        pass

    def optimize_position(self, axis: str,
                          central: float,
                          range: float,
                          step_size: float) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        """
        This method is used to optimize the position of the stage or objective.
        Input axis is a string that is either 'x' or 'y' or 'z'
        Input central is a float that is the central position to scan around
        Input range is a float that is the range to scan around the central position
        Input step_size is a float that is the step size to use for the scan

        The returned tuple elements should be:
        0th: np.ndarray of count rates across the axis
        1st: np.ndarray of axix positions (same length as 0, example: 31.5, 32, 32.5, ... 38.5, 39 )
        2nd: float of the position of the maximum count rate
        3rd: np.ndarray of the fit coefficients (C, mu, sigma, offset) that describe the best-fit gaussian shape to the raw_data
        """
        pass

    def set_scan_range(self, xmin: float, xmax: float, ymin: float, ymax: float) -> None:
        '''
        This method is used to set the scan range and is called in qt3scan.main
        '''
        pass

    def save_scan(self) -> None:
        """
        This method is used to save the scan data. An implementation could save the
        data in any way that is seen fit. This method is called by the "save" button.
        The current expectation is that a GUI window is launched allowing the user
        to save the data in the supported format of their choice. The implementation
        of this methdo should also package the data. There are alternatives, of course.
        For example, the implementation could set up a database connection for
        data to be saved in a continuous way.
        """
        pass

    def allowed_file_save_formats(self) -> list:
        '''
        Returns a list of tuples of the allowed file save formats
            [(description, file_extension), ...]
        '''
        pass

    def default_file_format(self) -> str:
        '''
        Returns the default file format
        '''
        pass

    def scan_image_rightclick_event(self, event: MouseEvent, index_x: int, index_y: int) -> None:
        """
        This method is called when the user right clicks on the scan image.
        """
        pass
