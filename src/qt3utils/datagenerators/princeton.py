import os
import logging
import numpy as np
from time import sleep
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import clr

    lf_root = Path(os.environ['LIGHTFIELD_ROOT'])
    automation_path = lf_root / 'PrincetonInstruments.LightField.AutomationV4.dll'
    addin_path = lf_root / 'AddInViews' / 'PrincetonInstruments.LightFieldViewV4.dll'
    support_path = lf_root / 'PrincetonInstruments.LightFieldAddInSupportServices.dll'

    addin_class = clr.AddReference(str(addin_path))
    automation_class = clr.AddReference(str(automation_path))
    support_class = clr.AddReference(str(support_path))

    import PrincetonInstruments.LightField as lf

    clr.AddReference("System.Collections")
    clr.AddReference("System.IO")
    from System.Collections.Generic import List
    from System import String
    from System.IO import FileAccess
except KeyError as e:
    logger.error(f"KeyError {e} during import")
except ImportError as e:
    logger.error(f"Unable to import packages: {e}")


class LightfieldApplicationManager:
    def __init__(self, visible):
        self._automation = lf.Automation.Automation(visible, List[String]())
        self._application = self._automation.LightFieldApplication
        self._experiment = self._application.Experiment

    @property
    def experiment(self):
        return self._experiment

    def __del__(self):
        """
        Uses Python garbage collection method used to terminate
        AddInProcess.exe, if this is not done, LightField will not reopen
        properly.
        """
        #NOTE: May need to call '.Dispose()' here again as qt3scan may fail to call 'close'
        self._automation.Dispose()
        logger.info('Closed AddInProcess.exe')

    def set(self, setting, value):
        """
        Helper function for setting experiment parameters with basic value
        checking.
        """
        if self.experiment.Exists(setting):
            if self.experiment.IsValid(setting, value):
                self.experiment.SetValue(setting, value)
            else:
                # TODO: might need to add a proper exception
                logger.error(f'Invalid value: {value} for setting: {setting}.')
        else:
            # TODO: might need to add a proper exception
            logger.error(f'Invalid setting: {setting}.')

    def get(self, setting):
        """
        Helper function for getting experiment parameters with a basic check
        to see if a specific setting is valid.
        """
        if self.experiment.Exists(setting):
            value = self.experiment.GetValue(setting)
        else:
            value = []
            logger.error(f'Invalid setting: {setting}.')
        return value

    def load_experiment(self, value):
        self.experiment.Load(value)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationAttachDate, True)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationAttachTime, True)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationAttachIncrement, False)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationBaseFileName, "TestingStuff")

    #TODO: Need to actually implement the three methods below so that you can:
    #      - save a new experiment
    #      - save what you are currently working on
    #      - stop the scan 
        
    def save_current_experiment(self):
        self.experiment.Save()
    
    def save_new_experient(self, value):
        self.experiment.SaveAs(value)

    def stop_scan(self):
        self.experiment.Stop()

    #NOTE: Thw while loop in here will not be needed once you fix the "FileNameGeneration" problem.
    def start_acquisition_and_wait(self):
        """
        Starts the acquisition process and waits until it is completed before carrying on.
        """
        acquisition_time = self.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime)
        num_frames = self.get(lf.AddIns.ExperimentSettings.AcquisitionFramesToStore)
        self.experiment.Acquire()
        
        sleep(0.001 * acquisition_time * num_frames)  # waiting for the exposure duration
        
        while self.experiment.IsRunning:
            sleep(0.1)  # checking if the experiment is still running

    def process_acquired_data(self):
        """
        Processes the most recently acquired data and returns it as a numpy array.
        """
        last_file = self._application.FileManager.GetRecentlyAcquiredFileNames()[0]
        curr_image = self._application.FileManager.OpenFile(last_file, FileAccess.Read)

        if curr_image.Regions.Length == 1:
            # Handle Single Frame
            if curr_image.Frames == 1:
                return self._process_single_frame(curr_image)
            # Handle Multiple Frames
            else:
                return self._process_multiple_frames(curr_image)
        else:
            raise Exception('curr_image.Regions is not valid. Please retry.')

    def _process_single_frame(self, curr_image):
        """
            **Single Frame**:
            - Data is returned as a 2D array representing raw counts from each pixel.
            - A vertical section (spanning 400 pixels) represents a range for wavelength averaging.
        """
        frame = curr_image.GetFrame(0, 0)
        return np.reshape(np.fromiter(frame.GetData(), dtype='uint16'), [frame.Width, frame.Height], order='F')

    def _process_multiple_frames(self, curr_image):
        """
            **Multiple Frames**:
            - Data from successive exposures is added as a new dimension, then returns a 3D array.
            - Averaging across frames can be done by summing over this additional dimension.
        """
        data = np.array([])
        for i in range(curr_image.Frames):
            frame = curr_image.GetFrame(0, i)
            new_frame = np.reshape(np.fromiter(frame.GetData(), dtype='uint16'), [frame.Width, frame.Height], order='F')
            data = np.dstack((data, new_frame)) if data.size else new_frame
        return data

    #NOTE: May not need to call the 'start_acquisition_and_wait' method if you fix the 'FileNameGeneration' issue
    def acquire(self):
        """
        Acquires image data from the spectrometer.
        """
        self.start_acquisition_and_wait()
        return self.process_acquired_data()

    def close(self):
        """
        Closes the Lightfield application without saving the settings.
        """
        self._automation.Dispose()
        logger.info('Closed AddInProcess.exe')

class SpectrometerConfig():

    MIN_WAVELENGTH_DIFFERENCE = 117

    def __init__(self, experiment_name=None):
        self._experiment_name = experiment_name
        self.light = LightfieldApplicationManager(True)

    def finalize(self):
        """
        Closes the Lightfield application without saving the settings.
        """
        self.light.close()
    
    def get_wavelengths(self):
        """
        Returns the wavelength calibration for a single frame.

        According to the person who made the Lightfield sofware there is not current way to use the exact Lightfield settings
        for step and glue. Will have to interpolate for now.
        """
        wavelength_array = np.fromiter(self.light.experiment.SystemColumnCalibration, np.float64)
        return wavelength_array
    
    @property
    def center_wavelength(self):
        """
        Returns the center wavelength in nanometers.
        """
        return self.light.get(lf.AddIns.SpectrometerSettings.GratingCenterWavelength)

    @center_wavelength.setter
    def center_wavelength(self, nanometers):
        """
        Sets the spectrometer center wavelength to nanometers.
        """
        #NOTE: The line below addresses bug where if step and glue is enabled it wont allow you to set the center wavelength.
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
        self.light.set(lf.AddIns.SpectrometerSettings.GratingCenterWavelength, nanometers)

    @property
    def experiment_name(self):
        """
        Returns the experiment name.
        """
        return self._experiment_name

    @experiment_name.setter
    def experiment_name(self, a_name):
        """
        User can set the experiment that they want to load.
        """
        if a_name != self._experiment_name:
            #Added this to prevent errors with incorrect file name
            if a_name in self.light.experiment.GetSavedExperiments(): 
                self._experiment_name = a_name
                self.light.load_experiment(self._experiment_name)
            else:
                logger.error(f"An experiment with that file name does not exist.")

    @property
    def grating(self):
        """
        Returns the current grating.
        """
        return self.light.get(lf.AddIns.SpectrometerSettings.GratingSelected)

    @grating.setter
    def grating(self, grating_string):
        """
        Sets the current grating to be the one specified by parameter grating.
        """
        if grating_string in self.grating_options:
            self.light.set(lf.AddIns.SpectrometerSettings.GratingSelected, grating_string)
        else:
            logger.error(f"Grating {grating_string} is not an options. The options are: {self.grating_options}")

    @property
    def grating_options(self):
        """
        Returns a list of all installed gratings.
        """
        #NOTE: This line below is important. "GetCurrentCapabilities" is able to return the list of possibilities of any Lightfield call in order to provide more information.
        available_gratings = self.light.experiment.GetCurrentCapabilities(lf.AddIns.SpectrometerSettings.GratingSelected)
        return [str(a) for a in available_gratings]

    @property
    def num_frames(self):
        """
        Returns the number of frames taken during the acquisition.
        """
        return self.light.get(lf.AddIns.ExperimentSettings.AcquisitionFramesToStore)

    @num_frames.setter
    def num_frames(self, num_frames):
        """
        Sets the number of frames to be taken during acquisition to number.
        """
        self.light.set(lf.AddIns.ExperimentSettings.AcquisitionFramesToStore, num_frames)

    @property
    def exposure_time(self):
        """
        Returns the single frame exposure time (in ms).
        """
        return self.light.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime)

    @exposure_time.setter
    def exposure_time(self, ms):
        """
        Sets the single frame exposure time to be ms (in ms).
        """
        self.light.set(lf.AddIns.CameraSettings.ShutterTimingExposureTime, ms)

    @property
    def sensor_temperature(self):
        """
        Returns the current sensor temperature (in Celsius).
        """
        self.light.get(lf.AddIns.CameraSettings.SensorTemperatureReading)

    @property
    def temperature_sensor_setpoint(self):
        """
        Returns the sensor setpoint temperature (Celsius).
        """
        return self.light.get(lf.AddIns.CameraSettings.SensorTemperatureSetPoint)

    @temperature_sensor_setpoint.setter
    def temperature_sensor_setpoint(self, deg_C):
        """
        Sets the sensor target temperature (in degrees Celsius) to deg_C.
        This function retrieves image data, with particular attention to the camera's configuration determined by the `temperature_sensor_setpoint`.
        The `temperature_sensor_setpoint` defines a target or reference value for the camera's sensor, ensuring optimal or specific operation conditions for image acquisition.
        Depending on the setpoint, the behavior or response of the camera sensor might vary.
        """
        self.light.set(lf.AddIns.CameraSettings.SensorTemperatureSetPoint, deg_C)

class SpectrometerDataAcquisition(SpectrometerConfig):
    def acquire_frame(self):
        """
        Acquires a frame (or series of frames) from the spectrometer, and the
        corresponding wavelength data.
        """
        return self.light.acquire(), self.get_wavelengths()
    
    def acquire_step_and_glue(self, wavelength_range):
        """
        Acquires a step and glue (wavelength sweep) over the specified range.
        Wavelength range must have two elements (both in nm), corresponding
        to the start and end wavelengths.
        Please note that the wavelength must be calibrated for this to be useful.

        Returns:
        - tuple:
        - spectrum (numpy.ndarray): The average spectrum obtained from the acquisition.
        - wavelength (numpy.ndarray): An array of wavelengths corresponding to the spectrum.
        """
        lambda_min = wavelength_range[0]
        lambda_max = wavelength_range[1]
        try:
            self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, True)
        except Exception as e:
            self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
            logger.error(f'Unable to perform step and glue due to error: {e}')

        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueStartingWavelength, lambda_min)
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEndingWavelength, lambda_max)
        
        if lambda_max - lambda_min < self.MIN_WAVELENGTH_DIFFERENCE:
            raise ValueError(f"End wavelength must be atleast {self.MIN_WAVELENGTH_DIFFERENCE} units greater than the start wavelength.") 

        data = self.light.acquire()
        spectrum = np.sum(data, axis=1) #had to add this here to flatten data so it is not 2D but rather, 1D
        wavelength = np.linspace(lambda_min, lambda_max, data.shape[0]) #just remember that this is not exact and just interpolates
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
        return spectrum, wavelength