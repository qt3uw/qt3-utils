import logging
import numpy as np
from typing import Tuple
import h5py

from qt3utils.applications.qt3scan.interface import QT3ScanDAQControllerInterface, QT3ScanPositionControllerInterface
import qt3utils.datagenerators
from qt3utils.errors import convert_nidaq_daqnotfounderror

module_logger = logging.getLogger(__name__)
module_logger.setLevel(logging.ERROR)


class QT3ScanConfocalApplicationController:
    """
    Implements qt3utils.applications.qt3scan.interface.QT3ScanApplicationControllerInterface
    """
    def __init__(self,
                 position_controller: QT3ScanPositionControllerInterface,
                 daq_controller: QT3ScanDAQControllerInterface,
                 logger_level) -> None:

        # Relize this looks strange and like a bunch of redundant code. 
        # This essentially wraps all the calls to a CounterAndScanner object. 
        # I considered to simply re-use CounterAndScanner object in qt3utils.main. But 
        # decided to aim toward good engineering practices and define an interface for the GUI application
        # to support potential future changes. 
        # Als considered to subclass CounterAndScanner. But CounterAndScanner would need to change
        # all of its private variables to _private variables. Additionally, the daq_controller
        # and position_controller objects would need to be redesigned as well.

        # Ideally, two sets of Protocol/Interface classes could be defined. 
        # One set would define programmatic interface and
        # the other set would define the GUI application interfaces
        # The programmatic interface would define a PositionControllerInterface, DAQControllerInterface and 
        # MicroscopeScannerInterface interface (ConfocalScannerInterface?).
        # Then would change CounterAndScanner object to
        # be an implementation of MicroscopeScannerInterface.
        # Would also then make implemetnations of PositionControllerInterface and
        # DAQControllerInterface using the nipiezojenapy classes and the classes in
        # daqsamplers.py.
        # However this would woudl be outside the current scope of this branch/issue
        # being developed. We are limiting the scope of this branch to just the GUI application
        # and not the underlying API. So for now, we are just wrapping the CounterAndScanner
        # Future work on qt3utils may include the above mentioned changes.
        # Also complicating the issue is that qt3utils relies heavily on nipiezojenapy
        # It's probably better to move nipiezojenapy into qt3utils.

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.daq_and_scanner = qt3utils.datagenerators.CounterAndScanner(daq_controller, position_controller)
        self.last_config_dict = {}

    @property
    def step_size(self) -> float:
        return self.daq_and_scanner.step_size

    @step_size.setter
    def step_size(self, value):
        self.daq_and_scanner.step_size = value

    @property
    def scanned_count_rate(self) -> np.ndarray:
        return self.daq_and_scanner.scanned_count_rate

    @property
    def scanned_raw_counts(self) -> np.ndarray:
        return self.daq_and_scanner.scanned_raw_counts

    @property
    def position_controller(self) -> QT3ScanPositionControllerInterface:
        return self.daq_and_scanner.stage_controller

    @property
    def daq_controller(self) -> QT3ScanDAQControllerInterface:
        return self.daq_and_scanner.rate_counter

    @property
    def xmin(self) -> float:
        return self.daq_and_scanner.xmin

    @property
    def xmax(self) -> float:
        return self.daq_and_scanner.xmax

    @property
    def ymin(self) -> float:
        return self.daq_and_scanner.ymin

    @property
    def ymax(self) -> float:
        return self.daq_and_scanner.ymax

    @property
    def current_y(self) -> float:
        return self.daq_and_scanner.current_y

    @convert_nidaq_daqnotfounderror(module_logger)
    def start(self) -> None:
        self.daq_and_scanner.start()

    @convert_nidaq_daqnotfounderror(module_logger)
    def stop(self) -> None:
        self.daq_and_scanner.stop()

    @convert_nidaq_daqnotfounderror(module_logger)
    def reset(self) -> None:
        self.daq_and_scanner.reset()

    @convert_nidaq_daqnotfounderror(module_logger)
    def set_to_starting_position(self) -> None:
        self.daq_and_scanner.set_to_starting_position()

    def still_scanning(self) -> bool:
        return self.daq_and_scanner.still_scanning()

    @convert_nidaq_daqnotfounderror(module_logger)
    def scan_x(self) -> None:
        self.daq_and_scanner.scan_x()

    @convert_nidaq_daqnotfounderror(module_logger)
    def move_y(self) -> None:
        self.daq_and_scanner.move_y()

    @convert_nidaq_daqnotfounderror(module_logger)
    def optimize_position(self, axis, central, range, step_size) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        """
        The returned tuple elements should be:
        0th: np.ndarray of count rates across the axis
        1st: np.ndarray of axix positions (same length as 0, example: 31.5, 32, 32.5, ... 38.5, 39 )
        2nd: float of the position of the maximum count rate
        3rd: np.ndarray of the fit coefficients (C, mu, sigma, offset) that describe the best-fit gaussian shape to the raw_data
        """
        return self.daq_and_scanner.optimize_position(axis, central, range, step_size)

    def set_scan_range(self, xmin, xmax, ymin, ymax) -> None:
        self.daq_and_scanner.set_scan_range(xmin, xmax, ymin, ymax)

    def set_num_data_samples_per_batch(self, N: int) -> None:
        self.daq_and_scanner.set_num_data_samples_per_batch(N)

    def get_completed_scan_range(self) -> Tuple[float, float, float, float]:
        return self.daq_and_scanner.get_completed_scan_range()

    def allowed_file_save_formats(self) -> list:
        '''
        Returns a list of tuples of the allowed file save formats
            [(description, file_extension), ...]
        '''
        formats = [('Compressed Numpy MultiArray', '*.npz'), ('Numpy Array (count rate only)', '*.npy'), ('HDF5', '*.h5')]
        return formats

    def default_file_format(self) -> str:
        '''
        Returns the default file format
        '''
        return '.npz'

    def save_scan(self, afile_name) -> None:

        file_type = afile_name.split('.')[-1]

        data = dict(
                    scan_range=self.get_completed_scan_range(),
                    raw_counts=self.daq_and_scanner.scanned_raw_counts,
                    count_rate=self.daq_and_scanner.scanned_count_rate,
                    step_size=self.daq_and_scanner.step_size,
                    daq_clock_rate=self.daq_controller.clock_rate,
                    )

        if file_type == 'npy':
            np.save(afile_name, data['count_rate'])

        if file_type == 'npz':
            np.savez_compressed(afile_name, **data)

        elif file_type == 'h5':
            h5file = h5py.File(afile_name, 'w')
            for key, value in data.items():
                h5file.create_dataset(key, data=value)
            h5file.close()

    def scan_image_rightclick_event(self, event) -> None:
        """
        This method is called when the user right clicks on the scan image.
        """
        self.logger.debug(f"scan_image_rightclick_event. click at {event.x}, {event.y}")

# class QT3ScanHyperSpectralApplicationController:
#     """
#     Implements qt3utils.applications.qt3scan.interface.QT3ScanApplicationControllerInterface
#     """