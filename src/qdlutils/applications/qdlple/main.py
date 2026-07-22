import importlib
import importlib.resources
import logging
import datetime
import h5py
from threading import Thread

import matplotlib

import nidaqmx
import numpy as np
import tkinter as tk
import yaml

import qdlutils
from qdlutils.applications.qdlple.application_gui import (
    MainApplicationView,
    ScanPopoutApplicationView,
)
from qdlutils.hardware.nidaq.counters.nidaqtimedratecounter import NidaqTimedRateCounter

matplotlib.use('Agg')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CONFIG_PATH = 'qdlutils.applications.qdlple.config_files'
DEFAULT_CONFIG_FILE = 'qdlple_base.yaml'


class MainTkApplication():
    '''
    Main application backend, launches the GUI and handles events
    '''
    def __init__(self, default_config_filename: str, is_root_process: bool) -> None:
        '''
        Initializes the application.
        Args:
            controller_name (str) : name of controller used to identify the YAML config
        '''
        # Boolean if the function is the root or not, determines if the application is
        # intialized via tk.Tk or tk.Toplevel
        self.is_root_process = is_root_process

        # Define class attributes to store data aquisition and controllers
        self.wavelength_controller_model = None
        self.data_acquisition_models = {}
        self.auxiliary_control_models = {}
        self.application_controller_constructor = None
        self.scan_thread = None

        # List to keep track of child scan windows
        self.scan_windows = []
        self.current_scan = None
        self.number_scans_on_session = 0 # The number of scans performed
        self.last_save_directory = 'C:/Users/Fu Lab NV PC/Documents' # Modify this for your system

        # Load the YAML file based off of `controller_name`
        self.load_controller_from_name(yaml_filename=default_config_filename)

        # Initialize the root tkinter widget (window housing GUI)
        if self.is_root_process:
            self.root = tk.Tk()
        else:
            self.root = tk.Toplevel()
        # Create the main application GUI and specify the controller name
        self.view = MainApplicationView(self, 
                                        scan_range=[self.wavelength_controller_model.min_voltage, 
                                                    self.wavelength_controller_model.max_voltage])
        
        # Bind the GUI buttons to callback functions
        self.view.control_panel.start_button.bind("<Button>", self.start_scan)
        self.view.control_panel.stop_button.bind("<Button>", self.stop_scan)
        self.view.control_panel.goto_button.bind("<Button>", self.go_to)
        self.view.control_panel.get_button.bind("<Button>", self.update_voltage_show)
        self.view.control_panel.hardware_config_from_yaml_button.bind("<Button>", lambda e: self.configure_from_yaml())
        self.view.control_panel.repump_laser_toggle.config(command=self.toggle_repump_laser)

        # Turn off the repump laser at startup
        self.toggle_repump_laser(cmd=False)

        # Set protocol for shutdown when the root tkinter widget is closed (if root process)
        if self.is_root_process:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)


    def go_to(self, event=None) -> None:
        '''
        Callback function for voltage setter `self.view.control_panel.goto_button`

        This function is a wrapper for the `application_controller.go_to()` method
        which is itself a wrapper for the `wavelength_controller.got_to()` method.
        This structure is so that information at behavior and information can be
        handled at intermediate levels (for example, this function gets the input 
        from the GUI, the `application_controller` level handles out-of-range 
        exceptions and the lowest-level `wavelength_controller` opens a nidaq task
        to change the voltage on the hardware.)
        '''
        self.disable_buttons()
        self.wavelength_controller_model.go_to_voltage(float(self.view.control_panel.voltage_entry.get()))
        self.enable_buttons()

    def update_voltage_show(self, event=None) -> None:
        '''
        Callback to update the reading on the GUI voltage getter

        Obtains the last write value from the wavelength_controller level and
        then updates the result on the GUI.
        '''
        # Get the last write value from the wavelength controller
        read = self.wavelength_controller_model.last_write_value
        # Update the GUI
        voltage_getter_entry = self.view.control_panel.voltage_show
        # Need to set the tk.Entry into normal, update, then reset to readonly
        voltage_getter_entry.config(state='normal')     
        voltage_getter_entry.delete(0,'end')
        voltage_getter_entry.insert(0,read)
        voltage_getter_entry.config(state='readonly')

    def toggle_repump_laser(self, cmd:bool=None) -> None:
        '''
        Callback to toggle the repump laser.
        Also functions as a directly callable function in the code 
        by passing the boolean `on` variable.
        '''
        # Check if the application has a repump controller
        if 'RepumpController' in self.auxiliary_control_models:

            # If the GUI toggle is on and no direct command `cmd` given
            # OR if the direct command is True then turn on the laser
            if ((self.view.control_panel.repump_laser_on.get() == 1) and cmd is None) or (cmd is True):
                logger.info('Turning repump laser on.')
                self.disable_buttons()
                self.auxiliary_control_models['RepumpController'].go_to_voltage(
                    voltage=self.auxiliary_control_models['RepumpController'].max_voltage)
                self.enable_buttons()
            # Else if the GUI toggle is off and no direct command is given
            # OR if the direct command is False then turn off the laser
            elif ((self.view.control_panel.repump_laser_on.get() == 0) and cmd is None) or (cmd is False):
                logger.info('Turning repump laser off.')
                self.disable_buttons()
                self.auxiliary_control_models['RepumpController'].go_to_voltage(
                    voltage=self.auxiliary_control_models['RepumpController'].min_voltage)
                self.enable_buttons()

    def start_scan(self, event=None) -> None:
        '''
        Callback to start scan button.

        This function runs the actual scan.
        It first collects the scan settings from the GUI inputs and performs
        the calculations for the scan inputs.
        It then launches a Thread which runs the scanning function to avoid 
        locking up the GUI during the scan.
        '''
        if self.current_scan is not None and self.current_scan.application_controller.running:
            return # Catch accidential trigger during scan?
        
        # Turn off the repump laser
        self.toggle_repump_laser(cmd=False)

        # Get the scan parameters from the GUI
        min_voltage = float(self.view.control_panel.voltage_start_entry.get())
        max_voltage = float(self.view.control_panel.voltage_end_entry.get())
        n_pixels_up = int(self.view.control_panel.num_pixels_up_entry.get())
        n_pixels_down = int(self.view.control_panel.num_pixels_down_entry.get())
        n_scans = int(self.view.control_panel.scan_num_entry.get())
        time_up = float(self.view.control_panel.upsweep_time_entry.get())
        time_down = float(self.view.control_panel.downsweep_time_entry.get())
        n_subpixels = int(self.view.control_panel.subpixel_entry.get())
        time_repump = float(self.view.control_panel.repump_entry.get())

        # Create an application controller
        application_controller = self.application_controller_constructor(
                    readers = self.data_acquisition_models, 
                    wavelength_controller = self.wavelength_controller_model,
                    auxiliary_controllers = self.auxiliary_control_models)

        # Configure the scanner
        application_controller.configure_scan(
                    min = min_voltage, 
                    max = max_voltage, 
                    n_pixels_up = n_pixels_up, 
                    n_pixels_down = n_pixels_down, 
                    n_subpixels = n_subpixels,
                    time_up = time_up,
                    time_down = time_down,
                    n_scans = n_scans,
                    time_repump = time_repump)
        
        # Launch new child scan window
        self.number_scans_on_session += 1
        self.current_scan = ScanPopoutApplication(parent_application=self,
                                                  application_controller=application_controller, 
                                                  id=str(self.number_scans_on_session).zfill(3))
        self.scan_windows.append( self.current_scan )
        logger.info(f'Creating new scan window number {self.number_scans_on_session}')

        # Disable the buttons
        self.disable_buttons()

        # Launch the thread
        self.scan_thread = Thread(target=self.scan_thread_function)
        self.scan_thread.start()

    def stop_scan(self, event=None) -> None:
        '''
        Stops the scan
        '''
        logger.info('Requesting to stop scan...')
        # Let the scanner finish the current scan
        # it should run application_controller.stop() after it finishes
        self.current_scan.application_controller.stop_scan = True
        #self.current_scan.application_controller.stop()
        self.enable_buttons()

    def scan_thread_function(self) -> None:
        '''
        Function to be called in background thread.

        Runs the scans and updates the figure.
        '''
        
        try:
            self.current_scan.application_controller.start()  # starts the DAQ

            while self.current_scan.application_controller.still_scanning():
                self.current_scan.application_controller.scan_wavelengths()
                self.current_scan.view.data_viewport.update_figure(self.current_scan.application_controller)
                self.current_scan.view.canvas.draw()

            # Set repump to toggle value
            self.toggle_repump_laser()

            logger.info('Scan complete.')
            self.current_scan.application_controller.stop()

        except nidaqmx.errors.DaqError as e:
            logger.info(e)
            logger.info(
                'Check for other applications using resources. If not, you may need to restart the application.')

        self.enable_buttons()

    def configure_from_yaml(self, afile=None) -> None:
        '''
        This method loads a YAML file to configure the hardware for PLE.
        If argument `afile` is provided and points to a valid YAML file,
        the file is loaded directly.

        If `afile` is not provided (default) then this method opens a GUI
        for the user to select a YAML file.
        
        This method configures the wavelength controller and the readers
        based off of the YAML file data, and then generates a class 
        consctrutor for the main application controller.
        '''
        # Specify the allowed filetypes (.yaml)
        filetypes = (
            ('YAML', '*.yaml'),
        )
        # If a file is not supplied...
        if not afile:
            # Open a GUI to get the file from the user
            afile = tk.filedialog.askopenfile(filetypes=filetypes, defaultextension='.yaml')
            if afile is None:
                return  # selection was canceled.
            # Log selection
            logger.info(f"Loading settings from: {afile}")
            # Retrieve the file in a dictionary `config`
            config = yaml.safe_load(afile)
            afile.close()
        else:
            # Else, open the provided file and load the YAML
            # Currently there is no protection against invalid YAML configs
            with open(afile, 'r') as file:
                # Log selection
                logger.info(f"Loading settings from: {afile}")
                config = yaml.safe_load(file)

        # At this point the `config` variable is a dictionary of 
        # nested dictionaries corresponding to each indent level in the YAML.
        # First we get the top level application name, e.g. "QT3PLE"
        APPLICATION_NAME = list(config.keys())[0]

        # Get the import path and class name for the application controller
        # We will use this to instantiate the application controller later on
        appl_ctrl_import_path = config[APPLICATION_NAME]['ApplicationController']['import_path']
        appl_ctrl_class_name = config[APPLICATION_NAME]['ApplicationController']['class_name']
        # Now we create a constructor for the aplication controller class
        # Import the application controller module
        module = importlib.import_module(appl_ctrl_import_path)
        logger.debug(f"Importing {appl_ctrl_import_path}")
        # Get the class constructor and write it to main
        self.application_controller_constructor = getattr(module, appl_ctrl_class_name)
        

        # The import paths and class names for the controllers and readers
        # are stored in the same YAML file at the same level as ['ApplicationController']
        # However, at this point we do not know how they are used by the
        # application controller. This information is referenced in the 
        # ['ApplicationController']['configure'] level.

        # There are three classes to configure, (1) controllers, (2) readers,
        # and (3) auxiliary controllers.
        # There can only be one controller for this application, we retrieve it by
        controller_name = config[APPLICATION_NAME]['ApplicationController']['configure']['controller']
        # There can be multiple readers. We can retrieve them by getting the
        # values of the readers dict (in no particular order)
        # In the future this step, and the YAML format should be modified to
        # handle the case of a single principal reader (which dictates the timing)
        # and multiple auxiliary readers which depend off of it.
        # This can be implemented by utilizing the keys of the ['configure']['readers']
        # dictionary, or by separating out ['configure']['readers'] into a 
        # singular ['configure']['principal_reader'] and ['configure']['aux_readers']
        # For now we just take all readers simultaneously in no particular order.
        reader_names = list(config[APPLICATION_NAME]['ApplicationController']['configure']['readers'])
        # Finally we can get the auxiliary controllers in the same way
        # We don't really care about the order here since we will use their names
        # as a way to reference them within the code itself.
        aux_ctrl_names = list(config[APPLICATION_NAME]['ApplicationController']['configure']['auxiliary_controllers'])

        # Now that we have their names we can retrieve their import paths
        # and class names from the YAML, along with their configurations.
        # We then can instantiate the controllers and readers and store them
        # within the application instance.
        # First get the dictionary containing the controller configuration
        controller_model_yaml_dict = config[APPLICATION_NAME][controller_name]

        # Import the controller model module
        module = importlib.import_module(controller_model_yaml_dict['import_path'])
        logger.debug(f"Importing {controller_model_yaml_dict['import_path']}")
        # Get the class generator
        controller_class = getattr(module, controller_model_yaml_dict['class_name'])
        # Instantiate the class 
        self.wavelength_controller_model = controller_class(logger.level)
        # Configure using the YAML config
        self.wavelength_controller_model.configure(controller_model_yaml_dict['configure'])

        # Repeat for each of the readers, store in MainTkApplication.data_acquisition_models
        for reader in reader_names:
            # First get the dictionary containing the controller configuration
            reader_model_yaml_dict = config[APPLICATION_NAME][reader]
            # Import the controller model module
            module = importlib.import_module(reader_model_yaml_dict['import_path'])
            logger.debug(f"Importing {reader_model_yaml_dict['import_path']}")
            # Get the class generator
            reader_class = getattr(module, reader_model_yaml_dict['class_name'])
            # Instantiate the class 
            reader_model = reader_class(logger.level)
            # Configure using the YAML config
            reader_model.configure(reader_model_yaml_dict['configure'])
            # Save to data_acquisition_models
            self.data_acquisition_models[reader] = reader_model

        # Repeat for each of the auxiliary controllers, store in MainTkApplication.auxiliary_control_models
        # Repeat for each of the readers
        for aux_ctrl in aux_ctrl_names:
            # First get the dictionary containing the controller configuration
            aux_ctrl_model_yaml_dict = config[APPLICATION_NAME][aux_ctrl]
            # Import the controller model module
            module = importlib.import_module(aux_ctrl_model_yaml_dict['import_path'])
            logger.debug(f"Importing {aux_ctrl_model_yaml_dict['import_path']}")
            # Get the class generator
            aux_ctrl_class = getattr(module, aux_ctrl_model_yaml_dict['class_name'])
            # Instantiate the class 
            aux_ctrl_model = aux_ctrl_class(logger.level)
            # Configure using the YAML config
            aux_ctrl_model.configure(aux_ctrl_model_yaml_dict['configure'])
            # Save to auxiliary_control_models
            self.auxiliary_control_models[aux_ctrl] = aux_ctrl_model


    def load_controller_from_name(self, yaml_filename: str) -> None:
        '''
        Loads the default yaml configuration file for the application controller.

        Should be called during instantiation of this class and should be the callback
        function for the support controller pull-down menu in the side panel
        '''
        yaml_path = importlib.resources.files(CONFIG_PATH).joinpath(yaml_filename)
        self.configure_from_yaml(str(yaml_path))

    def disable_buttons(self):
        self.view.control_panel.start_button['state'] = 'disabled'
        self.view.control_panel.goto_button['state'] = 'disabled'
        try:
            self.current_scan.view.control_panel.save_scan_button.config(state=tk.DISABLED)
        except Exception as e:
            if self.current_scan is not None:
                logger.debug('Exception caught disabling buttons')
                logger.debug(e)
                pass

    def enable_buttons(self):
        self.view.control_panel.start_button['state'] = 'normal'
        self.view.control_panel.goto_button['state'] = 'normal'
        try:
            self.current_scan.view.control_panel.save_scan_button.config(state=tk.NORMAL)
        except Exception as e:
            if self.current_scan is not None:
                logger.debug('Exception caught enabling buttons')
                logger.debug(e)
                pass


    def run(self) -> None:
        '''
        This function launches the application itself.
        '''
        # Set the title of the app window
        self.root.title("qdlple")
        # Display the window (not in task bar)
        self.root.deiconify()
        # Launch the main loop
        if self.is_root_process:
            self.root.mainloop()


    def on_closing(self) -> None:
        '''
        This function handles closing the application.
        '''
        if (self.scan_thread is not None) and (self.scan_thread.is_alive()):
            if tk.messagebox.askokcancel(
                    'Warning', 
                    'Scan is currently running and may not close properly.'
                    +'\nAre you sure you want to force quit?'):
                logger.warning('Forcing application closure.')

                # Close the application out
                self.toggle_repump_laser(cmd=True) # Turn the repump laser back on
                self.root.destroy()
                self.root.quit()
        else:
            self.toggle_repump_laser(cmd=True)
            self.root.destroy()
            self.root.quit()
        
        logger.info('Exited application.')
        

class ScanPopoutApplication():
    '''
    Scan popout application backend. Launches the GUI, houses the 
    application_controller, handles events for controlling the view port and
    saving data for a set of scans.
    '''
    def __init__(self, parent_application, application_controller, id: str = '') -> None:
        # Store the application controller and number identifier
        self.parent_application = parent_application
        self.application_controller = application_controller
        self.id = id
        self.timestamp = datetime.datetime.now()
        

        # First load meta/config data from the application controller
        self.min = application_controller.min
        self.max = application_controller.max
        self.n_pixels_up = application_controller.n_pixels_up
        self.n_pixels_down = application_controller.n_pixels_down
        self.n_subpixels = application_controller.n_subpixels
        self.time_up = application_controller.time_up
        self.time_down = application_controller.time_down
        self.n_scans = application_controller.n_scans
        self.time_repump = application_controller.time_repump
        self.pixel_step_size_up = application_controller.pixel_step_size_up
        self.pixel_step_size_down = application_controller.pixel_step_size_down
        self.sample_step_size_up = application_controller.sample_step_size_up
        self.sample_step_size_down = application_controller.sample_step_size_down
        self.pixel_voltages_up = application_controller.pixel_voltages_up
        self.pixel_voltages_down = application_controller.pixel_voltages_down
        self.sample_voltages_up = application_controller.sample_voltages_up
        self.sample_voltages_down = application_controller.sample_voltages_down
        self.pixel_time_up = application_controller.pixel_time_up
        self.pixel_time_down = application_controller.pixel_time_down
        self.sample_time_up = application_controller.sample_time_up
        self.sample_time_down = application_controller.sample_time_down

        # Then initialize the GUI
        self.root = tk.Toplevel()
        self.root.title(f'Scan {id} ({self.timestamp.strftime("%Y-%m-%d %H:%M:%S")})')
        self.view = ScanPopoutApplicationView(main_frame=self.root, scan_settings=self.__dict__)

        # Bind the buttons to callbacks
        self.view.control_panel.save_scan_button.bind("<Button>", self.save_data)
        self.view.control_panel.norm_button.bind("<Button>", self.set_normalize)
        self.view.control_panel.autonorm_button.bind("<Button>", self.auto_normalize)

        self.view.control_panel.integrate_scans_toggle.config(command=self.toggle_integrate)

        # Set the behavior on clsing the window, launch main loop for window
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def save_data(self, event=None) -> None:
        '''
        Method to save the data, you can add more logic later for other filetypes.
        The event input is to catch the tkinter event that is supplied but not used.
        '''
        allowed_formats = [('Image with dataset', '*.png'), ('Dataset', '*.hdf5')]

        # Default filename
        default_name = f'scan{self.id}_{self.timestamp.strftime("%Y%m%d")}'
            
        # Get the savefile name
        afile = tk.filedialog.asksaveasfilename(filetypes=allowed_formats, 
                                                initialfile=default_name+'.png',
                                                initialdir = self.parent_application.last_save_directory)
        # Handle if file was not chosen
        if afile is None or afile == '':
            logger.warning('File not saved!')
            return # selection was canceled.

        # Get the path
        file_path = '/'.join(afile.split('/')[:-1])  + '/'
        self.parent_application.last_save_directory = file_path # Save the last used file path
        logger.info(f'Saving files to directory: {file_path}')
        # Get the name with extension (will be overwritten)
        file_name = afile.split('/')[-1]
        # Get the filetype
        file_type = file_name.split('.')[-1]
        # Get the filename without extension
        file_name = '.'.join(file_name.split('.')[:-1]) # Gets everything but the extension

        # If the file type is .png, want to save image and hdf5
        if file_type == 'png':
            logger.info(f'Saving the PNG as {file_name}.png')
            fig = self.view.data_viewport.fig
            fig.savefig(file_path+file_name+'.png', dpi=300, bbox_inches=None, pad_inches=0)

        # Save as hdf5
        with h5py.File(file_path+file_name+'.hdf5', 'w') as df:
            
            logger.info(f'Saving the HDF5 as {file_name}.hdf5')
            
            # Save the file metadata
            ds = df.create_dataset('file_metadata', 
                                   data=np.array(['application', 
                                                  'qdlutils_version', 
                                                  'scan_id', 
                                                  'timestamp', 
                                                  'original_name'], dtype='S'))
            ds.attrs['application'] = 'qdlutils.qdlple'
            ds.attrs['qdlutils_version'] = qdlutils.__version__
            ds.attrs['scan_id'] = self.id
            ds.attrs['timestamp'] = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ds.attrs['original_name'] = file_name

            # Save the scan settings
            # If your implementation settings vary you should change the attrs
            ds = df.create_dataset('scan_settings/min', data=self.min)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Minimum scan voltage'
            ds = df.create_dataset('scan_settings/max', data=self.max)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Maximum scan voltage'
            # Pixel settings
            ds = df.create_dataset('scan_settings/n_pixels_up', data=self.n_pixels_up)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of pixels on upsweep'
            ds = df.create_dataset('scan_settings/n_pixels_down', data=self.n_pixels_down)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of pixels on downsweep'
            ds = df.create_dataset('scan_settings/n_subpixels', data=self.n_subpixels)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of subpixel samples per pixel'
            ds = df.create_dataset('scan_settings/n_scans', data=self.n_scans)
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Number of scans requested'
            # Time settings
            ds = df.create_dataset('scan_settings/time_up', data=self.time_up)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Total time for upsweep'
            ds = df.create_dataset('scan_settings/time_down', data=self.time_down)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Total time for downsweep'
            ds = df.create_dataset('scan_settings/time_repump', data=self.time_repump)
            ds.attrs['units'] = 'Milliseconds'
            ds.attrs['description'] = 'Time for repump at start of scan'
            # Derived settings
            ds = df.create_dataset('scan_settings/pixel_step_size_up', data=self.pixel_step_size_up)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage step size between pixels on upsweep'
            ds = df.create_dataset('scan_settings/pixel_step_size_down', data=self.pixel_step_size_down)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage step size between pixels on downsweep'
            ds = df.create_dataset('scan_settings/sample_step_size_up', data=self.sample_step_size_up)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage step size between samples on upsweep'
            ds = df.create_dataset('scan_settings/sample_step_size_down', data=self.sample_step_size_down)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage step size between samples on downsweep'
            ds = df.create_dataset('scan_settings/pixel_time_up', data=self.pixel_time_up)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Total time per pixel on upsweep'
            ds = df.create_dataset('scan_settings/pixel_time_down', data=self.pixel_time_down)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Total time per pixel on downsweep'
            ds = df.create_dataset('scan_settings/sample_time_up', data=self.sample_time_up)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Integration time per sample on upsweep'
            ds = df.create_dataset('scan_settings/sample_time_down', data=self.sample_time_down)
            ds.attrs['units'] = 'Seconds'
            ds.attrs['description'] = 'Integration time per sample on downsweep'

            # Create the primary datasets
            ds = df.create_dataset('data/pixel_voltages_up', data=self.pixel_voltages_up)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage value at start of each pixel on upsweep'
            ds = df.create_dataset('data/pixel_voltages_down', data=self.pixel_voltages_down)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage value at start of each pixel on downsweep'
            ds = df.create_dataset('data/sample_voltages_up', data=self.sample_voltages_up)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage value at sample points on upsweep'
            ds = df.create_dataset('data/sample_voltages_down', data=self.sample_voltages_down)
            ds.attrs['units'] = 'Volts'
            ds.attrs['description'] = 'Voltage value at sample points on downsweep'

            # Get the full image data
            # Maybe can remove if we update image data at the popout window level?
            for reader in self.application_controller.readers:
                if isinstance(self.application_controller.readers[reader], NidaqTimedRateCounter):
                    img_data = np.array([output[reader] for output in self.application_controller.outputs])
            # Write the image data to file
            ds = df.create_dataset('data/scan_counts', data=img_data)
            ds.attrs['units'] = 'Counts/second'
            ds.attrs['description'] = ('2-d array of counts per second at each pixel of the completed scans.'
                                      +' Each row consists of one upscan and downscan pair, appended in order.'
                                      +' The scans are ordered from oldest to newest.')
            ds = df.create_dataset('data/upscan_counts', data=[scan[:self.n_pixels_up] for scan in img_data])
            ds.attrs['units'] = 'Counts/second'
            ds.attrs['description'] = '2-d array of counts per second at each pixel of the upscans only.'
            ds = df.create_dataset('data/downscan_counts', data=[scan[self.n_pixels_up:] for scan in img_data])
            ds.attrs['units'] = 'Counts/second'
            ds.attrs['description'] = '2-d array of counts per second at each pixel of the downscans only.'

    def set_normalize(self, tkinter_event: tk.Event = None) -> None:
        '''
        Callback function to set the normalization of the figure based off of the values
        written to the GUI.
        '''
        # Get the value from the controller
        norm_min = float(self.view.control_panel.image_minimum.get())
        norm_max = float(self.view.control_panel.image_maximum.get())

        if norm_min > norm_max:
            raise ValueError(f'Minimum norm value {norm_min} > {norm_max}.')
        if norm_min < 0:
            raise ValueError(f'Minimum norm cannot be less than 0.')

        # Save the minimum/maximum norm
        self.view.data_viewport.norm_min = norm_min
        self.view.data_viewport.norm_max = norm_max

        self.view.data_viewport.update_figure(self.application_controller)
        self.view.canvas.draw()

    def auto_normalize(self, tkinter_event: tk.Event = None) -> None:   
        '''
        Callback function to autonormalize the figure.
        '''
        # Save the minimum/maximum norm
        self.view.data_viewport.norm_min = None
        self.view.data_viewport.norm_max = None

        self.view.data_viewport.update_figure(self.application_controller)
        self.view.canvas.draw()

    def toggle_integrate(self):
        # Check if the checkbox is checked in the GUI
        if (self.view.control_panel.integrate_scans.get() == 1):
            self.view.data_viewport.integrate_scans = True
        else:
            self.view.data_viewport.integrate_scans = False

        try:
            # Update the figure
            self.view.data_viewport.update_figure(self.application_controller)
            self.view.canvas.draw()
        except Exception as e:
            logger.warning(f'Error in toggling: {e}')


    def on_closing(self) -> None:
        '''
        This function handles shutdown when window is closed.

        This should warn the user that the current scan window was closed and
        that one should check that the scan controller is not incorrectly in the
        running state.
        It then destroys the window.
        
        FYI: You shouldn't run self.root.quit() even on child processes because
        this actually kills the mainloop() instantiated in startup and closes the
        whole application outright.
        '''
        if self.application_controller.still_scanning():
            logger.warning('Scan window closed while active. Verify scanning has stopped.')
            self.parent_application.stop_scan()
        self.root.destroy()


def main(is_root_process=True) -> None:
    tkapp = MainTkApplication(
        default_config_filename=DEFAULT_CONFIG_FILE,
        is_root_process=is_root_process)
    tkapp.run()


if __name__ == '__main__':
    main()
