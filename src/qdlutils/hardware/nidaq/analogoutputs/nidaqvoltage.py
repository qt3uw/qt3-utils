import logging
import nidaqmx
import time


class NidaqVoltageController:
    '''
    This class represents a base controller for NIDAQ analog output voltage
    control. This base class provides the base structure for other analog output
    controllers such as those for positioning and wavelength control, provided
    there is a well-defined relationship between the external quantity (e.g. position)
    and the internal voltage value.

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
    min_voltage : Float
        Minimum allowed voltage for the specific instantiation of the controller.
        Note that this is distinct from the hardware-limited minimum voltage (which
        is a property of the DAQ itself) and this value should be kept within such
        limits during operation.
    max_voltage : Float
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

    Methods
    -------
    configure(config_dict) -> None
        Loads settings for the controller based off of entries in config_dict with matching
        keys to attributes. If a key is missing the number is not changed.
    get_current_voltage() -> Float
        Returns the current voltage 
    go_to_voltage(voltage) -> None
        Sets the output voltage to the specfied voltage value.
    validate_value(voltage) -> Bool
        Validates if parameter voltage is within the range specified by min/max voltage.

    Notes
    -----
    This base class can either be copied and modified or inherited from in order to create
    NIDAQ analog output controllers for other hardware.
    To implement an inherited class, create private methods to convert between the external
    unit (e.g. position, wavelength) and the internal unit (voltage) and vice versa.
    Then in the __init__() call of your child class, call super().__init__(*args) to set
    the voltage parameters. You can then make wrapper functions which call the 
    NidaqVoltageController.get_current_voltage() and .go_to_voltage() methods passing or
    returning values converted to and from the external quantity respectively.
    Also you will need to overwrite the self.configure() method to update the specific
    parameters for the child class.
    '''

    def __init__(self, 
                 device_name: str = 'Dev1',
                 write_channel: str = 'ao0',
                 read_channel: str = None,
                 move_settle_time: float = 0.0,
                 min_voltage: float = -5.0,
                 max_voltage: float = 5.0) -> None:

        self.logger = logging.getLogger(__name__)
        self.device_name = device_name
        self.write_channel = write_channel
        self.read_channel = read_channel
        self.min_voltage = min_voltage
        self.max_voltage = max_voltage
        self.settling_time_in_seconds = move_settle_time
        self.last_write_value = None

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
        self.device_name = config_dict.get('daq_name', self.device_name)
        self.write_channel = config_dict.get('write_channels', self.write_channel)
        self.read_channel = config_dict.get('read_channels', self.read_channel)
        self.min_voltage = config_dict.get('min_voltage', self.min_voltage)
        self.max_voltage = config_dict.get('max_voltage', self.max_voltage)

    def get_current_voltage(self) -> float:
        '''
        Returns the voltage supplied to the three input analog channels.
        If no input analog channels were provided when objected was created,
        attempts to return the last write value. If no write value was set,
        raises a value error.

        Parameters
        ----------
        None

        Returns
        -------
        current_voltage : float
            The current voltage of the DAQ.
        
        Raises
        ------
            ValueError
                If no read channels were supplied and no voltage was written.
        '''
        if self.read_channel is not None:
            with nidaqmx.Task() as vread, nidaqmx.Task():
                vread.ai_channels.add_ai_voltage_chan(self.device_name + '/' + self.read_channel, min_val=0, max_val=10.0)
                current_voltage = vread.read()
        elif self.last_write_value is not None:
            current_voltage = self.last_write_value
        else:
            raise ValueError('An input channel not provided and no value has been written to channel yet.')
        return current_voltage

    def go_to_voltage(self, voltage: float = None) -> None:
        '''
        Sets the voltage on the DAQ channel.

        Parameters
        ----------
        Voltage : float
            The voltage to write to the DAQ channel

        Returns
        -------
        None
        
        Raises
        ------
            ValueError
                If requested voltage is out of bounds.
        '''
        if voltage is not None:
            # Validate the voltage
            self.validate_value(voltage)
            # Open an nidaq task and write the voltage to the channel
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(self.device_name + '/' + self.write_channel)
                task.write(voltage)
                # Save the last write value
                self.last_write_value = voltage
        # Wait at new position if desired
        if self.settling_time_in_seconds > 0:
            time.sleep(self.settling_time_in_seconds)
        # Log value
        self.logger.debug(f'Moved controller to {self.last_write_value}')

    def validate_value(self, voltage: float) -> None:
        '''
        Verifies if the provided voltage is within bounds.

        Parameters
        ----------
        Voltage : float
            The voltage to validate.

        Returns
        -------
        None
        
        Raises
        ------
            ValueError
                If requested voltage is out of bounds or of invalid type
        '''
        try:
            voltage = float(voltage)
        except:
            raise TypeError(f'value {voltage} is not a valid type.')
        if voltage < self.min_voltage:
            raise ValueError(f'value {voltage} is less than {self.min_voltage: .3f}.')
        if voltage > self.max_voltage:
            raise ValueError(f'value {voltage} is greater than {self.max_voltage: .3f}.')
