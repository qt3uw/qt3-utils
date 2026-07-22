from typing import Optional

from .nidaqvoltage import NidaqVoltageController

class NidaqPositionController(NidaqVoltageController):
    '''
    This class is a minimal position controller for hardware positioners that utilize
    the NIDAQ analog voltage output to control their position. It inherits from and 
    utilizes the structure of the base class NidaqVoltageController.

    Attributes
    ----------
    logger : logging.Logger
        A logging.Logger instantiation for writing log results to the terminal.
    device_name : Str
        Name of the NIDAQ device name to communicate with.
    write_channel : Str
        Which channel of the NIDAQ device to write instructions to.
    read_channel : Str
        Which NIDAQ analog input channel to read input from.
    minimum_allowed_voltage : Float
        Minimum allowed voltage for the specific instantiation of the controller.
        Note that this is distinct from the hardware-limited minimum voltage (which
        is a property of the DAQ itself) and this value should be kept within such
        limits during operation.
    maximum_allowed_voltage : Float
        Maximum allowed voltage for the specific instantiation of the controller.
        Note that this is distinct from the hardware-limited maximum voltage (which
        is a property of the DAQ itself) and this value should be kept within such
        limits during operation.
    settling_time_in_seconds : Float
        Determines how many seconds the DAQ pauses after each write command to
        allow for the hardware being controlled to settle.
    last_write_value : Float
        Internal value which tracks the last value written to the DAQ channel.
        On initialization it is set to None.
    scale_microns_per_volt : float
        Scaling factor of microns to volts.
    zero_microns_volt_offset : float
        Position offset at zero volts.
    min_position : float
        Minimum position in microns.
    max_position : float'
        Maximum position in microns.
    invert_axis : bool 
        If true, inverts the axis by updating `self.scale_microns_per_volt` and
        `self.zero_microns_volt_offset` after initialiation and configuration.

    Methods
    -------
    configure(config_dict) -> None
        Loads settings for the controller based off of entries in config_dict with matching
        keys to attributes. If a key is missing the number is not changed.
        Configure has been overwritten for class variable configuration and to recalculate
        the min/max voltages based off the provided positions.
    get_current_voltage() -> Float
        Returns the current voltage 
    go_to_voltage(voltage) -> None
        Sets the output voltage to the specfied voltage value.
    validate_value(voltage) -> Bool
        Validates if parameter voltage is within the range specified by min/max voltage.
    _microns_to_volts() -> float
        Internal method for converting microns to volts
    _volts_to_microns() -> float
        Internal method for converting volts to microns
    get_current_position() -> float
        Get the current position in microns
    go_to_position(position) -> None
        Go to the specified position in microns
    step_position(dx) -> None
        Step the current position by dx in microns
    '''

    def __init__(self, 
                 device_name: str = 'Dev1',
                 write_channel: str = 'ao0',
                 read_channel: str = None,
                 move_settle_time: float = 0.0,
                 scale_microns_per_volt: float=8,
                 zero_microns_volt_offset: float=0,
                 min_position: float = -40.0,
                 max_position: float = 40.0,
                 invert_axis: bool = False) -> None:

        self.scale_microns_per_volt = scale_microns_per_volt
        self.zero_microns_volt_offset = zero_microns_volt_offset
        self.min_position = min_position
        self.max_position = max_position
        self.settling_time_in_seconds = move_settle_time
        self.invert_axis = invert_axis
        self._last_position_microns = None  # Last commanded position (µm); independent of MON readback

        # Invert the axis if specified by self.modifying scale_microns_per_volt
        # and self.zero_microns_volt_offset.
        if self.invert_axis:
            center_position = (self.min_position + self.max_position) / 2
            center_voltage = self._microns_to_volts(center_position)
            self.scale_microns_per_volt = -self.scale_microns_per_volt
            self.zero_microns_volt_offset = center_voltage-(center_position/self.scale_microns_per_volt)

        # Voltage limits in ascending order
        # Depending on the conversion from microns to volts, the min and max 
        # positions and voltages may be flipped relative to each other
        voltage_limits = sorted([self._microns_to_volts(min_position), 
                                 self._microns_to_volts(max_position)])

        # Finially run the parent initialization
        super().__init__(device_name=device_name,
                         write_channel=write_channel,
                         read_channel=read_channel,
                         move_settle_time=move_settle_time,
                         min_voltage=voltage_limits[0],
                         max_voltage=voltage_limits[1])


    def _microns_to_volts(self, microns: float) -> float:
        '''
        Internal conversion from a position in microns to volts on the DAQ

        Parameters
        ----------
        microns : float
            Value in microns to be converted to volts

        Returns
        -------
        float
            Converted value of position in microns to volts

        '''
        return microns / self.scale_microns_per_volt + self.zero_microns_volt_offset

    def _volts_to_microns(self, volts: float) -> float:
        '''
        Internal conversion from volts on the DAQ to position in microns

        Parameters
        ----------
        volts : float
            Value in volts to be converted to microns

        Returns
        -------
        float
            Converted value of voltage in volts to microns
        '''
        return self.scale_microns_per_volt * (volts - self.zero_microns_volt_offset)
    
    def configure(self, config_dict: dict) -> None:
        '''
        This method configures the controller based off of matching keys in
        config_dict. If a key is not present the value remains unchanged.

        Parameters
        ----------
        config_dict : dict
            A dictionary whose keys can contain the attributes of this class.
            If a key matches the corresponding attribute is updated to the
            corresponding value in config_dict.

        Returns
        -------
        None
        '''
        self.device_name = config_dict.get('device_name', self.device_name)
        self.write_channel = config_dict.get('write_channel', self.write_channel)
        self.read_channel = config_dict.get('read_channel', self.read_channel)
        self.scale_microns_per_volt = config_dict.get('scale_microns_per_volt', self.scale_microns_per_volt)
        self.zero_microns_volt_offset = config_dict.get('zero_microns_volt_offset', self.zero_microns_volt_offset)
        self.min_position = config_dict.get('min_position', self.min_position)
        self.max_position = config_dict.get('max_position', self.max_position)
        self.settling_time_in_seconds = config_dict.get('move_settle_time', self.settling_time_in_seconds)
        self.invert_axis = config_dict.get('invert_axis', self.invert_axis)

        # Invert the axis if specified
        if self.invert_axis:
            center_position = (self.min_position + self.max_position) / 2
            center_voltage = self._microns_to_volts(center_position)
            self.scale_microns_per_volt = -self.scale_microns_per_volt
            self.zero_microns_volt_offset = center_voltage - (center_position / self.scale_microns_per_volt)

        # Get the voltage limits and configure via super
        # Voltage limits in ascending order
        # Depending on the conversion from microns to volts, the min and max 
        # positions and voltages may be flipped relative to each other
        voltage_limits = sorted([self._microns_to_volts(self.min_position), 
                                 self._microns_to_volts(self.max_position)])
        self.min_voltage = voltage_limits[0]
        self.max_voltage = voltage_limits[1]

    def has_last_position(self) -> bool:
        '''True if the user has set a position at least once (so "Current" is known).'''
        return self._last_position_microns is not None

    def get_last_commanded_position(self) -> Optional[float]:
        '''Last position commanded via go_to_position / step_position (µm), or None. Never reads MON.'''
        return self._last_position_microns

    def get_current_position(self) -> float:
        '''
        Returns position (µm), preferring MON readback when read_channel is configured.

        For UI that should track commanded position instead of inaccurate read channels,
        use get_last_commanded_position().
        '''
        if self.read_channel is not None:
            try:
                v = self.get_current_voltage()
                return self._volts_to_microns(v)
            except Exception:
                pass
        if self._last_position_microns is not None:
            return self._last_position_microns
        try:
            v = self.get_current_voltage()
            return self._volts_to_microns(v)
        except Exception:
            return self.min_position if self.min_position is not None else 0.0

    def go_to_position(self, position: float) -> float:
        '''
        This method the positioner to the requested position in microns

        Parameters
        ----------
        position : float
            The target position in microns.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If requested position corresponds to voltages outside of range.
        '''
        self.go_to_voltage(self._microns_to_volts(position))
        self._last_position_microns = position

    def step_position(self, dx: float=None) -> None:
        '''
        Steps the position of the positioner by dx

        Parameters
        ----------
        dx : float
            The step size; can be positive or negative.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If requested position corresponds to voltages outside of range.
        '''
        base_um = self._last_position_microns
        if base_um is None and self.last_write_value is not None:
            base_um = self._volts_to_microns(self.last_write_value)
        if base_um is not None:
            try:
                self.go_to_position(position=base_um + dx)
            except Exception as e:
                self.logger.warning(e)
        else:
            raise Exception('No last position available, cannot step.')   