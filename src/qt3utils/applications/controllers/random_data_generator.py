from typing import Union, Tuple, Optional
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

    def start(self) -> Union[dict, type(None)]:
        self.data_generator.start()

    def stop(self) -> Union[dict, type(None)]:
        self.data_generator.stop()

    def close(self) -> Union[dict, type(None)]:
        self.data_generator.close()

    def yield_count_rate(self) -> np.ndarray:
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

    def sample_count_rate(self, data_counts: np.ndarray) -> np.ndarray:
        return self.data_generator.sample_count_rate(data_counts)

    @property
    def num_data_samples_per_batch(self) -> int:
        return self.data_generator.num_data_samples_per_batch

    @num_data_samples_per_batch.setter
    def num_data_samples_per_batch(self, value):
        """Abstract property setter for num_data_samples_per_batch"""
        self.data_generator.num_data_samples_per_batch = value

    def get_daq_data(self) -> dict:
        data = dict(
                    raw_counts=self.data_generator.scanned_raw_counts,
                    count_rate=self.data_generator.scanned_count_rate,
                    step_size=self.data_generator.step_size,
                    daq_clock_rate=self.data_generator.clock_rate,
                    )
        return data

    def scan_image_rightclick_event(self, event) -> None:
        self.logger.debug(f"scan_image_rightclick_event. click at {event.x}, {event.y}")


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
    def maximum_allowed_position(self):
        """Abstract property: maximum_allowed_position"""
        return self.dummy_position.maximum_allowed_position

    @property
    def minimum_allowed_position(self):
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

    def configure(self, config_dict: dict):

        self.logger.debug("calling configure")

        # TODO -- modify the data generator so that these are properties that can be set rather than
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

        # pack variables into a dictionary to pass to the convert_gui_info_and_configure method
        gui_info = {
            'maximum_allowed_position': maximum_allowed_position_var,
            'minimum_allowed_position': minimum_allowed_position_var,
        }

        def convert_gui_info_and_configure():
            """
            This method sets the configuration values from the GUI.
            """
            config_dict = {k: v.get() for k, v in gui_info.items()}
            self.logger.info(config_dict)
            self.configure(config_dict)

        # add a button to set the values and close the window
        row += 1
        tk.Button(config_win,
                  text='  Set  ',
                  command=convert_gui_info_and_configure).grid(row=row, column=0)

        tk.Button(config_win,
                  text='Close',
                  command=config_win.destroy).grid(row=row, column=1)
