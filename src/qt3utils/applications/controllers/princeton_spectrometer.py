import numpy as np
import tkinter as tk
import logging
from typing import Tuple

import qt3utils.datagenerators.princeton as princeton


class QT3ScanPrincetonSpectrometerController:
    """
    Implements qt3utils.applications.qt3scan.interface.QT3ScanSpectrometerDAQControllerInterface
    """
    def __init__(self, logger_level: int):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.spectrometer = princeton.SpectrometerDataAcquisition()
        self.last_config_dict = {}

        self.wave_start = None
        self.wave_end = None
        self.last_measured_spectrum = None
        self.last_wavelength_array = None

    @property
    def clock_rate(self) -> float:
        try:
            _t = self.spectrometer.exposure_time / 1000.0  # Converting from milliseconds to seconds.
        except Exception as e:
            self.logger.error(e)
            _t = 2  # TODO: better default behavior. Should this be -1? 1? or should Spectrometer be changed.
        return 1.0 / _t

    def start(self) -> None:
        """
        Nothing to be done in this method. All acquisition is happening in the "sample_spectrum" method.
        """
        self.logger.debug('calling QT3ScanPrincetonSpectrometerController start')

    def stop(self) -> None:
        """
        Implementations should do necessary steps to stop acquiring data.
        """
        #TODO: Need to implement a feature to pause scan here. If there is a way to interrupt data acquistion, do that here. Otherwise, do nothing
        self.logger.debug('calling QT3ScanPrincetonSpectrometerController stop')

    def close(self) -> None:
        self.spectrometer.finalize()

    def sample_spectrum(self) -> Tuple[np.ndarray, np.ndarray]:
        self.last_measured_spectrum, self.last_wavelength_array = (self.spectrometer.acquire_step_and_glue([self.wave_start, self.wave_end]))
        #self.logger.debug(f'Length of what you pulled from get_wavelengths is {len(self.spectrometer.get_wavelengths())}')
        #self.logger.debug(f'Length of measured spectrum is {len(self.last_measured_spectrum)} and length of last wave array is {len(self.last_wavelength_array)}')
        self.logger.debug(f'acquired spectrum from {self.last_wavelength_array[0]} to {self.last_wavelength_array[-1]} nm')
        return self.last_measured_spectrum, self.last_wavelength_array

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the spectrometer with the provided settings.
        """
        self.logger.debug("Calling configure on the Princeton Spectrometer data controller")
        self.last_config_dict.update(config_dict)

        try:
            #NOTE: If you dont type cast these then you will get serialization errors
            self.spectrometer.experiment_name = str(config_dict.get('experiment_name', self.spectrometer.experiment_name))
            self.spectrometer.exposure_time = float(config_dict.get('exposure_time', self.spectrometer.exposure_time))
            self.spectrometer.center_wavelength = float(config_dict.get('center_wavelength', self.spectrometer.center_wavelength))
            self.spectrometer.temperature_sensor_setpoint = float(config_dict.get('temperature_sensor_setpoint', self.spectrometer.temperature_sensor_setpoint))
            self.spectrometer.grating = str(config_dict.get('grating', self.spectrometer.grating))
            self.wave_start = float(config_dict.get('wave_start', self.wave_start))
            self.wave_end = float(config_dict.get('wave_end', self.wave_end))
        except Exception as e:
            self.logger.error({str(e)})

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
        exposure_time_var = tk.DoubleVar(value=self.spectrometer.exposure_time)
        tk.Entry(config_win, textvariable=exposure_time_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Center Wavelength (nm)").grid(row=row, column=0, padx=10)
        center_wavelength_var = tk.DoubleVar(value=self.spectrometer.center_wavelength)
        tk.Entry(config_win, textvariable=center_wavelength_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Temperature Sensor Setpoint (°C)").grid(row=row, column=0, padx=10)
        temperature_sensor_setpoint_var = tk.DoubleVar(value=self.spectrometer.temperature_sensor_setpoint)
        tk.Entry(config_win, textvariable=temperature_sensor_setpoint_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Grating").grid(row=row, column=0, padx=10)
        grating_options = self.spectrometer.grating_options
        grating_var = tk.StringVar(value=self.spectrometer.grating)
        grating_menu = tk.OptionMenu(config_win, grating_var, *grating_options)
        grating_menu.grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Wavelength Start (nm)").grid(row=row, column=0, padx=10)
        wave_start_var = tk.DoubleVar(value=self.wave_start)
        tk.Entry(config_win, textvariable=wave_start_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Wavelength End (nm)").grid(row=row, column=0, padx=10)
        wave_end_var = tk.DoubleVar(value=self.wave_end)
        tk.Entry(config_win, textvariable=wave_end_var).grid(row=row, column=1)

        # Pack variables into a dictionary to pass to the _set_from_gui method
        gui_info = {
            'experiment_name': experiment_name_var,
            'exposure_time': exposure_time_var,
            'center_wavelength': center_wavelength_var,
            'temperature_sensor_setpoint': temperature_sensor_setpoint_var,
            'grating': grating_var,
            'wave_start': wave_start_var,
            'wave_end': wave_end_var, 
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
