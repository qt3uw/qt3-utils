from typing import Union
import tkinter as tk

import qt3utils.datagenerators.daqsamplers as daqsamplers
from qt3utils.applications.qt3scope.interface import QT3ScopeDataControllerInterface


class QT3ScopeRandomDataController(QT3ScopeDataControllerInterface):

    def __init__(self, logger):
        super().__init__(logger)
        self.data_generator = daqsamplers.RandomRateCounter()
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

    def yield_count_rate(self):
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
