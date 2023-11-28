import logging
import tkinter as tk
from typing import Tuple, Optional, Union

import nidaqmx
import nipiezojenapy


class QT3ScanNIDAQPositionController:

    def __init__(self, logger_level):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logger_level)

        self.position_controller = nipiezojenapy.PiezoControl('Dev1')

        self.last_config_dict = {}

    @property
    def maximum_allowed_position(self):
        """Abstract property: maximum_allowed_position"""
        return self.position_controller.maximum_allowed_position

    @property
    def minimum_allowed_position(self):
        """Abstract property: minimum_allowed_position"""
        return self.position_controller.minimum_allowed_position

    def go_to_position(self,
                       x: Optional[float] = None,
                       y: Optional[float] = None,
                       z: Optional[float] = None) -> None:
        """
        This method is used to move the stage or objective to a position.
        """
        try:
            self.position_controller.go_to_position(x, y, z)
        except (nidaqmx.errors.DaqError, nidaqmx._lib.DaqNotFoundError) as e:
            self.logger.error(e)

    def get_current_position(self) -> Tuple[float, float, float]:
        try:
            return self.position_controller.get_current_position()
        except (nidaqmx.errors.DaqError, nidaqmx._lib.DaqNotFoundError) as e:
            self.logger.error(e)
            return self.position_controller.last_write_values

    def check_allowed_position(self,
                               x: Optional[float] = None,
                               y: Optional[float] = None,
                               z: Optional[float] = None) -> None:
        """
        This method checks if the position is within the allowed range.

        If the position is not within the allowed range, a ValueError should be raised.
        """
        try:
            self.position_controller.check_allowed_position(x, y, z)
        except (nidaqmx.errors.DaqError, nidaqmx._lib.DaqNotFoundError) as e:
            self.logger.error(e)

    def split_channels(self, channels: str) -> Union[None, Tuple[str, str, str]]:
        """
        This method splits a comma separated string of channels into a tuple of three channels.
        """
        if channels is None:
            return None
        channel_list = channels.split(',')
        if len(channel_list) != 3:
            raise ValueError(f"Expected 3 channels, got {len(channel_list)}")
        return tuple(channel_list)

    def channels_to_str(self, channels: Tuple[str, str, str]) -> str:
        """
        This method converts a tuple of three channels into a comma separated string.
        """
        if channels is None:
            return 'None'
        return ','.join(channels)

    def vals_to_str(self, vals: Tuple) -> str:
        """
        This method converts a tuple of values into a comma separated string.
        """
        if len(set(vals)) == 1:
            return str(vals[0])
        else:
            return ','.join([str(x) for x in vals])

    def configure(self, config_dict: dict):

        self.logger.debug("calling configure")

        # TODO -- modify the data generator so that these are properties that can be set rather than
        # accessing the private variables directly.
        self.last_config_dict.update(config_dict)
        self.logger.debug(config_dict)

        self.position_controller.device_name = config_dict.get('daq_name', self.position_controller.device_name)
        if 'write_channels' in config_dict:
            self.position_controller.write_channels = self.split_channels(config_dict['write_channels'])

        if 'read_channels' in config_dict:
            self.position_controller.read_channels = self.split_channels(config_dict['read_channels'])

        self.position_controller.scale_microns_per_volt = config_dict.get('scale_microns_per_volt',
                                                                          self.position_controller.scale_microns_per_volt)
        self.position_controller.zero_microns_volt_offset = config_dict.get('zero_microns_volt_offset',
                                                                          self.position_controller.zero_microns_volt_offset)
        self.position_controller.maximum_allowed_position = config_dict.get('maximum_allowed_position',
                                                                            self.position_controller.maximum_allowed_position)
        self.position_controller.minimum_allowed_position = config_dict.get('minimum_allowed_position',
                                                                            self.position_controller.minimum_allowed_position)
        self.position_controller.settling_time_in_seconds = config_dict.get('settling_time_in_seconds',
                                                                            self.position_controller.settling_time_in_seconds)

    def configure_view(self, gui_root: tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the controller.
        """
        config_win = tk.Toplevel(gui_root)
        config_win.grab_set()
        config_win.title(f"{self.__class__.__name__} Settings")

        row = 0
        tk.Label(config_win, text="DAQ Name").grid(row=row, column=0)
        daq_var = tk.StringVar(value=self.position_controller.device_name)
        tk.Entry(config_win, textvariable=daq_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Write Channels").grid(row=row, column=0)
        write_channels_var = tk.StringVar(value=self.channels_to_str(self.position_controller.write_channels))
        tk.Entry(config_win, textvariable=write_channels_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Read Channels").grid(row=row, column=0)
        read_channels_var = tk.StringVar(value=self.channels_to_str(self.position_controller.read_channels))
        tk.Entry(config_win, textvariable=read_channels_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Scale Microns per Volt").grid(row=row, column=0)
        scale_microns_per_volt_var = tk.StringVar(value=self.vals_to_str(self.position_controller.scale_microns_per_volt))
        tk.Entry(config_win, textvariable=scale_microns_per_volt_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Zero Micron Voltage").grid(row=row, column=0)
        zero_microns_volt_offset_var = tk.StringVar(value=self.vals_to_str(self.position_controller.zero_microns_volt_offset))
        tk.Entry(config_win, textvariable=zero_microns_volt_offset_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Maximum Allowed Position (microns)").grid(row=row, column=0)
        maximum_allowed_position_var = tk.DoubleVar(value=self.position_controller.maximum_allowed_position)
        tk.Entry(config_win, textvariable=maximum_allowed_position_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Minimum Allowed Position (microns)").grid(row=row, column=0)
        minimum_allowed_position_var = tk.DoubleVar(value=self.position_controller.minimum_allowed_position)
        tk.Entry(config_win, textvariable=minimum_allowed_position_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Settling Time (seconds)").grid(row=row, column=0)
        settling_time_in_seconds_var = tk.DoubleVar(value=self.position_controller.settling_time_in_seconds)
        tk.Entry(config_win, textvariable=settling_time_in_seconds_var).grid(row=row, column=1)

        # pack variables into a dictionary to pass to the convert_gui_info_and_configure method
        gui_info = {
            'daq_name': daq_var,
            'write_channels': write_channels_var,
            'read_channels': read_channels_var,
            'scale_microns_per_volt': scale_microns_per_volt_var,
            'zero_microns_volt_offset': zero_microns_volt_offset_var,
            'maximum_allowed_position': maximum_allowed_position_var,
            'minimum_allowed_position': minimum_allowed_position_var,
            'settling_time_in_seconds': settling_time_in_seconds_var,
        }

        def convert_gui_info_and_configure():
            config_dict = {}
            for k, v in gui_info.items():
                if k in ['scale_microns_per_volt', 'zero_microns_volt_offset']:
                    if v.get() in ['None', '']:
                        raise ValueError(f"{k} must be a float, int, or list of three floats or ints. got {v.get()}")
                    split_v = v.get().split(',')
                    if len(split_v) == 1:
                        config_dict[k] = float(split_v[0])   
                    else:
                        config_dict[k] = [float(x) for x in split_v]
                else:
                    if v.get() not in ['None', '']:
                        config_dict[k] = v.get()
                    else:
                        config_dict[k] = None
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
