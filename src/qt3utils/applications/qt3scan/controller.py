import logging
import numpy as np
from typing import Tuple
import h5py
import pickle
import time
import tkinter as tk

import matplotlib
from matplotlib.backend_bases import MouseEvent
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
matplotlib.use('Agg')

from qt3utils.applications.qt3scan.interface import (
    QT3ScanDAQControllerInterface,
    QT3ScanCounterDAQControllerInterface,
    QT3ScanPositionControllerInterface,
    QT3ScanSpectrometerDAQControllerInterface,
)

import qt3utils.datagenerators
from qt3utils.errors import convert_nidaq_daqnotfounderror, QT3Error

module_logger = logging.getLogger(__name__)
module_logger.setLevel(logging.ERROR)


class QT3ScanConfocalApplicationController:
    """
    Implements qt3utils.applications.qt3scan.interface.QT3ScanApplicationControllerInterface

    Note that the DAQ controller here must implement QT3ScanCounterDAQControllerInterface
    """
    def __init__(self,
                 position_controller: QT3ScanPositionControllerInterface,
                 daq_controller: QT3ScanCounterDAQControllerInterface,
                 logger_level: int) -> None:

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

class QT3ScanHyperSpectralApplicationController:
    """
     Implements qt3utils.applications.qt3scan.interface.QT3ScanApplicationControllerInterface

     For HyperSpectral imaging, the daq_controller object will be a spectrometer that
     acquires a spectrum at each position in the scan.

     Note that the DAQ controller here must implement QT3ScanCounterDAQControllerInterface


     The following methods are required for a daq_controller object that
     are not currently in the QT3ScanDAQControllerInterface.
     We should find a way to declare these methods for any spectrometer
     that is used for hyperspectral imaging. This could be another interface,
     or perhaps using the concept of Python MixIns. To be discussed....

    """
    def __init__(self,
                 position_controller: QT3ScanPositionControllerInterface,
                 daq_controller: QT3ScanSpectrometerDAQControllerInterface,
                 logger_level: int) -> None:

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self._daq_controller = daq_controller
        self._position_controller = position_controller

        self.running = False
        self._current_y = 0
        self._ymin = self.position_controller.minimum_allowed_position
        self._ymax = self.position_controller.maximum_allowed_position
        self._xmin = self.position_controller.minimum_allowed_position
        self._xmax = self.position_controller.maximum_allowed_position

        self._step_size = 0.5
        self.raster_line_pause = 0.150  # wait 150ms for the piezo stage to settle before a line scan

        self.hyper_spectral_raw_data = None  # is there way to create a "default numpy array", similar a 'default dict'??
        self.hyper_spectral_wavelengths = None
    @property
    def step_size(self) -> float:
        return self._step_size

    @step_size.setter
    def step_size(self, value: float):
        self._step_size = value

    @property
    def scanned_count_rate(self) -> np.ndarray:
        return self.scanned_raw_counts * self.daq_controller.clock_rate

    @property
    def scanned_raw_counts(self) -> np.ndarray:
        if self.hyper_spectral_raw_data is not None:
            return np.sum(self.hyper_spectral_raw_data, axis=2)
        else:
            return np.array([])

    @property
    def position_controller(self) -> QT3ScanPositionControllerInterface:
        return self._position_controller

    @property
    def daq_controller(self) -> QT3ScanDAQControllerInterface:
        return self._daq_controller

    @property
    def xmin(self) -> float:
        return self._xmin

    @property
    def xmax(self) -> float:
        return self._xmax

    @property
    def ymin(self) -> float:
        return self._ymin

    @property
    def ymax(self) -> float:
        return self._ymax

    @property
    def current_y(self) -> float:
        return self._current_y

    def start(self) -> None:
        """
        This method is used to start the scan over the scan range. It should prepare the hardware to
        begin acquistion of data.
        """
        self.running = True
        self.daq_controller.start()

    def stop(self) -> None:
        """
        This method is used to stop the scan. It should stop the hardware from acquiring data.
        """
        self.daq_controller.stop()
        self.running = False

    def reset(self) -> None:
        """
        Resets internal data structure. NB: this blows away any previously stored data.

        """
        self.hyper_spectral_raw_data = None
        self.hyper_spectral_wavelengths = None

    def set_to_starting_position(self) -> None:
        self._current_y = self.ymin
        self.position_controller.go_to_position(x = self.xmin, y = self.ymin)

    def still_scanning(self) -> bool:
        if self.running == False: #this allows external process to stop scan
            return False

        if self.current_y < self.ymax: #stops scan when reaches final position
            return True
        else:
            self.running = False
            return False

    def scan_x(self):
        """
        Scans the x axis from xmin to xmax in steps of step_size.

        """
        raw_counts_for_axis, wavelengths = (
            self.scan_axis('x', self.xmin, self.xmax, self.step_size)
        )
        # raw_counts_for_axis is of shape (N steps, M spectrum size)
        # wavelengths is of shape (M spectrum size,)
        assert len(wavelengths) == raw_counts_for_axis.shape[-1]

        # rehape raw_counts to
        # (1, N, M)
        raw_counts_for_axis = raw_counts_for_axis.reshape(1, len(raw_counts_for_axis), -1)

        if self.hyper_spectral_raw_data is None:
            self.hyper_spectral_raw_data = raw_counts_for_axis
            self.logger.debug(f'Creating new hyperspectral array of shape: {self.hyper_spectral_raw_data.shape}')
        else:
            if self.hyper_spectral_raw_data.shape[-1] != raw_counts_for_axis.shape[-1]:
                raise QT3Error("Inconsistent spectrum size obtained during scan_x! Check your hardware."
                               f"expected shape[-1] {self.hyper_spectral_raw_data.shape[-1]}. found {raw_counts_for_axis.shape[-1]}")

            self.hyper_spectral_raw_data = np.vstack((self.hyper_spectral_raw_data, raw_counts_for_axis))

        if self.hyper_spectral_wavelengths is None:
            self.hyper_spectral_wavelengths = wavelengths

        if np.array_equal(self.hyper_spectral_wavelengths, wavelengths) is False:
            raise QT3Error("Inconsistent wavelength array obtained during scan_x! Check your hardware.")

    def scan_axis(self, axis, min, max, step_size) -> Tuple[np.ndarray, np.ndarray]:
        """
        Moves the microscope along the specified axis from min to max in steps of step_size.
        Returns a tuple of two numpy arrays
        The first numpy array is the raw spectrum from the scan in the shape
        (N, M) where N is the number of positions along the axis and M
        is the size of the spectrum
        The second numpy array is an array of wavelength values for the spectrum of shape (M,)
        """
        spectrums_in_scan = []

        # we use these to check the returned spectrum
        # and wavelength array for consistency.
        # we also currently do not support the
        # values of the wavelengths changing for each position
        # that is, the spectrometer must scan over the same set of wavelengths each time.
        wavelength_array = None
        initial_spectrum_size = None

        self.position_controller.go_to_position(**{axis: min})
        time.sleep(self.raster_line_pause)
        for val in np.arange(min, max, step_size):
            self.position_controller.go_to_position(**{axis: val})

            measured_spectrum, measured_wavelengths = self.daq_controller.sample_spectrum()
            spectrums_in_scan.append(measured_spectrum)

            if initial_spectrum_size is None:
                initial_spectrum_size = len(measured_spectrum)
            if wavelength_array is None:
                wavelength_array = measured_wavelengths

            if initial_spectrum_size != len(measured_spectrum):
                raise QT3Error("Inconsistent spectrum size obtained during scan! Check your hardware.")
            if initial_spectrum_size != len(measured_wavelengths):
                raise QT3Error("Inconsistent wavelength array size obtained during scan! Check your hardware.")
            if len(measured_spectrum) != len(measured_wavelengths):
                raise QT3Error("Inconsistent wavelength array and spectrum size obtained during scan! Check your hardware.")
            if np.array_equal(wavelength_array, measured_wavelengths) is False:
                raise QT3Error("Inconsistent wavelength array obtained during scan! Check your hardware.")

        return np.array(spectrums_in_scan), wavelength_array

    def move_y(self) -> None:
        if self.current_y < self.ymax:
            self._current_y += self.step_size
        try:
            self.position_controller.go_to_position(y=self.current_y)
        except ValueError as e:
            self.logger.info(f'move y: out of range\n\n{e}')

    def optimize_position(self, axis: str,
                            central: float,
                            range: float,
                            step_size: float) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        """
        Not Yet Implemented.
        """
        raise NotImplementedError("QT3ScanHyperSpectralApplicationController does not implement optimize_position")

    def set_scan_range(self, xmin: float, xmax: float, ymin: float, ymax: float) -> None:
        '''
        This method is used to set the scan range and is called in qt3scan.main
        '''
        self.position_controller.check_allowed_position(xmin, ymin)
        self.position_controller.check_allowed_position(xmax, ymax)

        self._ymin = ymin
        self._ymax = ymax
        self._xmin = xmin
        self._xmax = xmax

    def get_completed_scan_range(self) -> Tuple[float, float, float, float]:
        """
        Returns a tuple of the scan range that has been completed
        :return: _xmin, _xmax, _ymin, current_y
        """
        return self._xmin, self._xmax, self._ymin, self.current_y

    def save_scan(self, afile_name) -> None:
        file_type = afile_name.split('.')[-1]

        data = dict(
            wavelengths=self.hyper_spectral_wavelengths,
            hyperspectral_image=self.hyper_spectral_raw_data,
            scan_range=self.get_completed_scan_range(),
            raw_counts=self.scanned_raw_counts,
            count_rate=self.scanned_count_rate,
            step_size=self.step_size,
            daq_clock_rate=self.daq_controller.clock_rate
        )

        if file_type == 'npy':
            np.save(afile_name, data['count_rate'])

        elif file_type == 'npz':
            np.savez_compressed(afile_name, **data)

        elif file_type == 'h5':
            with h5py.File(afile_name, 'w') as h5file:
                for key, value in data.items():
                    h5file.create_dataset(key, data=value)

        elif file_type == 'pkl':
            with open(afile_name, 'wb') as f:
                pickle.dump(data, f)

    def allowed_file_save_formats(self) -> list:
        '''
        Returns a list of tuples of the allowed file save formats
            [(description, file_extension), ...]
        '''
        formats = [('Compressed Numpy MultiArray', '*.npz'),
                   ('Numpy Array (count rate only)', '*.npy'),
                   ('HDF5', '*.h5'),
                   ('Pickle', '*.pkl'),
                   ]
        return formats

    def default_file_format(self) -> str:
        '''
        Returns the default file format
        '''
        return '.npz'

    def scan_image_rightclick_event(self, event: MouseEvent) -> None:
        """
        This method is called when the user right clicks on the scan image.
        """
        self.logger.debug(f"Mouse Event {event}")
        # we need to get the x,y position of the Mouse Event,
        # and using the step_size of the position_controller,
        # find the corresponding spectrum stored in self.hyper_spectral_raw_data array.
        # then create a new window to display the spectrum.
        # see qt3scan.main.show_optimization_plot function for how to build a
        # new window with data

        # NB this is tech debt here. We have GUI (view) code inside a controller
        # A better solution would be to simply return the data to the caller (qt3scan.main)
        # and make it responsible to build a GUI
        # For the sake of expediency we leave this here

        if event.xdata is None or event.ydata is None:
            return

        win = tk.Toplevel()
        win.title(f'Spectrum for location (x,y): {event.xdata}, {event.ydata}')
        fig, ax = plt.subplots()
        ax.set_xlabel('Wavelength (nm)')
        ax.set_ylabel('Counts / bin')

        dist_x = event.xdata + self.step_size/2 - self.xmin  # we have to subtract step_size / 2 because the GUI shifts the view. This isn't good. We should fix this in the GUI
        dist_y = event.ydata + self.step_size/2 - self.ymin
        self.logger.debug(f'Selected position at distance from lower left (x, y): {dist_x, dist_y}')
        index_x = int(dist_x / self.step_size)
        index_y = int(dist_y / self.step_size)
        self.logger.debug(f'Selecting {index_y}, {index_x} from hyper spectral array of shape {self.hyper_spectral_raw_data.shape}')
        selected_spectrum = self.hyper_spectral_raw_data[index_y, index_x, :]

        ax.plot(self.hyper_spectral_wavelengths, selected_spectrum, label='data')
        ax.grid(True)

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas.draw()
