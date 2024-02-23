import logging
import tkinter as tk
from typing import Tuple

import numpy as np

import qt3utils.datagenerators.spectrometers.princeton as princeton


class QT3ScanPrincetonSpectrometerController:
    """
    Implements qt3utils.applications.qt3scan.interface.QT3ScanSpectrometerDAQControllerInterface
    """
    def __init__(self, logger_level: int):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.spectrometer_config = princeton.PrincetonSpectrometerConfig()
        self.spectrometer_daq = princeton.PrincetonSpectrometerDataAcquisition(self.spectrometer_config)

        self.logger.debug('Initializing the Princeton Spectrometer')
        self.spectrometer_config.open()
        
        self.last_config_dict = {}

        self.last_measured_spectrum = None
        self.last_wavelength_array = None

    @property
    def clock_rate(self) -> float:
        """
        The clock rate of a single exposure (1/exposure_time in Hz).
        """
        try:
            _t = self.spectrometer_config.exposure_time / 1000.0  # Converting from milliseconds to seconds.
        except Exception as e:
            self.logger.error(e)
            _t = 2
        return 1.0 / _t

    def start(self) -> None:
        """
        Nothing to be done in this method. All acquisitions are happening in the "sample_spectrum" method.
        """
        self.logger.debug('calling QT3ScanPrincetonSpectrometerController start')

    def stop(self) -> None:
        """
        Implementations should do the necessary steps to stop acquiring data.
        """
        self.spectrometer_daq.stop_acquisition()
        self.logger.debug('calling QT3ScanPrincetonSpectrometerController stop')

    def close(self) -> None:
        self.spectrometer_config.close()

    def sample_spectrum(self) -> Tuple[np.ndarray, np.ndarray]:
        self.last_measured_spectrum, self.last_wavelength_array = self.spectrometer_daq.acquire('step-and-glue')
        # self.logger.debug(f'Length of what you pulled from get_wavelengths is {len(self.spectrometer.get_wavelengths())}')
        # self.logger.debug(f'Length of measured spectrum is {len(self.last_measured_spectrum)} and length of last wave array is {len(self.last_wavelength_array)}')
        self.logger.debug(
            f'acquired spectrum from {self.last_wavelength_array[0]} to {self.last_wavelength_array[-1]} nm')
        return self.last_measured_spectrum, self.last_wavelength_array

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the spectrometer with the provided settings.
        """
        self.logger.debug("Calling configure on the Princeton Spectrometer data controller")
        self.last_config_dict.update(config_dict)

        self.spectrometer_config.experiment_name = config_dict.get('experiment_name', self.spectrometer_config.experiment_name)
        self.spectrometer_config.exposure_time = config_dict.get('exposure_time', self.spectrometer_config.exposure_time)
        self.spectrometer_config.center_wavelength = config_dict.get('center_wavelength', self.spectrometer_config.center_wavelength)
        self.spectrometer_config.sensor_temperature_set_point = config_dict.get('sensor_temperature_set_point',
                                                                                self.spectrometer_config.sensor_temperature_set_point)
        self.spectrometer_config.current_grating = config_dict.get('current_grating', self.spectrometer_config.current_grating)
        self.spectrometer_config.starting_wavelength = config_dict.get('starting_wavelength', self.spectrometer_config.starting_wavelength)
        self.spectrometer_config.ending_wavelength = config_dict.get('ending_wavelength', self.spectrometer_config.ending_wavelength)

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the data controller.
        """
        config_win = tk.Toplevel(gui_root)
        config_win.grab_set()
        config_win.title('Princeton Spectrometer Settings')

        row = 0
        tk.Label(config_win, text="Experiment Name)").grid(row=row, column=0, padx=10)
        experiment_name_var = tk.StringVar(value=str(self.spectrometer_config.experiment_name))
        tk.Entry(config_win, textvariable=experiment_name_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Exposure Time (ms)").grid(row=row, column=0, padx=10)
        exposure_time_var = tk.DoubleVar(value=self.spectrometer_config.exposure_time)
        tk.Entry(config_win, textvariable=exposure_time_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Center Wavelength (nm)").grid(row=row, column=0, padx=10)
        center_wavelength_var = tk.DoubleVar(value=self.spectrometer_config.center_wavelength)
        tk.Entry(config_win, textvariable=center_wavelength_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Temperature Sensor Setpoint (°C)").grid(row=row, column=0, padx=10)
        sensor_temperature_set_point_var = tk.DoubleVar(value=self.spectrometer_config.sensor_temperature_set_point)
        tk.Entry(config_win, textvariable=sensor_temperature_set_point_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Grating").grid(row=row, column=0, padx=10)
        grating_list = self.spectrometer_config.grating_list
        current_grating_var = tk.StringVar(value=self.spectrometer_config.current_grating)
        grating_menu = tk.OptionMenu(config_win, current_grating_var, *grating_list)
        grating_menu.grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Wavelength Start (nm)").grid(row=row, column=0, padx=10)
        starting_wavelength_var = tk.DoubleVar(value=self.spectrometer_config.starting_wavelength)
        tk.Entry(config_win, textvariable=starting_wavelength_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Wavelength End (nm)").grid(row=row, column=0, padx=10)
        ending_wavelength_var = tk.DoubleVar(value=self.spectrometer_config.ending_wavelength)
        tk.Entry(config_win, textvariable=ending_wavelength_var).grid(row=row, column=1)

        # Pack variables into a dictionary to pass to the _set_from_gui method
        gui_info = {
            'experiment_name': experiment_name_var,
            'exposure_time': exposure_time_var,
            'center_wavelength': center_wavelength_var,
            'sensor_temperature_set_point': sensor_temperature_set_point_var,
            'current_grating': current_grating_var,
            'starting_wavelength': starting_wavelength_var,
            'ending_wavelength': ending_wavelength_var,
        }

        row += 1
        tk.Button(config_win, text='Set', command=lambda: self._set_from_gui(gui_info)).grid(row=row, column=0)
        tk.Button(config_win, text='Close', command=config_win.destroy).grid(row=row, column=1)

    def _set_from_gui(self, gui_vars: dict) -> None:
        """
        Sets the spectrometer configuration from the GUI.
        """
        config_dict = {k: v.get() if v.get() not in ['None', ''] else None for k, v in
                       gui_vars.items()}  # code to handle the edge case where there are "None" value
        self.logger.info(config_dict)
        self.configure(config_dict)

    def print_config(self) -> None:
        print("Princeton Spectrometer config")
        print(self.last_config_dict)  # NOTE: We don't use the logger to be sure this is printed to stdout
