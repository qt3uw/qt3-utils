import os
import uuid
import logging
import numpy as np
from time import sleep
from pathlib import Path
from qt3utils.errors import  QT3Error
from typing import Any, Tuple, List, Union

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
    def __init__(self, visible: bool) -> None:
        self._automation = lf.Automation.Automation(visible, List[String]())
        self._application = self._automation.LightFieldApplication
        self._experiment = self._application.Experiment

    @property
    def experiment(self) -> Any:
        return self._experiment

    def __del__(self) -> None:
        """
        Uses Python garbage collection method used to terminate
        AddInProcess.exe, if this is not done, LightField will not reopen
        properly.
        """
        #NOTE: May need to call '.Dispose()' here again as qt3scan may fail to call 'close'
        self._automation.Dispose()
        logger.info('Closed AddInProcess.exe')

    def set(self, setting: str, value: Any) -> None:
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

    def get(self, setting: Any) -> Any:
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

    def load_experiment(self, value: str) -> None:
        self.experiment.Load(value)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationAttachDate, False)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationAttachTime, False)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationAttachIncrement, True)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationIncrementNumber, 0)

    def file_setup(self) -> None:
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationBaseFileName, str(uuid.uuid4()))
    
    #TODO: Need to actually implement the three methods below so that you can:
    #      - save a new experiment
    #      - save what you are currently working on
    #      - stop the scan 
        
    def save_current_experiment(self) -> None:
        self.experiment.Save()
    
    def save_new_experient(self, value) -> None:
        self.experiment.SaveAs(value)

    def stop_scan(self) -> None:
        self.experiment.Stop()

    #NOTE: Thw while loop in here will not be needed once you fix the "FileNameGeneration" problem.
    def start_acquisition_and_wait(self) -> None:
        """
        Starts the acquisition process and waits until it is completed before carrying on.
        """
        acquisition_time_seconds = self.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime) / 1000.0
        num_frames = self.get(lf.AddIns.ExperimentSettings.AcquisitionFramesToStore)
        self.experiment.Acquire()

        sleep(num_frames * acquisition_time_seconds) 
        
        while self.experiment.IsRunning:
            sleep(0.1)  # checking if the experiment is still running

    def process_acquired_data(self) -> np.ndarray:
        """
        Processes the most recently acquired data and returns it as a numpy array.
        """
        last_file = self._application.FileManager.GetRecentlyAcquiredFileNames()[0]
        image_dataset = self._application.FileManager.OpenFile(last_file, FileAccess.Read)

        if image_dataset.Regions.Length == 1:
            if image_dataset.Frames == 1:
                return self._process_single_frame(image_dataset)
            else:
                return self._process_multiple_frames(image_dataset)
        else:
            raise QT3Error(f"LightField FileManager OpenFile error. Unsupported value for Regions.Length: {image_dataset.Regions.Length}.Should be == 1")

    def _process_single_frame(self, image_dataset: Any) -> np.ndarray:
        """
            **Single Frame**:
            - Data is returned as a 2D array representing raw counts from each pixel.
            - A vertical section (spanning 400 pixels) represents a range for wavelength averaging.
        """
        frame = image_dataset.GetFrame(0, 0)
        return np.reshape(np.fromiter(frame.GetData(), dtype='uint16'), [frame.Width, frame.Height], order='F')

    def _process_multiple_frames(self, image_dataset: Any) -> np.ndarray:
        """
            **Multiple Frames**:
            - Data from successive exposures is added as a new dimension, then returns a 3D array.
            - Averaging across frames can be done by summing over this additional dimension.
        """
        data = np.array([])
        for i in range(image_dataset.Frames):
            frame = image_dataset.GetFrame(0, i)
            new_frame = np.reshape(np.fromiter(frame.GetData(), dtype='uint16'), [frame.Width, frame.Height], order='F')
            data = np.dstack((data, new_frame)) if data.size else new_frame
        return data

    #NOTE: May not need to call the 'start_acquisition_and_wait' method if you fix the 'FileNameGeneration' issue
    def acquire(self) -> np.ndarray:
        """
        Acquires image data from the spectrometer.
        """
        self.file_setup()
        self.start_acquisition_and_wait()
        return self.process_acquired_data()

    def close(self) -> None:
        """
        Closes the Lightfield application without saving the settings.
        """
        self._automation.Dispose()
        logger.info('Closed AddInProcess.exe')

class SpectrometerConfig():

    MIN_WAVELENGTH_DIFFERENCE = 117

    def __init__(self, experiment_name=None) -> None:
        self._experiment_name = experiment_name
        self.light = LightfieldApplicationManager(True)

    def finalize(self) -> None:
        """
        Closes the Lightfield application without saving the settings.
        """
        self.light.close()
    
    def get_wavelengths(self) -> np.ndarray:
        """
        Returns the wavelength calibration for a single frame.

        According to the person who made the Lightfield sofware there is not current way to use the exact Lightfield settings
        for step and glue. Will have to interpolate for now.
        """
        wavelength_array = np.fromiter(self.light.experiment.SystemColumnCalibration, np.float64)
        return wavelength_array
    
    @property
    def center_wavelength(self) -> float:
        """
        Returns the center wavelength in nanometers.
        """
        return self.light.get(lf.AddIns.SpectrometerSettings.GratingCenterWavelength)

    @center_wavelength.setter
    def center_wavelength(self, nanometers: float) -> None:
        """
        Sets the spectrometer center wavelength to nanometers.
        """
        # The line below addresses bug where if step and glue is enabled it wont allow you to set the center wavelength.
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
        self.light.set(lf.AddIns.SpectrometerSettings.GratingCenterWavelength, nanometers)

    @property
    def experiment_name(self) -> Union[str, None]:
        """
        Returns the experiment name.
        """
        return self._experiment_name

    @experiment_name.setter
    def experiment_name(self, a_name: str) -> None:
        """
        User can set the experiment that they want to load.
        """
        if a_name != self._experiment_name:
            # Added this to prevent errors with incorrect file name
            if a_name in self.light.experiment.GetSavedExperiments(): 
                self._experiment_name = a_name
                self.light.load_experiment(self._experiment_name)
            else:
                logger.error(f"An experiment with that file name does not exist.")

    @property
    def grating(self) -> str:
        """
        Returns the current grating.
        """
        return self.light.get(lf.AddIns.SpectrometerSettings.GratingSelected)

    @grating.setter
    def grating(self, value: str) -> None:
        """
        Sets the current grating to be the one specified by parameter grating.
        """
        if value in self.grating_options:
            self.light.set(lf.AddIns.SpectrometerSettings.GratingSelected, value)
        else:
            logger.error(f"Grating {value} is not an options. The options are: {self.grating_options}")

    @property
    def grating_options(self) -> List[str]:
        """
        Returns a list of all installed gratings.
        """
        # This line below is critical. "GetCurrentCapabilities" is able to return the list of possibilities of any Lightfield call in order to provide more information.
        available_gratings = self.light.experiment.GetCurrentCapabilities(lf.AddIns.SpectrometerSettings.GratingSelected)
        return [str(a) for a in available_gratings]

    @property
    def num_frames(self) -> int:
        """
        Returns the number of frames taken during the acquisition.
        """
        return self.light.get(lf.AddIns.ExperimentSettings.AcquisitionFramesToStore)

    @num_frames.setter
    def num_frames(self, num_frames: int) -> None:
        """
        Sets the number of frames to be taken during acquisition to number.
        """
        self.light.set(lf.AddIns.ExperimentSettings.AcquisitionFramesToStore, num_frames)

    @property
    def exposure_time(self) -> float:
        """
        Returns the single frame exposure time (in ms).
        """
        return self.light.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime)

    @exposure_time.setter
    def exposure_time(self, ms: float) -> None:
        """
        Sets the single frame exposure time to be ms (in ms).
        """
        self.light.set(lf.AddIns.CameraSettings.ShutterTimingExposureTime, ms)

    @property
    def temperature_sensor_setpoint(self) -> float:
        """
        Returns the sensor setpoint temperature (Celsius).
        """
        return self.light.get(lf.AddIns.CameraSettings.SensorTemperatureSetPoint)

    @temperature_sensor_setpoint.setter
    def temperature_sensor_setpoint(self, deg_C: float) -> None:
        """
        Sets the sensor target temperature (in degrees Celsius) to deg_C.
        This function retrieves image data, with particular attention to the camera's configuration determined by the `temperature_sensor_setpoint`.
        The `temperature_sensor_setpoint` defines a target or reference value for the camera's sensor, ensuring optimal or specific operation conditions for image acquisition.
        Depending on the setpoint, the behavior or response of the camera sensor might vary.
        """
        self.light.set(lf.AddIns.CameraSettings.SensorTemperatureSetPoint, deg_C)

class SpectrometerDataAcquisition(SpectrometerConfig):
    def acquire_frame(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Acquires a frame (or series of frames) from the spectrometer, and the
        corresponding wavelength data.
        """
        return self.light.acquire(), self.get_wavelengths()
    
    def acquire_step_and_glue(self, wavelength_range: Tuple[float, float]) -> Tuple[np.ndarray, np.ndarray]:
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