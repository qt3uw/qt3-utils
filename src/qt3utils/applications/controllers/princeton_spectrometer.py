import numpy as np
import tkinter as tk
import logging

import qt3utils.datagenerators.princeton as princeton

module_logger = logging.getLogger(__name__)
module_logger.setLevel(logging.ERROR)


class QT3ScanPrincetonSpectrometerController:

    def __init__(self, logger_level: int):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.spectrometer = princeton.Spectrometer()
        # self.spectrometer.initialize() # you should probably initialize the spectrometer with an __init__ method instead.
        self.last_config_dict = {}
        # self.spectrum = np.array([])
        # self.wavelength_array = np.array([])
        self.wave_start = None
        self.wave_end = None

    @property
    def clock_rate(self) -> float:
        return 1.0 / (self.spectrometer.exposure_time / 1000.0)  # convert from ms to s

    def start(self) -> None:
        # this function should take data for the current settings of the spectromter.
        # All data acquistion should occur here.
        self.logger.debug('calling QT3ScanPrincetonSpectrometerController start')
        # nothing to be done

    def stop(self) -> None:
        """
        Implementations should do necessary steps to stop acquiring data.
        """
        # if there is a way to interrupt data acquistion, do that here. Otherwise, do nothing
        pass

    def close(self) -> None:
        self.spectrometer.finalize()

    def sample_counts(self, num_batches: int) -> np.ndarray:
        """
        Implementations should return a numpy array of shape (1,2)

        The first element of the array should be the total number of counts
        The second element of the array should be the total number of clock ticks.
        For example, see daqsamplers.RateCounterBase.sample_counts(), which
        returns a numpy array of shape (1,2) when sum_counts = True.
        """
        # this is a simple integeration of all of the counts in the spectrum
        # it may be desireable to apply some kind of filter to the spectrum before integration
        # one simple filter may be to allow the user to configure a start / stop wavelength
        # that is applied to a narrow region of the full spectrum that was acquired.

        self.measured_spectrum, self.wavelength_array = self.spectrometer.acquire_step_and_glue([self.wave_start, self.wave_end])
        self.logger.debug(f'acquired spectrum from {self.wavelength_array[0]} to {self.wavelength_array[-1]} nm')
        sample_counts = np.array([[np.sum(self.measured_spectrum), 1]])
        self.logger.debug(sample_counts)
        return sample_counts  # this should be of shape (1,2)

    def sample_count_rate(self, data_counts: np.ndarray) -> np.floating:
        """
        Implementations should return a numpy floating point number

        The returned value should be the count rate in counts per second.
        The input of data_counts should be of shape (1, 2) where the first
        element is the number of counts, the second element is the number of clock ticks.
        Using the clock_rate, this method should compute the count rate, which is
        counts / (clock_ticks / clock_rate).
        """
        # cribbed from daqsamplers.RateCounterBase.sample_count_rate
        _data = np.sum(data_counts, axis=0)
        if _data[1] > 0:
            return self.clock_rate * _data[0]/_data[1]
        else:
            return np.nan

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the spectrometer with the provided settings.
        """
        self.logger.debug("Calling configure on the Princeton Spectrometer data controller")
        self.last_config_dict.update(config_dict)

        self.spectrometer.experiment_name = config_dict.get('experiment_name', self.spectrometer.experiment_name)
        self.spectrometer.center_wavelength = float(config_dict.get('center_wavelength', self.spectrometer.center_wavelength))
        self.spectrometer.exposure_time = float(config_dict.get('exposure_time', self.spectrometer.exposure_time))
        self.spectrometer.temperature_sensor_setpoint = float(config_dict.get('temperature_sensor_setpoint', self.spectrometer.temperature_sensor_setpoint))
        self.spectrometer.num_frames = float(config_dict.get('num_frames', self.spectrometer.num_frames))
        self.spectrometer.grating = config_dict.get('grating', self.spectrometer.grating)

        #NOTE: These are meant to be passed as parameters into the "acquire_step_and_glue" function. Not sure if I should have them here.
        self.wave_start = float(config_dict.get('wave_start', self.wave_start))
        self.wave_end = float(config_dict.get('wave_end', self.wave_end))

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the data controller.
        """

        config_win = tk.Toplevel(gui_root)
        config_win.grab_set()
        config_win.title('Princeton Spectrometer Settings')

        # TODO: change all of the StringVar to DoubleVar and remove casting above
        row = 0
        tk.Label(config_win, text="Experiment Name)").grid(row=row, column=0, padx=10)
        experiment_name_var = tk.StringVar(value=str(self.spectrometer.experiment_name))
        tk.Entry(config_win, textvariable=experiment_name_var).grid(row=row, column=1)

        row += 1
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
            'experiment_name': experiment_name_var,
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
