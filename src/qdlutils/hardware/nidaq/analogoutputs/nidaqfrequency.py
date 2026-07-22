from qdlutils.hardware.nidaq.analogoutputs.nidaqvoltage import NidaqVoltageController

class NidaqFrequencyController(NidaqVoltageController):
    '''
    This class is a minimal frequency controller for laser systems that utilize
    the NIDAQ analog voltage output to control their frequency. It inherits from and 
    utilizes the structure of the base class NidaqVoltageController. This code is
    functionally identical to qdlutils.hardware.nidaq.analogoutputs.nidaqposition
    but with the replacement of position -> frequency and microns -> GHz.

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
    scale_ghz_per_volt : float
        Scaling factor of ghz to volts.
    zero_ghz_volt_offset : float
        Frequency offset at zero volts.
    min_frequency : float
        Minimum frequency in ghz.
    max_frequency : float'
        Maximum frequency in ghz.
    invert_axis : bool 
        If true, inverts the axis by updating `self.scale_ghz_per_volt` and
        `self.zero_ghz_volt_offset` after initialiation and configuration.

    Methods
    -------
    configure(config_dict) -> None
        Loads settings for the controller based off of entries in config_dict with matching
        keys to attributes. If a key is missing the number is not changed.
        Configure has been overwritten for class variable configuration and to recalculate
        the min/max voltages based off the provided frequencies.
    get_current_voltage() -> Float
        Returns the current voltage 
    go_to_voltage(voltage) -> None
        Sets the output voltage to the specfied voltage value.
    validate_value(voltage) -> Bool
        Validates if parameter voltage is within the range specified by min/max voltage.
    _ghz_to_volts() -> float
        Internal method for converting ghz to volts
    _volts_to_ghz() -> float
        Internal method for converting volts to ghz
    get_current_frequency() -> float
        Get the current frequency in ghz
    go_to_frequency(frequency) -> None
        Go to the specified frequency in ghz
    step_frequency(dx) -> None
        Step the current frequency by dx in ghz
    '''

    def __init__(self, 
                 device_name: str = 'Dev1',
                 write_channel: str = 'ao0',
                 read_channel: str = None,
                 move_settle_time: float = 0.0,
                 scale_ghz_per_volt: float=8,
                 zero_ghz_volt_offset: float=5,
                 min_frequency: float = -40.0,
                 max_frequency: float = 40.0,
                 invert_axis: bool = False) -> None:

        self.scale_ghz_per_volt = scale_ghz_per_volt
        self.zero_ghz_volt_offset = zero_ghz_volt_offset
        self.min_frequency = min_frequency
        self.max_frequency = max_frequency
        self.settling_time_in_seconds = move_settle_time
        self.invert_axis = invert_axis

        # Invert the axis if specified by self.modifying scale_ghz_per_volt
        # and self.zero_ghz_volt_offset.
        if self.invert_axis:
            center_frequency = (self.min_frequency + self.max_frequency) / 2
            center_voltage = self._ghz_to_volts(center_frequency)
            self.scale_ghz_per_volt = -self.scale_ghz_per_volt
            self.zero_ghz_volt_offset = center_voltage-(center_frequency/self.scale_ghz_per_volt)

        # Voltage limits in ascending order
        # Depending on the conversion from ghz to volts, the min and max 
        # frequencys and voltages may be flipped relative to each other
        voltage_limits = sorted([self._ghz_to_volts(min_frequency), 
                                 self._ghz_to_volts(max_frequency)])

        # Finially run the parent initialization
        super().__init__(device_name=device_name,
                         write_channel=write_channel,
                         read_channel=read_channel,
                         move_settle_time=move_settle_time,
                         min_voltage=voltage_limits[0],
                         max_voltage=voltage_limits[1])


    def _ghz_to_volts(self, ghz: float) -> float:
        '''
        Internal conversion from a frequency in ghz to volts on the DAQ

        Parameters
        ----------
        ghz : float
            Value in ghz to be converted to volts

        Returns
        -------
        float
            Converted value of frequency in ghz to volts

        '''
        return ghz / self.scale_ghz_per_volt + self.zero_ghz_volt_offset

    def _volts_to_ghz(self, volts: float) -> float:
        '''
        Internal conversion from volts on the DAQ to frequency in ghz

        Parameters
        ----------
        volts : float
            Value in volts to be converted to ghz

        Returns
        -------
        float
            Converted value of voltage in volts to ghz
        '''
        return self.scale_ghz_per_volt * (volts - self.zero_ghz_volt_offset)
    
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
        self.scale_ghz_per_volt = config_dict.get('scale_ghz_per_volt', self.scale_ghz_per_volt)
        self.zero_ghz_volt_offset = config_dict.get('zero_ghz_volt_offset', self.zero_ghz_volt_offset)
        self.min_frequency = config_dict.get('min_frequency', self.min_frequency)
        self.max_frequency = config_dict.get('max_frequency', self.max_frequency)
        self.settling_time_in_seconds = config_dict.get('move_settle_time', self.settling_time_in_seconds)
        self.invert_axis = config_dict.get('invert_axis', self.invert_axis)

        # Invert the axis if specified
        if self.invert_axis:
            center_frequency = (self.min_frequency + self.max_frequency) / 2
            center_voltage = self._ghz_to_volts(center_frequency)
            self.scale_ghz_per_volt = -self.scale_ghz_per_volt
            self.zero_ghz_volt_offset = center_voltage - (center_frequency / self.scale_ghz_per_volt)

        # Get the voltage limits and configure via super
        # Voltage limits in ascending order
        # Depending on the conversion from ghz to volts, the min and max 
        # frequencys and voltages may be flipped relative to each other
        voltage_limits = sorted([self._ghz_to_volts(self.min_frequency), 
                                 self._ghz_to_volts(self.max_frequency)])
        self.min_voltage = voltage_limits[0]
        self.max_voltage = voltage_limits[1]

    def get_current_frequency(self) -> float:
        '''
        This method gets the current frequency in ghz

        Parameters
        ----------
        None

        Returns
        -------
        float
            Current frequency in ghz
        '''
        return self._volts_to_ghz(self.get_current_voltage())
    
    def go_to_frequency(self, frequency: float) -> float:
        '''
        This method the frequencyer to the requested frequency in ghz

        Parameters
        ----------
        frequency : float
            The target frequency in ghz.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If requested frequency corresponds to voltages outside of range.
        '''
        self.go_to_voltage(self._ghz_to_volts(frequency))
        self.last_write_value = frequency
    
    def step_frequency(self, dx: float=None) -> None:
        '''
        Steps the frequency of the frequencyer by dx

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
            If requested frequency corresponds to voltages outside of range.
        '''
        if self.last_write_value is not None:
            try:
                self.go_to_frequency(frequency=self.last_write_value + dx)
            except Exception as e:
                self.logger.warning(e)
        else:
            # Eventually would like to include a step to read in the frequency
            # at this point if read-in was implemented.
            # For now just raise an error.
            raise Exception('No last write value provided, cannot step.')