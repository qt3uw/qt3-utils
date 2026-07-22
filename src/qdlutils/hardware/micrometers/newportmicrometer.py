import serial
import time
import logging


class NewportMicrometer():
    '''
    Controller for Newport automated micrometers via serial port connection
    '''
    def __init__(self,
                 port: str='COM4',
                 min: float=0.0,
                 max: float=25000.0,
                 timeout: float=10):
        '''
        Parameters
        ----------
        port : str
            A string of the communication port on which to open the channel.
        min : float
            Minimum position that the micrometer can be set.
        max : float
            Maximum position that the micrometer can be set.
        timeout: float
            Time in seconds until the controller aborts a movement.

        Notes
        -----
        Specific serial connection properties can be modified in `self.open()`
        '''

        self.port = port
        self.min = min
        self.max = max
        self.timeout = timeout

        self.last_write_value = None
        self.logger = logging.getLogger(__name__)

        self.channel_open = False

    def go_to_position(self, position: float) -> None:

        '''
        Drives the micrometer to a desired position.

        Parameters
        ----------
        position : float
            The target position in micrometers.
        '''
        
        # Check if the requested position is valid
        if self.is_valid_position(position):
            # Encoding needs to be in units of mm
            # Input is provided in units of microns so divide by 1e3
            # Generate the command and write to serial.
            command='1SE'+str(position/1000)+'\r\n'
            self.ser.write(command.encode('utf-8'))
            self.ser.write('SE\r\n'.encode('utf-8'))

            # Response of the micrometers is finite
            # This loop waits for the micrometers to finish movement.
            timeout_clock=0
            moving=True
            while moving:
                # Wait for 0.1 seconds
                time.sleep(0.1)
                # Increment the timeout clock
                timeout_clock+=0.1

                # Check if position is within 0.1 microns of target
                if abs(self.read_position()-position)<0.1:
                    # Break from loop
                    moving=False
                # Check if the movement is timed out
                if (timeout_clock > self.timeout):
                    moving=False
                    self.logger.warning(
                        f'Micrometer movement timed out at {self.read_position():.2f}' 
                        + f' after {timeout_clock:.2f}s en route to {position:.2f}.')
                    
            self.last_write_value = self.read_position()
            
        else:
            # Raise value error if the requested position is invalid.
            error_message = f'Requested position {position} is out of bounds.'
            raise ValueError(error_message)


    def read_position(self) -> float:
        '''
        Read the position of the micrometer.

        Returns
        -------
        position: float
            Read position in micrometers.
        '''
        # Get the read command and write to serial
        command='1TP\r\n'
        self.ser.write(command.encode('utf-8'))

        # Read the result and cast to float
        # The first 3 characters of the string are discarded
        raw=self.ser.readline()
        return float(raw[3:12]) * 1000
    

    def step_position(self, dx: float) -> None:
        '''
        Steps the micrometers dx steps along axis

        Parameters
        ----------
        dx: float
            Step size in micrometers to move (can be positive or negative)
        '''
        if self.last_write_value is None:
            self.last_write_value = self.read_position()

        self.go_to_position(position = self.last_write_value + dx)


    def open(self) -> None:
        '''
        Opens a serial connection to the micrometer.
        '''
        self.ser = serial.Serial(
            port=self.port,
            baudrate=921600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            xonxoff=True
        )
        #Initialization
        #Emter configuration state
        self.ser.write('1PW1\r\n'.encode('utf-8'))
        #HT Set Home Search type
        self.ser.write('1HT\r\n'.encode('utf-8'))
        #BA Set backlash compensation
        self.ser.write('1BA0.003\r\n'.encode('utf-8'))
        #Set friction compensation
        self.ser.write('1FF05\r\n'.encode('utf-8'))
        #Leave configuration state
        self.ser.write('1PW0\r\n'.encode('utf-8'))
        #Execute Home Search, needed before controller can move
        self.ser.write('1OR\r\n'.encode('utf-8'))

        self.channel_open = True

    def close(self) -> None:
        '''
        Closes the serial connection to micrometer.
        '''
        # Send the close command to serial
        self.ser.write('SE\r\n'.encode('utf-8'))
        self.ser.close()

        self.channel_open = False

    def configure(self, config_dict: dict) -> None:
        '''
        This method is used to configure the data controller.

        Parameters
        ----------
        config_dict: float
            Dictionary containing parameter value pairs to initialize 
            the micrometer.
        '''
        self.port = config_dict.get('port', self.port)
        self.min = config_dict.get('min', self.min)
        self.max = config_dict.get('max', self.max)
        self.timeout = config_dict.get('timeout', self.timeout)
        # Open a serial connection
        self.open()


    def is_valid_position(self, value):
        '''
        Validates if value is within the allowed range

        Parameters
        ----------
        value: float, int
            Checks if the value is within the range of the micrometer.
        '''
        return (value >= self.min) and (value <= self.max)
    