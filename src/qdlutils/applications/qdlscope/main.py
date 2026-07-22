import importlib
import importlib.resources
import logging
import numpy as np
import datetime
import h5py
import time

from threading import Thread
import tkinter as tk
import yaml

import qdlutils
from qdlutils.applications.qdlscope.application_gui import ScopeApplicationView

logger = logging.getLogger(__name__)
logging.basicConfig()


CONFIG_PATH = 'qdlutils.applications.qdlscope.config_files'
DEFAULT_CONFIG_FILE = 'qdlscope_base.yaml'


class ScopeApplication:
    '''
    This class is main `qdlscope` application which handles the internal application
    logic, coordinates the GUI, and queries the application controller for data.

    Notes
    -----
    Due to the implementation of the continuous scanning there is a slight overhead
    associated to each data sample which results in an increased time between samples.

    Based off of the current implementation and testing with the time module, it seems
    like the majority of the overhead is due to the updating of the figure (about 50 ms
    at 500 samples per view). The actual overhead associated with the sampling appears
    to be quite miniminal for the desired data (< 1 ms in all cases).

    This discrepancy can be problematic if the scope sample times are of importance (for
    example, if one is trying to fit a slow exponential decay). Currently we handle this
    by recording the total time between each start/stop of the scanning (not including
    pauses and resetting on "reset"). Additionally we save the relative timetag of the
    sample (technically the time at the end of the sample) to memory to get an
    approximation of the sample timing. While this likely does not contribute much to the
    computational overhead of each cycle it is likely suboptimal. Additional optimization
    of the plotting functionality would also enable faster sampling rates.

    The application controller is also set up to run "batched" samples wherein the user
    may specify a "batch time" during which samples of length "sample time" are taken
    sequentially using the low-level DAQ counting methods (see `NidaqTimedRateCounter`).
    This would enable precise timing control as there is no computational overhead 
    between samples as it is handled entirely by the DAQ. This would enable users to use
    `qdlscope` as a "slow" timing board (limited only by the DAQ clock rate) for cases
    where precise timing is required. Note, however, that this is currently not 
    implemented within the application (this file) or the application GUI and must be
    added separately. For more information see the comments in
        `qdlscope.application_controller:read_counts_batches()`
    '''

    def __init__(self, default_config_filename: str, is_root_process: bool) -> None:
        '''
        Parameters
        ----------
        default_config_filename : str
            Name of the default YAML config file. The loader will look for this file in
            the default path `CONFIG_PATH` defined at the top of this module. 
        '''
        # Boolean if the function is the root or not, determines if the application is
        # intialized via tk.Tk or tk.Toplevel
        self.is_root_process = is_root_process
        
        self.application_controller = None

        # Data
        self.data_x = []
        self.data_y = []
        self.total_measurement_time = 0

        # Parameters
        self.max_samples_to_plot = 500
        self.max_allowed_samples = 1000000 # 1e6 ~ 3 hours at 0.01 s per sample.
        self.daq_parameters = {
            'sample_time': 0.01,
            'get_rate': True,
        }
        self.timestamp = datetime.datetime.now()

        # Last save directory
        self.last_save_directory = None

        # Load the YAML file
        self.load_yaml_from_name(yaml_filename=default_config_filename)

        # Initialize the root tkinter widget (window housing GUI)
        if self.is_root_process:
            self.root = tk.Tk()
        else:
            self.root = tk.Toplevel()
        # Create the main application GUI
        self.view = ScopeApplicationView(main_window=self.root, application=self)

        # Bind the buttons
        self.view.control_panel.start_button.bind("<Button>", self.start_continuous_sampling)
        self.view.control_panel.pause_button.bind("<Button>", self.stop_sampling)
        self.view.control_panel.reset_button.bind("<Button>", self.reset_data)
        self.view.control_panel.save_button.bind("<Button>", self.save_data)

        # Enable the buttons
        self.enable_buttons()

    def run(self) -> None:
        '''
        This function launches the application including the GUI
        '''
        # Set the title of the app window
        self.root.title("qdlscope")
        # Display the window (not in task bar)
        self.root.deiconify()
        # Launch the main loop
        if self.is_root_process:
            self.root.mainloop()

    def enable_buttons(self) -> None:
        '''
        Sets the buttons into the default configuration after resetting the scanner.
        '''
        self.view.control_panel.sample_time_entry.config(state='normal')
        self.view.control_panel.raw_counts_checkbutton.config(state='normal')
        self.view.control_panel.start_button.config(state='normal')
        self.view.control_panel.pause_button.config(state='disabled')
        self.view.control_panel.reset_button.config(state='disabled')
        self.view.control_panel.save_button.config(state='disabled')

    def disable_buttons(self) -> None:
        '''
        Disables the buttons while running the sampler
        '''
        self.view.control_panel.sample_time_entry.config(state='disabled')
        self.view.control_panel.raw_counts_checkbutton.config(state='disabled')
        self.view.control_panel.start_button.config(state='disabled')
        self.view.control_panel.pause_button.config(state='normal')
        self.view.control_panel.reset_button.config(state='disabled')
        self.view.control_panel.save_button.config(state='disabled')

    def start_continuous_sampling(self, tkinter_event: tk.Event = None) -> None:
        '''
        Callback function to start the sampling, appending data onto the current saved data.

        Parameters
        ----------
        tkinter_event : tk.Event
            The `tkinter` event (not used).
        '''
        # Catch if already running
        if self.application_controller.running:
            return None

        logger.info('Starting continuous sampling.')

        # Disable the buttons
        self.disable_buttons()

        # Get the data
        self._get_daq_config()

        # Reset the figure if data is reset
        if len(self.data_x) == 0:
            self.view.initialize_figure()

        # Launch the thread
        self.scan_thread = Thread(target=self.sample_continuous_thread_function)
        self.scan_thread.start()

    def sample_continuous_thread_function(self) -> None:
        '''
        Sampling thread function which handles the data collection.
        '''
        #try:
        logger.info('Starting continuous sampling thread.')

        # Log the start of the measurement
        start_time = time.time()
        for sample in self.application_controller.read_counts_continuous(
                            sample_time = self.daq_parameters['sample_time'], 
                            get_rate = self.daq_parameters['get_rate']):

            # Logging the measurement time directly for each sample
            # This is probably inefficient and will decrease the actual sample rate
            # Although it should be negligible.
            # In this current configuration the logged time corresponds to the end of the
            # sample time bin.
            self.data_x.append(time.time() - start_time)
            # Save the data
            self.data_y.append(sample)
            # Update the viewport
            self.view.update_figure()

            # If the length of the list is too long then terminate the experiemnt
            if len(self.data_x) > self.max_allowed_samples:
                logger.warning(f'Maximum number of allowed samples ({self.max_allowed_samples}) reached, stopping sampling.')
                self.stop_sampling()


        # Increment the total measurement time
        self.total_measurement_time += self.application_controller.readout_time

        logger.info('Sampling complete.')
        try:
            pass
        except Exception as e:
            logger.info(e)

    def stop_sampling(self, tkinter_event: tk.Event = None) -> None:
        '''
        Callback function to stop the sampling.

        Parameters
        ----------
        tkinter_event : tk.Event
            The `tkinter` event (not used).
        '''
        # Catch if already stopped
        if not self.application_controller.running:
            return None

        logger.info('Stopping sampling.')

        # Set the running flag to false to stop after the next sample
        self.application_controller.running = False

        # Enable the buttons
        self.view.control_panel.start_button.config(state='normal')
        self.view.control_panel.pause_button.config(state='disabled')
        self.view.control_panel.reset_button.config(state='normal')
        self.view.control_panel.save_button.config(state='normal')

    def reset_data(self, tkinter_event: tk.Event = None) -> None:
        '''
        Callback function to reset the scanner, resetting the data and figure.

        Parameters
        ----------
        tkinter_event : tk.Event
            The `tkinter` event (not used).
        '''
        # Catch if already running
        if self.application_controller.running:
            return None

        logger.info('Resetting data.')

        # Reset the data variables
        self.data_x = []
        self.data_y = []
        self.total_measurement_time = 0

        # Reset the figure
        self.view.initialize_figure()

        # Enable the buttons
        self.enable_buttons()

    def save_data(self, tkinter_event=None) -> None:
        '''
        Method to save the data, you can add more logic later for other filetypes.
        The event input is to catch the tkinter event that is supplied but not used.
        
        Parameters
        ----------
        tkinter_event : tk.Event
            The `tkinter` event (not used).
        '''

        # Catch if already running
        if self.application_controller.running:
            return None

        allowed_formats = [('Image with dataset', '*.png'), ('Dataset', '*.hdf5')]

        # Default filename
        default_name = f'scope_{self.timestamp.strftime("%Y%m%d")}'
            
        # Get the savefile name
        afile = tk.filedialog.asksaveasfilename(filetypes=allowed_formats, 
                                                initialfile=default_name+'.png',
                                                initialdir = self.last_save_directory)
        # Handle if file was not chosen
        if afile is None or afile == '':
            logger.warning('File not saved!')
            return # selection was canceled.

        # Get the path
        file_path = '/'.join(afile.split('/')[:-1])  + '/'
        self.last_save_directory = file_path # Save the last used file path
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
                                                  'timestamp'
                                                  'original_name'], dtype='S'))
            ds.attrs['application'] = 'qdlutils.qdlscope'
            ds.attrs['qdlutils_version'] = qdlutils.__version__
            ds.attrs['timestamp'] = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ds.attrs['original_name'] = file_name

            # Save the scan settings
            # If your implementation settings vary you should change the attrs
            ds = df.create_dataset('scan_settings/sample_time', data=self.daq_parameters['sample_time'])
            ds.attrs['units'] = 'seconds'
            ds.attrs['description'] = 'Time that the DAQ integrates counts over.'
            ds = df.create_dataset('scan_settings/is_rate', data=self.daq_parameters['get_rate'])
            ds.attrs['units'] = 'None'
            ds.attrs['description'] = 'Boolean; if the recorded data is the rate.'

            ds = df.create_dataset('data/sample_timestamps', data=self.data_x)
            ds.attrs['units'] = 'seconds'
            ds.attrs['description'] = 'Timestamp of each sample relative to the start of the sampling.'
            ds = df.create_dataset('data/intensity', data=self.data_y)
            if self.daq_parameters['get_rate']:
                ds.attrs['units'] = 'counts per second'
            else:
                ds.attrs['units'] = 'counts'
            ds.attrs['description'] = 'Intensity of samples.'
            ds = df.create_dataset('data/total_measurement_time', data=self.total_measurement_time)
            ds.attrs['units'] = 'seconds'
            ds.attrs['description'] = 'Total time in seconds that samples were taken (not including pauses).'

    def configure_from_yaml(self, afile: str) -> None:
        '''
        This method loads a YAML file to configure the qdlmove hardware
        based on yaml file indicated by argument `afile`.

        This method instantiates and configures the counters and application
        controller.

        Parameters
        ----------
        afile: str
            Full-path filename of the YAML config file.
        '''
        with open(afile, 'r') as file:
            # Log selection
            logger.info(f"Loading settings from: {afile}")
            # Get the YAML config as a nested dict
            config = yaml.safe_load(file)

        # First we get the top level application name
        APPLICATION_NAME = list(config.keys())[0]

        # Get the names of the counter and positioners
        hardware_dict = config[APPLICATION_NAME]['ApplicationController']['hardware']
        counter_name = hardware_dict['counter']

        # Get the counter, instantiate, and configure
        import_path = config[APPLICATION_NAME][counter_name]['import_path']
        class_name = config[APPLICATION_NAME][counter_name]['class_name']
        module = importlib.import_module(import_path)
        logger.debug(f"Importing {import_path}")
        constructor = getattr(module, class_name)
        counter = constructor()
        counter.configure(config[APPLICATION_NAME][counter_name]['configure'])

        # Get the application controller constructor 
        import_path = config[APPLICATION_NAME]['ApplicationController']['import_path']
        class_name = config[APPLICATION_NAME]['ApplicationController']['class_name']
        module = importlib.import_module(import_path)
        logger.debug(f"Importing {import_path}")
        constructor = getattr(module, class_name)

        # Create the application controller passing the hardware as kwargs.
        self.application_controller = constructor(
            **{'counter_controller': counter}
        )

    def load_yaml_from_name(self, yaml_filename: str) -> None:
        '''
        Loads the yaml configuration file from name.

        Should be called during instantiation of this class and should be the callback
        function for loading of other standard yaml files while running.

        Parameters
        ----------
        yaml_filename: str
            Filename of the .yaml file in the qdlscan/config_files path.
        '''
        yaml_path = importlib.resources.files(CONFIG_PATH).joinpath(yaml_filename)
        self.configure_from_yaml(str(yaml_path))

    def _get_daq_config(self) -> None:
        '''
        Gets the position parameters in the GUI and validates if they are allowable. 
        Then saves the GUI input to the launcher application if valid.
        '''

        sample_time = float(self.view.control_panel.sample_time_entry.get())
        get_rate = not(bool(self.view.control_panel.raw_counts_toggle.get()))
        
        # Check if the sample time is too long or too short
        if (sample_time < 0.001) or (sample_time > 60):
            raise ValueError(f'Requested sample time {sample_time} is out of bounds (< 1 ms or > 60 s).')
        
        if sample_time < 0.01:
            logger.warning(f'Requested sample time {sample_time}s is less than sample overhead.'
                           +' The actual sample rate will not increase appreciably.')

        # Write to data memory
        self.daq_parameters = {
            'sample_time': sample_time,
            'get_rate': get_rate,
        }


def main(is_root_process=True):
    tkapp = ScopeApplication(
        default_config_filename=DEFAULT_CONFIG_FILE,
        is_root_process=is_root_process)
    tkapp.run()

if __name__ == '__main__':
    main()
