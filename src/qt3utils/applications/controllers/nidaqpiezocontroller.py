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
    def maximum_allowed_position(self) -> float:
        return self.position_controller.maximum_allowed_position

    @property
    def minimum_allowed_position(self) -> float:
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

    def _split_channels(self, channels: Optional[str]) -> Union[None, Tuple[str, str, str]]:
        """
        This method splits a comma separated string of channels into a tuple of three channels.

        However, if channels is None or 'None', then returns None
        """
        if channels in [None, 'None']:
            return None
        channel_list = channels.split(',')
        if len(channel_list) != 3:
            raise ValueError(f"Expected 3 channels, got {len(channel_list)}")
        return tuple(channel_list)

    def _channels_to_str(self, channels: Union[None, str, Tuple[str, str, str]]) -> str:
        """
        This method converts a tuple of three channels into a comma separated string.

        However, if channels is None or 'None', then returns 'None'
        """
        if channels in [None, 'None']:
            return 'None'
        return ','.join(channels)

    def _vals_to_str(self, vals: Tuple) -> str:
        """
        This method converts a tuple of values into a comma separated string.
        """
        return ','.join([str(x) for x in vals])

    def configure(self, config_dict: dict) -> None:

        self.logger.debug("calling configure")

        # TODO -- modify the nipiezojenapy.PiezoControl so that these are properties that can be set rather than
        # accessing the private variables directly.

        protected_config_dict = {}
        for key, val in config_dict.items():
            if key in ['scale_microns_per_volt', 'zero_microns_volt_offset']:
                if val in [None, 'None', '']:
                    raise ValueError(f"{key} must be a float, int, or list of three floats or ints. got {val}")

                if isinstance(val, str):
                    split_v = val.split(',')
                elif isinstance(val, (int, float)):
                    split_v = [val]
                elif isinstance(val, (list, tuple)):
                    split_v = val

                if len(split_v) == 1:
                    protected_config_dict[key] = float(split_v[0])
                else:
                    protected_config_dict[key] = [float(x) for x in split_v]
            else:
                protected_config_dict[key] = val if val not in ['None', ''] else None

        self.logger.debug('protected configuration')
        self.logger.debug(protected_config_dict)
        self.last_config_dict.update(protected_config_dict)

        self.position_controller.device_name = protected_config_dict.get('daq_name', self.position_controller.device_name)
        if 'write_channels' in protected_config_dict:
            self.position_controller.write_channels = self._split_channels(protected_config_dict['write_channels'])

        if 'read_channels' in protected_config_dict:
            self.position_controller.read_channels = self._split_channels(protected_config_dict['read_channels'])

        self.position_controller.scale_microns_per_volt = protected_config_dict.get('scale_microns_per_volt',
                                                                          self.position_controller.scale_microns_per_volt)
        self.position_controller.zero_microns_volt_offset = protected_config_dict.get('zero_microns_volt_offset',
                                                                          self.position_controller.zero_microns_volt_offset)
        self.position_controller.maximum_allowed_position = protected_config_dict.get('maximum_allowed_position',
                                                                            self.position_controller.maximum_allowed_position)
        self.position_controller.minimum_allowed_position = protected_config_dict.get('minimum_allowed_position',
                                                                            self.position_controller.minimum_allowed_position)
        self.position_controller.settling_time_in_seconds = protected_config_dict.get('settling_time_in_seconds',
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
        write_channels_var = tk.StringVar(value=self._channels_to_str(self.position_controller.write_channels))
        tk.Entry(config_win, textvariable=write_channels_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Read Channels").grid(row=row, column=0)
        read_channels_var = tk.StringVar(value=self._channels_to_str(self.position_controller.read_channels))
        tk.Entry(config_win, textvariable=read_channels_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Scale Microns per Volt (x,y,z)").grid(row=row, column=0)
        scale_microns_per_volt_var = tk.StringVar(value=self._vals_to_str(self.position_controller.scale_microns_per_volt))
        tk.Entry(config_win, textvariable=scale_microns_per_volt_var).grid(row=row, column=1)

        row += 1
        tk.Label(config_win, text="Zero Micron Voltage (x,y,z)").grid(row=row, column=0)
        zero_microns_volt_offset_var = tk.StringVar(value=self._vals_to_str(self.position_controller.zero_microns_volt_offset))
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
            self.configure({k: v.get() for k, v in gui_info.items()})

        # add a button to set the values and close the window
        row += 1
        tk.Button(config_win,
                  text='  Set  ',
                  command=convert_gui_info_and_configure).grid(row=row, column=0)

        tk.Button(config_win,
                  text='Close',
                  command=config_win.destroy).grid(row=row, column=1)
