import tkinter as Tk
import numpy as np
from typing import Tuple, Optional, Protocol, runtime_checkable


@runtime_checkable
class QT3ScanPositionControllerInterface(Protocol):

    def __init__(self, logger_level):
        pass

    @property
    def maximum_allowed_position(self):
        """Abstract property: maximum_allowed_position"""
        pass

    @property
    def minimum_allowed_position(self):
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

    def configure(self, config_dict: dict):
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
class QT3ScanDAQControllerInterface(Protocol):

    def __init__(self, logger_level):
        pass

    @property
    def clock_rate(self) -> float:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass

    def sample_counts(self, num_batches: int) -> np.ndarray:
        pass

    def sample_count_rate(self, data_counts: np.ndarray) -> np.ndarray:
        pass

    @property
    def num_data_samples_per_batch(self) -> int:
        pass

    @num_data_samples_per_batch.setter
    def num_data_samples_per_batch(self, value):
        """Abstract property setter for num_data_samples_per_batch"""
        pass

    def configure(self, config_dict: dict):
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
class QT3ScanApplicationControllerInterface(Protocol):

    def __init__(self,
                 position_controller: QT3ScanPositionControllerInterface,
                 daq_controller: QT3ScanDAQControllerInterface,
                 logger_level) -> None:
        pass

    @property
    def step_size(self) -> float:
        pass

    @step_size.setter
    def step_size(self, value):
        """Abstract property setter for num_data_samples_per_batch"""
        pass

    ## TODO -- scanned_count_rate and scanned_raw_counts might not be the best names for these properties
    # these are the 2D data representation of the scan -- for confocal scans, each pixel is
    # simply the number of counts. for hyperspectral, the pixel is the counts summed across the spectrum
    @property
    def scanned_count_rate(self) -> np.ndarray:
        pass

    @property
    def scanned_raw_counts(self) -> np.ndarray:
        pass

    @property
    def position_controller(self) -> QT3ScanPositionControllerInterface:
        pass

    @property
    def daq_controller(self) -> QT3ScanDAQControllerInterface:
        pass

    @property
    def xmin(self) -> float:
        pass

    @property
    def xmax(self) -> float:
        pass

    @property
    def ymin(self) -> float:
        pass

    @property
    def ymax(self) -> float:
        pass

    @property
    def current_y(self) -> float:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def reset(self) -> None:
        pass

    def set_to_starting_position(self) -> None:
        pass

    def still_scanning(self) -> bool:
        pass

    def scan_x(self) -> None:
        pass

    def move_y(self) -> None:
        pass

    def optimize_position(self, axis, central, range, step_size) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        """
        The returned tuple elements should be:
        0th: np.ndarray of count rates across the axis
        1st: np.ndarray of axix positions (same length as 0, example: 31.5, 32, 32.5, ... 38.5, 39 )
        2nd: float of the position of the maximum count rate
        3rd: np.ndarray of the fit coefficients (C, mu, sigma, offset) that describe the best-fit gaussian shape to the raw_data
        """
        pass

    def set_scan_range(self, xmin, xmax, ymin, ymax) -> None:
        pass

    # TODO -- should this be part of daq controler?? I think yes.
    def set_num_data_samples_per_batch(self, N: int) -> None:
        pass

    # TODO -- investigate if this is necessary. This function is not used in qt3scan.main
    # but it is used internally in the QT3ScanConfocalApplicationController for saving data
    # TODO -- check all of the other methods in this interface to see if they are necessary at the interface level
    def get_completed_scan_range(self) -> Tuple[float, float, float, float]:
        pass

    def save_scan(self) -> None:
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

    def scan_image_rightclick_event(self, event) -> None:
        """
        This method is called when the user right clicks on the scan image.
        """
        pass
