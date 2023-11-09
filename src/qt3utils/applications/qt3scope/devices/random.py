from typing import Union
import tkinter as tk

import qt3utils.datagenerators.daqsamplers as daqsamplers
from qt3utils.applications.qt3scope.interface import QT3ScopeDataControllerInterface


class QT3ScopeRandomDataController(QT3ScopeDataControllerInterface):

    def __init__(self):
        self.data_generator = daqsamplers.RandomRateCounter()

    def configure(self, **kw_config):
        """
        This method is used to configure the data controller.
        """
        print("calling configure on the random data controller")

        # TODO -- modify the data generator so that these are properties that can be set rather than
        # accessing the private variables directly.
        self.last_config = kw_config
        print(kw_config)

        self.data_generator.simulate_single_light_source = kw_config.get('simulate_single_light_source', False)
        self.data_generator.num_data_samples_per_batch = kw_config.get('num_data_samples_per_batch', 10)
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
        print('random configure view')

        config_win = tk.Toplevel(gui_root)
        config_win.geometry('400x200')

        row = 0
        win_title = tk.Label(config_win, text="RandomRateCounter Settings", font='Helvetica 16')
        win_title.grid(row=row, column=0, columnspan=2, pady=10)

        row += 1
        simulate_single_light_source_var = tk.BooleanVar()
        simulate_single_light_source_var.set(self.data_generator.simulate_single_light_source)
        simToggle = tk.Checkbutton(config_win,
                                   text="Simulate Single Light Source",
                                   variable=simulate_single_light_source_var,
                                   onvalue=True,
                                   offvalue=False)
        simToggle.grid(row=row, column=0, columnspan=2, pady=10)

        # pack variables into a dictionary to pass to the set_from_gui method
        gui_info = {
            'simulate_single_light_source': simulate_single_light_source_var,
        }

        # add a button to set the values and close the window
        row += 1
        tk.Button(config_win,
                  text='  Set  ',
                  command=lambda: self.set_from_gui(**gui_info)).grid(row=row, column=0)

        tk.Button(config_win,
                  text='Close',
                  command=config_win.destroy).grid(row=row, column=1)

        config_win.grab_set()

    def set_from_gui(self, **kwargs):
        """
        This method is used to set the data controller from the GUI.
        """

        for k, v in kwargs.items():
            kwargs[k] = v.get()

        print(kwargs)
        self.configure(**kwargs)

    def print_config(self) -> None:
        print("Random Data Controller Configuration:")
        print(self.last_config)

    def configure_from_yaml(self) -> None:
        """
        This method launches a GUI window to allow the user to select a yaml file to configure the data controller.
        """
        pass
