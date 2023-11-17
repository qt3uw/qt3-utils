from typing import Union
import numpy as np
import tkinter as tk

import qt3utils.datagenerators.daqsamplers as daqsamplers
from qt3utils.applications.qt3scope.interface import QT3ScopeDataControllerInterface


class QT3ScopeNIDAQEdgeCounterController(QT3ScopeDataControllerInterface):

    def __init__(self, logger):
        super().__init__(logger)
        self.data_generator = daqsamplers.NiDaqDigitalInputRateCounter()
        self.last_config_dict = {}

    def configure(self, config_dict: dict):
        """
        This method is used to configure the data controller.
        """
        self.logger.debug("calling configure on the nidaq edge counter data controller")
        self.last_config_dict.update(config_dict)

        self.data_generator.daq_name = config_dict.get('daq_name', self.data_generator.daq_name)
        self.data_generator.signal_terminal = config_dict.get('signal_terminal', self.data_generator.signal_terminal)
        self.data_generator.clock_terminal = config_dict.get('clock_terminal', self.data_generator.clock_terminal)
        self.data_generator.clock_rate = config_dict.get('clock_rate', self.data_generator.clock_rate)
        self.data_generator.num_data_samples_per_batch = config_dict.get('num_data_samples_per_batch', self.data_generator.num_data_samples_per_batch)
        self.data_generator.read_write_timeout = config_dict.get('read_write_timeout', self.data_generator.read_write_timeout)
        self.data_generator.signal_counter = config_dict.get('signal_counter', self.data_generator.signal_counter)

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
        config_win.title('NIDAQ Edge Counter Settings')

        row = 0
        tk.Label(config_win, text="DAQ Name").grid(row=row, column=0, padx=10)
        daq_var = tk.StringVar(value=self.data_generator.daq_name)
        tk.Entry(config_win, textvariable=daq_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Signal Terminal").grid(row=row, column=0, padx=10)
        signal_terminal_var = tk.StringVar(value=self.data_generator.signal_terminal)
        tk.Entry(config_win, textvariable=signal_terminal_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Clock Terminal").grid(row=row, column=0, padx=10)
        clock_terminal_var = tk.StringVar()
        clock_terminal_var.set(self.data_generator.clock_terminal)  # we set the var this way so that it captures "None".... otherwise it will be an empty string
        tk.Entry(config_win, textvariable=clock_terminal_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Clock Rate (Hz)").grid(row=row, column=0, padx=10)
        clock_rate_var = tk.IntVar(value=self.data_generator.clock_rate)
        tk.Entry(config_win, textvariable=clock_rate_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="N samples per batch").grid(row=row, column=0, padx=10)
        num_data_samples_per_batch_var = tk.IntVar(value=self.data_generator.num_data_samples_per_batch)
        tk.Entry(config_win, textvariable=num_data_samples_per_batch_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Read/Write Timeout (s)").grid(row=row, column=0, padx=10)
        read_write_timeout_var = tk.IntVar(value=self.data_generator.read_write_timeout)
        tk.Entry(config_win, textvariable=read_write_timeout_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Signal Counter").grid(row=row, column=0, padx=10)
        signal_counter_var = tk.StringVar(value=self.data_generator.signal_counter)
        tk.Entry(config_win, textvariable=signal_counter_var).grid(row=row, column=1)

        # pack variables into a dictionary to pass to the _set_from_gui method
        gui_info = {
            'daq_name': daq_var,
            'signal_terminal': signal_terminal_var,
            'clock_terminal': clock_terminal_var,
            'clock_rate': clock_rate_var,
            'num_data_samples_per_batch': num_data_samples_per_batch_var,
            'read_write_timeout': read_write_timeout_var,
            'signal_counter': signal_counter_var,
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
        config_dict = {k:v.get() if v.get() not in ['None', ''] else None for k, v in gui_vars.items()}  # special case to handle None values
        self.logger.info(config_dict)
        self.configure(config_dict)

    def print_config(self) -> None:
        print('NIDAQ edge counter config')
        print(self.last_config_dict)  # we dont' use the logger because we want to be sure this is printed to stdout