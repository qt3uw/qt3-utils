import logging
import numpy as np
from typing import Tuple
import h5py
from matplotlib.backend_bases import MouseEvent

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

        # I realize this implementation looks strange since it essentially wraps all the calls
        # to a CounterAndScanner object, except for a few of the methods.
        # The reason for this is that the CounterAndScanner object is designed to be used
        # programatically. It was not designed to be used by a GUI application and I wanted
        # to implement good engineering practices.
        # I considered subclassing the CounterAndScanner object here,
        # but that required work too far outside the scope of the issue where this was developed.
        # Future work could consider that possiblity.
        #
        # However, better organizations of the code are also possible and open to development.
        #
        # Here is one such proposal
        #
        # The proposal would result in two sets of Protocol/Interface classes.  One set would define
        # a programmatic interface (to be used by researchers in Jupyter notebooks and
        # in their own external scripts that depend on qt3utils classes). The second set
        # would define the GUI application interfaces, which we have already
        # done in interface.py.
        #
        # The programmatic interface would define
        #   * PositionControllerInterface
        #   * DAQControllerInterface
        #   * XYMicroscopeScannerInterface (perhaps ConfocalScannerInterface?).
        # Then we would change CounterAndScanner object to
        # be an implementation of XYMicroscopeScannerInterface.
        # We would also then make implemetnations of PositionControllerInterface and
        # DAQControllerInterface using the nipiezojenapy classes and the classes in
        # daqsamplers.py.
        #
        # From that point, we could then see if the GUI interfaces should subclass the
        # programmatic interfaces or remain independent.
        #
        # Additionally, this proposal alo implies a future programmatic interface for the
        # SpectromterController and a GUI interface for the SpectrometerController.

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
    def optimize_position(self, axis: str,
                          central: float,
                          range: float,
                          step_size: float) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        """
        The returned tuple elements should be:
        0th: np.ndarray of count rates across the axis
        1st: np.ndarray of axix positions (same length as 0, example: 31.5, 32, 32.5, ... 38.5, 39 )
        2nd: float of the position of the maximum count rate
        3rd: np.ndarray of the fit coefficients (C, mu, sigma, offset) that describe the best-fit gaussian shape to the raw_data
        """
        return self.daq_and_scanner.optimize_position(axis, central, range, step_size)

    def set_scan_range(self, xmin: float, xmax: float, ymin: float, ymax: float) -> None:
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

    def scan_image_rightclick_event(self, event: MouseEvent) -> None:
        """
        This method is called when the user right clicks on the scan image.
        """
        self.logger.debug(f"scan_image_rightclick_event. click at {event.xdata}, {event.ydata}")

# class QT3ScanHyperSpectralApplicationController:
#     """
#     Implements qt3utils.applications.qt3scan.interface.QT3ScanApplicationControllerInterface
#     """