import importlib
import importlib.resources
import logging

import tkinter as tk
import yaml

from qdlutils.applications.qdlmove.application_gui import (
    PositionControllerApplicationView, 
    TwoAxisApplicationView, 
    ThreeAxisApplicationView
    )
from qdlutils.applications.qdlmove.application_controller import MovementController

from qdlutils.hardware.micrometers.newportmicrometer import NewportMicrometer
from qdlutils.hardware.nidaq.analogoutputs.nidaqposition import NidaqPositionController


logger = logging.getLogger(__name__)
logging.basicConfig()


CONFIG_PATH = 'qdlutils.applications.qdlmove.config_files'
DEFAULT_CONFIG_FILE = 'qdlmove_base.yaml'


class PositionControllerApplication():
    '''
    The main position controller application logic which coordinates the GUI inputs with
    the `application_controller` backend.

    Users who wish to customize or add new position controllers to their system should
    edit this file in the designated regions, following directions in both this and
    `qdlmove.application_gui` respectively.

    Individual movement controllers are separated into two-, and three-axis versions
    which handle different subsets of the axes. These both act identically and can be
    instantiated multiple times to handle any number of movement controllers.
    Currently only the `newportmicrometer` and `nidaqpiezo` are supported, however you 
    should be able to easily add other hardware types.
    '''

    def __init__(self, default_config_filename: str, is_root_process: bool):
        
        # Boolean if the function is the root or not, determines if the application is
        # intialized via tk.Tk or tk.Toplevel
        self.is_root_process = is_root_process

        self.positioners = {}
        self.application_controller = None

        # Load the YAML configuration file
        self.load_yaml_from_name(yaml_filename=default_config_filename)

        # Start application
        if self.is_root_process:
            self.root = tk.Tk()
        else:
            self.root = tk.Toplevel()
        # Launch the GUI
        self.view = PositionControllerApplicationView(main_window = self.root)
        # Load the application controller
        self.application_controller = MovementController(positioners = self.positioners)

        # ===============================================================================
        # Edit here to add more controllers
        # ===============================================================================
        
        # 1. FIRST MAKE EDITS IN `application_gui.py`.

        # 3. CREATE A CONTROLLER FOR YOUR STAGE:
        # Names must match the relevant entries in the YAML configuration file
        # This creates a controller for the specified axes
        # Edit the relevant section in `application_gui.py` to change the names
        # Make sure to pass the right application GUI to the `gui` argument below
        # self.micros_application = TwoAxisApplicationControl(
        #                             parent=self, 
        #                             gui=self.view.micros_view, 
        #                             axis_1_controller_name='MicroX', 
        #                             axis_2_controller_name='MicroY',
        #                             read_precision=0)
        self.piezos_application = ThreeAxisApplicationControl(
                                    parent=self, 
                                    gui=self.view.piezos_view, 
                                    axis_1_controller_name='PiezoX', 
                                    axis_2_controller_name='PiezoY',
                                    axis_3_controller_name='PiezoZ',
                                    read_precision=2)
        
        # 4. ADD THOSE CONTROLLERS TO THIS LIST
        # This list is used to keep track of the controllers to ensure that the stepping
        # does not overlap.
        self.movement_controllers = [#self.micros_application,
                                     self.piezos_application,]
        
        # 5. ADD LOGIC FOR NEW TYPES OF HARDWARE
        # If you are using new hardware types (i.e. not `nidaqpizeo` or 
        # `newportmicrometer`) then you need to add logic for their start up to the 
        # `__init__` methods of TwoAxisApplicationControl and ThreesAxisApplicationControl

        # ===============================================================================
        # No edits below here!
        # ===============================================================================
        
        # Set the focus to the root when hitting enter
        self.root.bind('<Return>', self.refocus)

    def configure_from_yaml(self, afile: str) -> None:
        '''
        This method loads a YAML file to configure the qdlmove hardware
        based on yaml file indicated by argument `afile`.

        This method constructs the positioners and configures them, then
        stores them in a dictionary which is saved in the application.
        '''
        with open(afile, 'r') as file:
            # Log selection
            logger.info(f"Loading settings from: {afile}")
            # Get the YAML config as a nested dict
            config = yaml.safe_load(file)

        # First we get the top level application name
        APPLICATION_NAME = list(config.keys())[0]

        # Get the names of the positioners as a list
        positioner_names = list(config[APPLICATION_NAME]['Positioners'])

        # For each positioner, get the class constructor, instantiate, then configure
        for positioner_name in positioner_names:

            # Get the path and the name of the class
            import_path = config[APPLICATION_NAME][positioner_name]['import_path']
            class_name = config[APPLICATION_NAME][positioner_name]['class_name']
            #Load the class
            module = importlib.import_module(import_path)
            logger.debug(f"Importing {import_path}")
            # Get the class constructor
            constructor = getattr(module, class_name)
            # Instantiate a positioner class and configure it
            positioner = constructor()
            positioner.configure(config[APPLICATION_NAME][positioner_name]['configure'])
            # Save to positioners dictionary
            self.positioners[positioner_name] = positioner


    def load_yaml_from_name(self, yaml_filename: str) -> None:
        '''
        Loads the default yaml configuration file for the application controller.

        Should be called during instantiation of this class and should be the callback
        function for the support controller pull-down menu in the side panel
        '''
        yaml_path = importlib.resources.files(CONFIG_PATH).joinpath(yaml_filename)
        self.configure_from_yaml(str(yaml_path))

    def refocus(self, tkinter_event=None):
        '''
        This method is called when the enter key is hit.
        This resets the focus of the application onto the root window removing the
        cursor from any entry widgets, enabling movement with keys without unintended
        input into the entry widgets.
        '''
        logger.debug('Refocus triggered.')
        if tkinter_event.keysym == 'Return':
            logger.debug('Refocused successfully.')
            self.root.focus_set()


    def run(self) -> None:
        '''
        This function launches the application itself.
        '''
        # Set the title of the app window
        self.root.title("qdlmove")
        # Display the window (not in task bar)
        self.root.deiconify()
        # Launch the main loop if root
        if self.is_root_process:
            self.root.mainloop()



class TwoAxisApplicationControl():
    '''
    Application controller for two axis movement
    '''

    def __init__(self,
                 parent: PositionControllerApplication,
                 gui: TwoAxisApplicationView,
                 axis_1_controller_name: str,
                 axis_2_controller_name: str, 
                 read_precision: int=1):
        
        # Save the controller names for each axis
        self.parent = parent
        self.gui = gui
        self.axis_1_controller_name = axis_1_controller_name
        self.axis_2_controller_name = axis_2_controller_name
        self.read_precision = read_precision

        # Bind keys to the parent application view
        self.gui.stepping_laser_toggle.config(command=self.toggle_stepping)
        self.gui.axis_1_set_button.bind("<Button>", self.set_axis_1)
        self.gui.axis_2_set_button.bind("<Button>", self.set_axis_2)

        # On startup the last write value of the positioners cannot generally be obtained
        # Unfortunately NIDAQ does not enable to to know the current set voltage of an AO
        # channel, but the serial micros enable readout of the current position.
        # Unfortunately, this means that stepping and the GUI readout is generally broken 
        # on startup. Thus we do some logic here to force an update on each of the axes.
        # (there is probably a cleaner way of doing this).
        # For each axis we check for the type of instance and then force an update depending
        # on the type of hardware...
        # If axis 1 is an NidaqPositionController...
        if isinstance(self.parent.positioners[self.axis_1_controller_name], NidaqPositionController):
            # Initialize the value to zero on start up
            # Initial value in GUI for step is zero so setting the axis sets it to zero
            self.set_axis_1()
        # If axis 1 is a NewportMicrometer
        if isinstance(self.parent.positioners[self.axis_1_controller_name], NewportMicrometer):
            # Annoyingly we need to read the current position directly, place it in the GUI,
            # then set the position.
            current_position = round(self.parent.positioners[self.axis_1_controller_name].read_position(),self.read_precision)
            # Set the entry in the gui
            self.gui.axis_1_set_entry.insert(0, current_position)
            # Set the gui position
            self.set_axis_1()
        # Repeat for axis 2
        if isinstance(self.parent.positioners[self.axis_2_controller_name], NidaqPositionController):
            self.set_axis_2()
        if isinstance(self.parent.positioners[self.axis_2_controller_name], NewportMicrometer):
            current_position = round(self.parent.positioners[self.axis_2_controller_name].read_position(),self.read_precision)
            self.gui.axis_2_set_entry.insert(0, current_position)
            self.set_axis_2()
        # ===============================================================================
        # Add more startup logic for new controllers here if needed
        # ===============================================================================

    def toggle_stepping(self):
        '''
        Callback for when the toggle checkbox is clicked.
        Sets enables or disables stepping depending on the state.
        '''
        # Check if the checkbox is checked in the GUI
        if (self.gui.stepping_active.get() == 1):
            # Disable the other stepping checkboxes if they are active
            for controller in self.parent.movement_controllers:
                if controller is not self and (controller.gui.stepping_active.get()==1):
                    # Uncheck the box
                    controller.gui.stepping_active.set(0)
                    # Toggle the stepping
                    controller.toggle_stepping()
            # Bind the keys to root
            self.parent.root.bind('<Left>', self.step_axis_1)
            self.parent.root.bind('<Right>', self.step_axis_1)
            self.parent.root.bind('<Up>', self.step_axis_2)
            self.parent.root.bind('<Down>', self.step_axis_2)
            logger.info('Stepping active.')
        else:
            # Unbind all events tied to the root window
            # except for the return key refocus
            for event in self.parent.root.bind():
                if event != '<Key-Return>':
                    self.parent.root.unbind(event)
            logger.info('Stepping inactive.')


    # Call back functions for setting x,y positions and 
    def set_axis_1(self, tkinter_event=None):
        '''
        Moves the axis 1 position to the value specified in the GUI
        '''
        # Get the position from the GUI element
        position = float(self.gui.axis_1_set_entry.get())
        # Set the axis
        self.parent.application_controller.move_axis(
            axis_controller_name=self.axis_1_controller_name, 
            position=position)
        # Update the reader
        self.gui.axis_1_readout_entry.config(state='normal')     
        self.gui.axis_1_readout_entry.delete(0,'end')
        self.gui.axis_1_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_1_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_1_readout_entry.config(state='readonly')

    
    def set_axis_2(self, tkinter_event=None):
        '''
        Moves the axis 2 position to the value specified in the GUI
        '''
        # Get the position from the GUI element
        position = float(self.gui.axis_2_set_entry.get())
        # Set the axis
        self.parent.application_controller.move_axis(axis_controller_name=self.axis_2_controller_name, position=position)
        # Update the reader
        self.gui.axis_2_readout_entry.config(state='normal')     
        self.gui.axis_2_readout_entry.delete(0,'end')
        self.gui.axis_2_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_2_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_2_readout_entry.config(state='readonly')

    def step_axis_1(self, tkinter_event=None):
        '''
        Steps the axis 1 position by the value specified in the GUI
        with direction dependent on the key press
        '''
        #if self.stepping_active:
        # Get the position from the GUI element
        dx = float(self.gui.axis_1_step_entry.get())
        # Set the axis
        if tkinter_event.keysym == 'Left':
            logger.info(f'Moving Axis 1 left by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_1_controller_name, dx=-dx)
        elif tkinter_event.keysym == 'Right':
            logger.info(f'Moving Axis 1 right by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_1_controller_name, dx=dx)
        else:
            logger.warning('Axis 1 step key not identified')
        # Update the reader
        self.gui.axis_1_readout_entry.config(state='normal')     
        self.gui.axis_1_readout_entry.delete(0,'end')
        self.gui.axis_1_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_1_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_1_readout_entry.config(state='readonly')
    
    def step_axis_2(self, tkinter_event=None):
        '''
        Steps the axis 2 position by the value specified in the GUI
        with direction dependent on the key press
        '''
        #if self.stepping_active:
        # Get the position from the GUI element
        dx = float(self.gui.axis_2_step_entry.get())
        # Set the axis
        if tkinter_event.keysym == 'Down':
            logger.info(f'Moving Axis 2 down by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_2_controller_name, dx=-dx)
        elif tkinter_event.keysym == 'Up':
            logger.info(f'Moving Axis 2 up by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_2_controller_name, dx=dx)
        else:
            logger.warning('Axis 2 step key not identified')
        # Update the reader
        self.gui.axis_2_readout_entry.config(state='normal')     
        self.gui.axis_2_readout_entry.delete(0,'end')
        self.gui.axis_2_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_2_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_2_readout_entry.config(state='readonly')

    

class ThreeAxisApplicationControl():
    '''
    Application controller for three axis movement
    '''

    def __init__(self,
                 parent: PositionControllerApplication,
                 gui: ThreeAxisApplicationView,
                 axis_1_controller_name: str,
                 axis_2_controller_name: str, 
                 axis_3_controller_name: str, 
                 read_precision: int=1):
        
        # Save the controller names for each axis
        self.parent = parent
        self.gui = gui
        self.axis_1_controller_name = axis_1_controller_name
        self.axis_2_controller_name = axis_2_controller_name
        self.axis_3_controller_name = axis_3_controller_name
        self.read_precision = read_precision

        # Bind buttons
        self.gui.stepping_laser_toggle.config(command=self.toggle_stepping)
        self.gui.axis_1_set_button.bind("<Button>", self.set_axis_1)
        self.gui.axis_2_set_button.bind("<Button>", self.set_axis_2)
        self.gui.axis_3_set_button.bind("<Button>", self.set_axis_3)

        # Initialize the GUI entries depending on the type of controller
        # See the TwoAxisApplicationController code for comments.
        if isinstance(self.parent.positioners[self.axis_1_controller_name], NidaqPositionController):
            self.set_axis_1()
        if isinstance(self.parent.positioners[self.axis_1_controller_name], NewportMicrometer):
            current_position = round(self.parent.positioners[self.axis_1_controller_name].read_position(),self.read_precision)
            self.gui.axis_1_set_entry.insert(0, current_position)
            self.set_axis_1()
        if isinstance(self.parent.positioners[self.axis_2_controller_name], NidaqPositionController):
            self.set_axis_2()
        if isinstance(self.parent.positioners[self.axis_2_controller_name], NewportMicrometer):
            current_position = round(self.parent.positioners[self.axis_2_controller_name].read_position(),self.read_precision)
            self.gui.axis_2_set_entry.insert(0, current_position)
            self.set_axis_2()
        if isinstance(self.parent.positioners[self.axis_3_controller_name], NidaqPositionController):
            self.set_axis_3()
        if isinstance(self.parent.positioners[self.axis_3_controller_name], NewportMicrometer):
            current_position = round(self.parent.positioners[self.axis_3_controller_name].read_position(),self.read_precision)
            self.gui.axis_3_set_entry.insert(0, current_position)
            self.set_axis_3()
        # ===============================================================================
        # Add more startup logic for new controllers here if needed
        # ===============================================================================

    def toggle_stepping(self):
        '''
        Callback for when the toggle checkbox is clicked.
        Sets enables or disables stepping depending on the state.
        '''
        if (self.gui.stepping_active.get() == 1):
            # Disable the other stepping checkboxes if they are active
            for controller in self.parent.movement_controllers:
                if controller is not self and (controller.gui.stepping_active.get() == 1):
                    # Uncheck the box
                    controller.gui.stepping_active.set(0)
                    # Toggle the stepping
                    controller.toggle_stepping()
            # Bind the keys to root
            self.parent.root.bind('<Left>', self.step_axis_1)
            self.parent.root.bind('<Right>', self.step_axis_1)
            self.parent.root.bind('<Up>', self.step_axis_2)
            self.parent.root.bind('<Down>', self.step_axis_2)
            # For the third axis, allow for '=' or '+' to zoom since numpad has '+'
            self.parent.root.bind('<=>', self.step_axis_3)
            self.parent.root.bind('<+>', self.step_axis_3)
            self.parent.root.bind('<minus>', self.step_axis_3)
            logger.info('Stepping active.')
        else:
            # Unbind all events tied to the root window except for the return key refocus
            for event in self.parent.root.bind():
                if event != '<Key-Return>':
                    self.parent.root.unbind(event)
            logger.info('Stepping inactive.')


    # Call back functions for setting x,y positions and 
    def set_axis_1(self, tkinter_event=None):
        '''
        Moves the axis 1 position to the value specified in the GUI
        '''
        # Get the position from the GUI element
        position = float(self.gui.axis_1_set_entry.get())
        # Set the axis
        self.parent.application_controller.move_axis(
            axis_controller_name=self.axis_1_controller_name, 
            position=position)
        # Update the reader
        self.gui.axis_1_readout_entry.config(state='normal')     
        self.gui.axis_1_readout_entry.delete(0,'end')
        self.gui.axis_1_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_1_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_1_readout_entry.config(state='readonly')

    
    def set_axis_2(self, tkinter_event=None):
        '''
        Moves the axis 2 position to the value specified in the GUI
        '''
        # Get the position from the GUI element
        position = float(self.gui.axis_2_set_entry.get())
        # Set the axis
        self.parent.application_controller.move_axis(
            axis_controller_name=self.axis_2_controller_name, position=position)
        # Update the reader
        self.gui.axis_2_readout_entry.config(state='normal')     
        self.gui.axis_2_readout_entry.delete(0,'end')
        self.gui.axis_2_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_2_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_2_readout_entry.config(state='readonly')

    def set_axis_3(self, tkinter_event=None):
        '''
        Moves the axis 3 position to the value specified in the GUI
        '''
        # Get the position from the GUI element
        position = float(self.gui.axis_3_set_entry.get())
        # Set the axis
        self.parent.application_controller.move_axis(
            axis_controller_name=self.axis_3_controller_name, position=position)
        # Update the reader
        self.gui.axis_3_readout_entry.config(state='normal')     
        self.gui.axis_3_readout_entry.delete(0,'end')
        self.gui.axis_3_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_3_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_3_readout_entry.config(state='readonly')

    def step_axis_1(self, tkinter_event=None):
        '''
        Steps the axis 1 position by the value specified in the GUI
        with direction dependent on the key press
        '''
        #if self.stepping_active:
        # Get the position from the GUI element
        dx = float(self.gui.axis_1_step_entry.get())
        # Set the axis
        if tkinter_event.keysym == 'Left':
            logger.info(f'Moving Axis 1 left by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_1_controller_name, dx=-dx)
        elif tkinter_event.keysym == 'Right':
            logger.info(f'Moving Axis 1 right by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_1_controller_name, dx=dx)
        else:
            logger.warning('Axis 1 step key not identified')
        # Update the reader
        self.gui.axis_1_readout_entry.config(state='normal')     
        self.gui.axis_1_readout_entry.delete(0,'end')
        self.gui.axis_1_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_1_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_1_readout_entry.config(state='readonly')
    
    def step_axis_2(self, tkinter_event=None):
        '''
        Steps the axis 2 position by the value specified in the GUI
        with direction dependent on the key press
        '''
        #if self.stepping_active:
        # Get the position from the GUI element
        dx = float(self.gui.axis_2_step_entry.get())
        # Set the axis
        if tkinter_event.keysym == 'Down':
            logger.info(f'Moving Axis 2 down by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_2_controller_name, dx=-dx)
        elif tkinter_event.keysym == 'Up':
            logger.info(f'Moving Axis 2 up by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_2_controller_name, dx=dx)
        else:
            logger.warning('Axis 2 step key not identified')
        # Update the reader
        self.gui.axis_2_readout_entry.config(state='normal')     
        self.gui.axis_2_readout_entry.delete(0,'end')
        self.gui.axis_2_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_2_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_2_readout_entry.config(state='readonly')

    def step_axis_3(self, tkinter_event=None):
        '''
        Steps the axis 3 position by the value specified in the GUI
        with direction dependent on the key press
        '''
        #if self.stepping_active:
        # Get the position from the GUI element
        dx = float(self.gui.axis_3_step_entry.get())
        # Set the axis
        if tkinter_event.keysym == 'minus':
            logger.info(f'Moving Axis 3 down by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_3_controller_name, dx=-dx)
        elif tkinter_event.char == '=' or tkinter_event.char == '+':
            logger.info(f'Moving Axis 3 up by {dx}')
            self.parent.application_controller.step_axis(axis_controller_name=self.axis_3_controller_name, dx=dx)
        else:
            logger.warning('Axis 3 step key not identified')
        # Update the reader
        self.gui.axis_3_readout_entry.config(state='normal')     
        self.gui.axis_3_readout_entry.delete(0,'end')
        self.gui.axis_3_readout_entry.insert(
            0,round(self.parent.application_controller.positioners[self.axis_3_controller_name].last_write_value,
                    self.read_precision))
        self.gui.axis_3_readout_entry.config(state='readonly')


def main(is_root_process=True):
    tkapp = PositionControllerApplication(
        default_config_filename=DEFAULT_CONFIG_FILE,
        is_root_process=is_root_process)
    tkapp.run()


if __name__ == '__main__':
    main()
