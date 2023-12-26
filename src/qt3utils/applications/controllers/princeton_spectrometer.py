from typing import Generator
import numpy as np
import tkinter as tk
import logging

import qt3utils.datagenerators.princeton as princeton

module_logger = logging.getLogger(__name__)
module_logger.setLevel(logging.ERROR)

class QT3ScanPrincetonSpectrometerController:

    def __init__(self, logger_level):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.spectrometer = princeton.Spectrometer()
        self.last_config_dict = {}

    def configure(self, config_dict: dict) -> None:
        """ 
        This method is used to configure the spectrometer with the provided settings.
        """
        self.logger.debug("Calling configure on the Princeton Spectrometer data controller")
        self.last_config_dict.update(config_dict)
        
        self.spectrometer.center_wavelength = float(config_dict.get('center_wavelength', self.spectrometer.center_wavelength))
        self.spectrometer.exposure_time = float(config_dict.get('exposure_time', self.spectrometer.exposure_time))
        self.spectrometer.temperature_sensor_setpoint = float(config_dict.get('temperature_sensor_setpoint', self.spectrometer.temperature_sensor_setpoint))
        self.spectrometer.num_frames = float(config_dict.get('num_frames', self.spectrometer.num_frames))
        self.spectrometer.grating = config_dict.get('grating', self.spectrometer.grating)
        
        #NOTE: These are meant to be passed as parameters into the "acquire_step_and_glue" function. Not sure if I should have them here.
        self.wave_start = config_dict.get('wave_start', self.spectrometer.wave_start)
        self.wave_end = config_dict.get('wave_end', self.spectrometer.wave_end)

    def start(self) -> None:
        self.spectrometer.initialize()
    

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """ 
        This method launches a GUI window to configure the data controller.
        """
        
        config_win = tk.Toplevel(gui_root)
        config_win.grab_set()
        config_win.title('Princeton Spectrometer Settings')
        
        row = 0
        tk.Label(config_win, text="Exposure Time (ms)").grid(row=row, column=0, padx=10)
        exposure_time_var = tk.StringVar(value=str(self.spectrometer.exposure_time))
        tk.Entry(config_win, textvariable=exposure_time_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Center Wavelength (nm)").grid(row=row, column=0, padx=10)
        center_wavelength_var = tk.StringVar(value=str(self.spectrometer.center_wavelength))
        tk.Entry(config_win, textvariable=center_wavelength_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Temperature Sensor Setpoint (°C)").grid(row=row, column=0, padx=10)
        temperature_sensor_setpoint_var = tk.StringVar(value=str(self.spectrometer.temperature_sensor_setpoint))
        tk.Entry(config_win, textvariable=temperature_sensor_setpoint_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Grating").grid(row=row, column=0, padx=10)
        grating_var = tk.StringVar(value=self.spectrometer.grating)
        tk.Entry(config_win, textvariable=grating_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Wavelength Start (nm)").grid(row=row, column=0, padx=10)
        wave_start_var = tk.StringVar(value=str(self.wave_start))
        tk.Entry(config_win, textvariable=wave_start_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Wavelength End (nm)").grid(row=row, column=0, padx=10)
        wave_end_var = tk.StringVar(value=str(self.wave_end))
        tk.Entry(config_win, textvariable=wave_end_var).grid(row=row, column=1)

        # Pack variables into a dictionary to pass to the _set_from_gui method
        gui_info = {
            'exposure_time': exposure_time_var,
            'center_wavelength': center_wavelength_var,
            'temperature_sensor_setpoint': temperature_sensor_setpoint_var,
            'grating': grating_var,
            'wave_start': wave_start_var,
            'wave_end': wave_end_var
        }

        row += 1
        tk.Button(config_win, text='Set', command=lambda: self._set_from_gui(gui_info)).grid(row=row, column=0)
        tk.Button(config_win, text='Close', command=config_win.destroy).grid(row=row, column=1)
    
    def _set_from_gui(self, gui_vars: dict) -> None:
        """
        Sets the spectrometer configuration from the GUI.
        """
        config_dict = {k:v.get() if v.get() not in ['None', ''] else None for k, v in gui_vars.items()}  # special case to handle None values
        self.logger.info(config_dict)
        self.configure(config_dict)
        
    def print_config(self) -> None:
        print("Princeton Spectrometer config")
        print(self.last_config_dict)  # we dont' use the logger because we want to be sure this is printed to stdout
            
    def close(self) -> None: 
        self.spectrometer.finalize()
