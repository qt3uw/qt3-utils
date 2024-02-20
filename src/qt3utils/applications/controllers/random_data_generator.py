from typing import Tuple, Optional, Generator
import tkinter as tk
import logging
import numpy as np

import nipiezojenapy

import qt3utils.datagenerators.daqsamplers
import qt3utils.datagenerators


class QT3ScopeRandomDataController:
    """
    Implements the qt3utils.applications.qt3scope.interface.QT3ScopeDAQControllerInterface for a random data generator.
    """

    def __init__(self, logger_level):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.data_generator = qt3utils.datagenerators.daqsamplers.RandomRateCounter()
        self.last_config_dict = {}

    def configure(self, config_dict: dict):
        """
        This method is used to configure the data controller.
        """
        self.logger.debug("calling configure on the random data controller")

        # TODO -- modify the data generator so that these are properties that can be set rather than
        # accessing the private variables directly.
        self.last_config_dict.update(config_dict)
        self.logger.debug(config_dict)

        self.data_generator.simulate_single_light_source = config_dict.get('simulate_single_light_source',
                                                                           self.data_generator.simulate_single_light_source)
        self.data_generator.num_data_samples_per_batch = config_dict.get('num_data_samples_per_batch',
                                                                         self.data_generator.num_data_samples_per_batch)
        self.data_generator.default_offset = config_dict.get('default_offset',
                                                             self.data_generator.default_offset)
        self.data_generator.signal_noise_amp = config_dict.get('signal_noise_amp',
                                                               self.data_generator.signal_noise_amp)
        ## NB - I don't like how all of these configuration values are being accessed by string name.

    def start(self) -> None:
        self.data_generator.start()

    def stop(self) -> None:
        self.data_generator.stop()

    def close(self) -> None:
        self.data_generator.close()

    def yield_count_rate(self) -> Generator[np.floating, None, None]:
        """
        This method is used to yield data from the data controller.
        """
        return self.data_generator.yield_count_rate()

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the data controller.
        """

        config_win = tk.Toplevel(gui_root)
        config_win.grab_set()
        config_win.title('RandomRateCounter Settings')

        row = 0
        simulate_single_light_source_var = tk.BooleanVar(value=self.data_generator.simulate_single_light_source)
        simToggle = tk.Checkbutton(config_win,
                                   text="Simulate Single Light Source",
                                   variable=simulate_single_light_source_var,
                                   onvalue=True,
                                   offvalue=False)
        simToggle.grid(row=row, column=0, columnspan=2, pady=10, padx=10)

        row += 1
        tk.Label(config_win, text="N per batch").grid(row=row, column=0, padx=10)
        n_var = tk.IntVar(value=self.data_generator.num_data_samples_per_batch)
        tk.Entry(config_win, textvariable=n_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Default Offset").grid(row=row, column=0, padx=10)
        offset_var = tk.IntVar(value=self.data_generator.default_offset)
        tk.Entry(config_win, textvariable=offset_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Signal to Noise").grid(row=row, column=0, padx=10)
        signal_noise_amp_var = tk.DoubleVar(value=self.data_generator.signal_noise_amp)
        tk.Entry(config_win, textvariable=signal_noise_amp_var).grid(row=row, column=1)

        # pack variables into a dictionary to pass to the _set_from_gui method
        gui_info = {
            'simulate_single_light_source': simulate_single_light_source_var,
            'num_data_samples_per_batch': n_var,
            'default_offset': offset_var,
            'signal_noise_amp': signal_noise_amp_var
        }

        # add a button to set the values and close the window
        row += 1
        tk.Button(config_win,
                  text='  Set  ',
                  command=lambda: self._set_from_gui(gui_info)).grid(row=row, column=0)

        tk.Button(config_win,
                  text='Close',
                  command=config_win.destroy).grid(row=row, column=1)

    def _set_from_gui(self, gui_vars: dict) -> None:
        """
        This method is used to set the data controller from the GUI.
        """
        config_dict = {k:v.get() for k, v in gui_vars.items()}
        self.logger.info(config_dict)
        self.configure(config_dict)

    def print_config(self) -> None:
        print("\nRandom Data Controller Configuration:")
        print(self.last_config_dict)


class QT3ScanRandomDataController(QT3ScopeRandomDataController):
    """
    Implements the qt3utils.applications.qt3scan.interface.QT3ScanDAQControllerInterface for a random data generator.
    """

    @property
    def clock_rate(self) -> float:
        return self.data_generator.clock_rate

    def sample_counts(self, num_batches: int) -> np.ndarray:
        return self.data_generator.sample_counts(num_batches)

    def sample_count_rate(self, data_counts: np.ndarray) -> np.floating:
        return self.data_generator.sample_count_rate(data_counts)


class QT3ScanRandomSpectrometerDataController:
    """
    Implements qt3utils.applications.qt3scan.interface.QT3ScanSpectrometerDAQControllerInterface
    """
    def __init__(self, logger_level: int):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.spectrometer = self.RandomSpectometer()

        self.last_config_dict = {}

        self.last_measured_spectrum = None
        self.last_wavelength_array = None

    class RandomSpectometer:
        def __init__(self):
            self.exposure_time = 500 # milliseconds
            self.experiment_name = ""
            self.num_wavelength_bins = 250
            self.wave_start = 600
            self.wave_end = 850
            self.num_frames = 1
            self.center_wavelength = 700  # nm
            self.sensor_temperature_set_point = -70  # grad

            self.nv_probability = 0.01
            self.background_counts = int(1e5)
            self.nv_brightness = int(1e6)

        def acquire_step_and_glue(self) -> Tuple[np.ndarray, np.ndarray]:
            wavelengths = np.linspace(self.wave_start, self.wave_end, self.num_wavelength_bins, endpoint=False)
            if np.random.random() > self.nv_probability:
                spectrum = self.background_counts * np.random.random(self.num_wavelength_bins) / self.num_wavelength_bins
            else:
                redux = 10
                num_samples = int(self.nv_brightness / redux) # a little hack to make the sampling faster
                sample_sideband = np.random.normal(690, 40, size=99 * num_samples // 100)
                bins = np.linspace(self.wave_start, self.wave_end, self.num_wavelength_bins + 1, endpoint=True)
                hist_sideband, _ = np.histogram(sample_sideband, bins=bins)
                zpl_sample = np.random.normal(637, 2, size=1 * num_samples // 100)
                zpl, _ = np.histogram(zpl_sample, bins=bins)
                spectrum = (zpl + hist_sideband) * redux
            return spectrum, wavelengths

    @property
    def clock_rate(self) -> float:
        try:
            _t = self.spectrometer.exposure_time / 1000.0  #Convert from milliseconds to seconds.
        except Exception as e:
            self.logger.error(e)
            _t = 2  #TODO: better default behavior. Should this be -1? 1? or should Spectrometer be changed.
        return 1.0 / _t

    def start(self) -> None:
        """
        Nothing to be done in this method. All acquisition is happening in the "sample_spectrum" method.
        """
        self.logger.debug('calling QT3ScanRandomSpectrometerDataController start')

    def stop(self) -> None:
        """
        Implementations should do necessary steps to stop acquiring data.
        """
        # if there is a way to interrupt data acquistion, do that here. Otherwise, do nothing
        self.logger.debug('calling QT3ScanRandomSpectrometerDataController stop')

    def close(self) -> None:
        self.logger.debug('calling QT3ScanRandomSpectrometerDataController close')

    def sample_spectrum(self) -> Tuple[np.ndarray, np.ndarray]:
        self.last_measured_spectrum, self.last_wavelength_array = (
            self.spectrometer.acquire_step_and_glue()
        )
        # self.logger.debug(f'acquired spectrum from {self.last_wavelength_array[0]}'
        #                   f'to {self.last_wavelength_array[-1]} nm')
        return self.last_measured_spectrum, self.last_wavelength_array

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the spectrometer with the provided settings.
        """
        self.logger.debug("QT3ScanRandomSpectrometerDataController.configure called")
        self.last_config_dict.update(config_dict)

        self.spectrometer.experiment_name = config_dict.get('experiment_name', self.spectrometer.experiment_name)
        self.spectrometer.center_wavelength = config_dict.get('center_wavelength', self.spectrometer.center_wavelength)
        self.spectrometer.exposure_time = config_dict.get('exposure_time', self.spectrometer.exposure_time)
        self.spectrometer.sensor_temperature_set_point = config_dict.get('sensor_temperature_set_point', self.spectrometer.sensor_temperature_set_point)
        self.spectrometer.num_frames = config_dict.get('num_frames', self.spectrometer.num_frames)
        self.spectrometer.num_wavelength_bins = config_dict.get('num_wavelength_bins', self.spectrometer.num_wavelength_bins)
        self.spectrometer.wave_start = config_dict.get('wave_start', self.spectrometer.wave_start)
        self.spectrometer.wave_end = config_dict.get('wave_end', self.spectrometer.wave_end)
        self.spectrometer.nv_probability = config_dict.get('nv_probability', self.spectrometer.nv_probability)

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the data controller.
        """
        config_win = tk.Toplevel(gui_root)
        config_win.grab_set()
        config_win.title('Princeton Spectrometer Settings')

        row = 0
        tk.Label(config_win, text="Experiment Name)").grid(row=row, column=0, padx=10)
        experiment_name_var = tk.StringVar(value=str(self.spectrometer.experiment_name))
        tk.Entry(config_win, textvariable=experiment_name_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Exposure Time (ms)").grid(row=row, column=0, padx=10)
        exposure_time_var = tk.IntVar(value=str(self.spectrometer.exposure_time))
        tk.Entry(config_win, textvariable=exposure_time_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Center Wavelength (nm)").grid(row=row, column=0, padx=10)
        center_wavelength_var = tk.IntVar(value=str(self.spectrometer.center_wavelength))
        tk.Entry(config_win, textvariable=center_wavelength_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Temperature Sensor Setpoint (°C)").grid(row=row, column=0, padx=10)
        sensor_temperature_set_point_var = tk.IntVar(value=str(self.spectrometer.sensor_temperature_set_point))
        tk.Entry(config_win, textvariable=sensor_temperature_set_point_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Num Wavelength Bins").grid(row=row, column=0, padx=10)
        num_wavelength_bins_var = tk.IntVar(value=self.spectrometer.num_wavelength_bins)
        tk.Entry(config_win, textvariable=num_wavelength_bins_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Wavelength Start (nm)").grid(row=row, column=0, padx=10)
        wave_start_var = tk.IntVar(value=str(self.spectrometer.wave_start))
        tk.Entry(config_win, textvariable=wave_start_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Wavelength End (nm)").grid(row=row, column=0, padx=10)
        wave_end_var = tk.IntVar(value=str(self.spectrometer.wave_end))
        tk.Entry(config_win, textvariable=wave_end_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="NV Probability").grid(row=row, column=0, padx=10)
        nv_probability_var = tk.DoubleVar(value=str(self.spectrometer.nv_probability))
        tk.Entry(config_win, textvariable=nv_probability_var).grid(row=row, column=1)

        gui_info = {
            'experiment_name': experiment_name_var,
            'exposure_time': exposure_time_var,
            'center_wavelength': center_wavelength_var,
            'sensor_temperature_set_point': sensor_temperature_set_point_var,
            'num_wavelength_bins': num_wavelength_bins_var,
            'wave_start': wave_start_var,
            'wave_end': wave_end_var,
            'nv_probability': nv_probability_var,
        }

        row += 1
        tk.Button(config_win, text='Set', command=lambda: self._set_from_gui(gui_info)).grid(row=row, column=0)
        tk.Button(config_win, text='Close', command=config_win.destroy).grid(row=row, column=1)

    def _set_from_gui(self, gui_vars: dict) -> None:
        """
        Sets the spectrometer configuration from the GUI.
        """
        config_dict = {k:v.get() if v.get() not in ['None', ''] else None for k, v in gui_vars.items()}  # code to handle the edge case where there are "None" value
        self.logger.info(config_dict)
        self.configure(config_dict)

    def print_config(self) -> None:
        print("Princeton Spectrometer config")
        print(self.last_config_dict)  #NOTE: We dont' use the logger because we want to be sure this is printed to stdout

class QT3ScanDummyPositionController:
    """
    Implements the qt3utils.applications.qt3scan.interface.QT3ScanPositionControllerInterface for a dummy position controller.
    """
    def __init__(self, logger_level):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.dummy_position = nipiezojenapy.BaseControl()
        self.last_config_dict = {}

    @property
    def maximum_allowed_position(self) -> float:
        """Abstract property: maximum_allowed_position"""
        return self.dummy_position.maximum_allowed_position

    @property
    def minimum_allowed_position(self) -> float:
        """Abstract property: minimum_allowed_position"""
        return self.dummy_position.minimum_allowed_position

    def go_to_position(self,
                       x: Optional[float] = None,
                       y: Optional[float] = None,
                       z: Optional[float] = None) -> None:
        """
        This method is used to move the stage or objective to a position.
        """
        self.dummy_position.go_to_position(x, y, z)

    def get_current_position(self) -> Tuple[float, float, float]:
        return self.dummy_position.get_current_position()

    def check_allowed_position(self,
                               x: Optional[float] = None,
                               y: Optional[float] = None,
                               z: Optional[float] = None) -> None:
        """
        This method checks if the position is within the allowed range.
        If the position is not within the allowed range, a ValueError should be raised.
        """
        self.dummy_position.check_allowed_position(x, y, z)

    def configure(self, config_dict: dict) -> None:

        # TODO -- modify the nipiezojenapy.BaseController class so that these are properties that can be set rather than
        # accessing the private variables directly.
        self.last_config_dict.update(config_dict)
        self.logger.debug(config_dict)

        self.dummy_position.maximum_allowed_position = config_dict.get('maximum_allowed_position',
                                                                       self.dummy_position.maximum_allowed_position)
        self.dummy_position.minimum_allowed_position = config_dict.get('minimum_allowed_position',
                                                                       self.dummy_position.minimum_allowed_position)

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the controller.
        """
        config_win = tk.Toplevel(gui_root)
        config_win.grab_set()
        config_win.title(f"{self.__class__.__name__} Settings")

        row = 0
        tk.Label(config_win, text="Maximum Allowed Position").grid(row=row, column=0)
        maximum_allowed_position_var = tk.IntVar(value=self.dummy_position.maximum_allowed_position)
        tk.Entry(config_win, textvariable=maximum_allowed_position_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Minimum Allowed Position").grid(row=row, column=0)
        minimum_allowed_position_var = tk.IntVar(value=self.dummy_position.minimum_allowed_position)
        tk.Entry(config_win, textvariable=minimum_allowed_position_var).grid(row=row, column=1)

        gui_info = {
            'maximum_allowed_position': maximum_allowed_position_var,
            'minimum_allowed_position': minimum_allowed_position_var,
        }

        def convert_gui_info_and_configure():
            """
            This method sets the configuration values from the GUI.
            """
            config_dict = {k: v.get() for k, v in gui_info.items()}
            self.configure(config_dict)

        row += 1
        tk.Button(config_win,
                  text='  Set  ',
                  command=convert_gui_info_and_configure).grid(row=row, column=0)

        tk.Button(config_win,
                  text='Close',
                  command=config_win.destroy).grid(row=row, column=1)
