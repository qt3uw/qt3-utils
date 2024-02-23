import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, List, Literal, Tuple, Union

import numpy as np

from qt3utils.errors import QT3Error
from qt3utils.datagenerators.spectrometers.spectrometer import SpectrometerConfig, SpectrometerDataAcquisition

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
    from System import String, Int32, Int64, Double
    from System.IO import FileAccess
except KeyError as e:
    logger.error(f"KeyError {e} during import")
except ImportError as e:
    logger.error(f"Unable to import packages: {e}")


class LightfieldApplicationManager:
    def initialize(self, visible: bool) -> None:
        self._automation = lf.Automation.Automation(visible, List[String]())
        self._application = self._automation.LightFieldApplication
        self._experiment = self._application.Experiment
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationAttachDate, False)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationAttachTime, False)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationAttachIncrement, True)
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationIncrementNumber, Int32(0))
        self.stop_flag = False

    @property
    def experiment(self) -> Any:
        return self._experiment
    
    @property
    def automation(self) -> Any:
        return self._automation

    def set(self, setting: str, value: Any) -> None:
        """
        Helper function for setting experiment parameters with basic value
        checking.
        """
        if self.experiment.Exists(setting):
            if self.experiment.IsValid(setting, value):
                self.experiment.SetValue(setting, value)
            else:
                raise Exception(f'Invalid value: {value} for setting: {setting}.')
        else:
            raise Exception(f'Invalid setting: {setting}.')

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

    def load_experiment(self, selected_experiment: str) -> None:
        """
        This method loads a specified experiment from the list of experiments stored in Lightfield.
        """
        self.experiment.Load(String(selected_experiment))

    def _file_setup(self) -> None:
        self.set(lf.AddIns.ExperimentSettings.FileNameGenerationBaseFileName, str(uuid.uuid4()))

    def _start_acquisition_and_wait(self) -> None:
        """
        Starts the acquisition process and waits until it is completed before carrying on.
        """
        if self.stop_flag == False:
            self.experiment.Acquire()
            while self.experiment.IsRunning:
                time.sleep(0.1)

    def _process_acquired_data(self) -> np.ndarray:
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
            raise QT3Error(f"LightField FileManager OpenFile error. Unsupported value for Regions.Length: \n"
                           f"{image_dataset.Regions.Length}. Should be == 1")

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

    # NOTE: May not need to call the 'start_acquisition_and_wait' method if you fix the 'FileNameGeneration' issue.
    def acquire(self) -> np.ndarray:
        """
        Acquires image data from the spectrometer.
        """
        self.stop_flag = False
        self._file_setup()
        self._start_acquisition_and_wait()
        return self._process_acquired_data()

    def close(self) -> None:
        """
        Closes the Lightfield application without saving the settings.
        """
        self.automation.Dispose()
        logger.info('Closed AddInProcess.exe')
      

_light_app = LightfieldApplicationManager()
""" Instantiation of the lightfield application manager. """


class PrincetonSpectrometerConfig(SpectrometerConfig):

    light = _light_app
    """ Access to the Lightfield application manager. """

    DEVICE_NAME: str = 'Princeton Spectrometer'

    def __init__(self, experiment_name: str = None):
        super().__init__()
        self._experiment_name = experiment_name

    def open(self) -> None:
        """ Opens the Lightfield application. """
        self.light.initialize(True)

    def close(self) -> None:
        """
        Close Lightfield application without saving the settings.
        """
        self.light.close()

    def __del__(self) -> None:
        """
        Invoke this after object garbage collection occurs. 
        This method cannot be placed in the LightfieldApplicationManager class anymore 
        since 'automation' will be None before it can even be called 
        and will return a 'TypeError: module object is not callable' error when you close the GUI.
        Preventing you from running the HyperSpectral GUI again.
        """
        if self.light.automation is not None:
            try:
                self.light.automation.Dispose()
            except Exception as e:
                logger.error(f"Error disposing Lightfield automation: {e}")

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
            if a_name in self.light.experiment.GetSavedExperiments():
                self._experiment_name = a_name
                self.light.load_experiment(self._experiment_name)
            else:
                self.logger.error(f"An experiment with that file name does not exist.")

    @property
    def grating_list(self) -> List[str]:
        # NOTE: The code below is critical.
        # "GetCurrentCapabilities" is able to return the list of possibilities of any Lightfield call to provide more information.
        available_gratings = self.light.experiment.GetCurrentCapabilities( lf.AddIns.SpectrometerSettings.GratingSelected)
        return [str(a) for a in available_gratings]

    @property
    def current_grating(self) -> str:
        return self.light.get(lf.AddIns.SpectrometerSettings.GratingSelected)

    @current_grating.setter
    def current_grating(self, value: str) -> None:
        if value in self.grating_list:
            self.light.set(lf.AddIns.SpectrometerSettings.GratingSelected, String(value))
        else:
            self.logger.error(f"Grating {value} is not an options. The options are: {self.grating_list}")

    @property
    def center_wavelength(self) -> float:
        return self.light.get(lf.AddIns.SpectrometerSettings.GratingCenterWavelength)

    @center_wavelength.setter
    def center_wavelength(self, nanometers: float) -> None:
        # NOTE: The code below addresses bug where if step-and-glue is enabled, it won't allow you to set the center wavelength.
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
        self.light.set(lf.AddIns.SpectrometerSettings.GratingCenterWavelength, Double(nanometers))
    
    @property
    def starting_wavelength(self) -> float:
        """ The step-and-glue minimum wavelength. """
        return self.light.get(lf.AddIns.ExperimentSettings.StepAndGlueStartingWavelength)
    
    @starting_wavelength.setter
    def starting_wavelength(self, lambda_min: float) -> None:
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueStartingWavelength, Double(lambda_min))
        
    @property
    def ending_wavelength(self) -> float:
        """ The step-and-glue maximum wavelength. """
        return self.light.get(lf.AddIns.ExperimentSettings.StepAndGlueEndingWavelength)
    
    @ending_wavelength.setter
    def ending_wavelength(self, lambda_max: float) -> None:
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEndingWavelength, Double(lambda_max))
        
    def get_wavelengths(self) -> np.ndarray:
        """
        Returns the wavelength calibration for a single frame.

        According to the person who made the Lightfield software,
        there is not a current way to use the exact Lightfield settings
        for step and glue. Will have to interpolate for now.
        """
        wavelength_array = np.fromiter(self.light.experiment.SystemColumnCalibration, np.float64)
        return wavelength_array

    @property
    def sensor_temperature_set_point(self) -> float:
        return self.light.get(lf.AddIns.CameraSettings.SensorTemperatureSetPoint)

    @sensor_temperature_set_point.setter
    def sensor_temperature_set_point(self, deg_celsius: float) -> None:
        """
        This function retrieves image data, with particular attention to the camera's configuration determined by the `sensor_temperature_set_point`.
        The `sensor_temperature_set_point` defines a target or reference value for the camera's sensor, ensuring optimal or specific operation conditions for image acquisition.
        Depending on the setpoint, the behavior or response of the camera sensor might vary.
        """
        self.light.set(lf.AddIns.CameraSettings.SensorTemperatureSetPoint, Double(deg_celsius))

    @property
    def exposure_time(self) -> float:
        return self.light.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime)

    @exposure_time.setter
    def exposure_time(self, ms: float) -> None:
        self.light.set(lf.AddIns.CameraSettings.ShutterTimingExposureTime, Double(ms))

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
        self.light.set(lf.AddIns.ExperimentSettings.AcquisitionFramesToStore, Int64(num_frames))

class PrincetonSpectrometerDataAcquisition(SpectrometerDataAcquisition):

    light = _light_app
    """ Access to the Lightfield application manager. """

    DEVICE_NAME: str = 'Princeton Spectrometer'
    ACQUISITION_MODES: set[str] = {'single', 'step-and-glue'}

    MIN_WAVELENGTH_DIFFERENCE = 117
    """
    This constant represents the minimum difference your maximum 
    and minimum wavelength have to be away from each other in 
    order to perform 'acquire_step_and_glue". If the difference between 
    lambda_max and lambda_min is less than this you will run into an error.
    """

    def acquire(
            self,
            acquisition_mode: Literal['single', 'step-and-glue'],
            **kwargs
    ) -> Union[Tuple[np.ndarray, np.ndarray], None]:
        return super().acquire(acquisition_mode)

    def single_acquisition(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.light.acquire(), self.spectrometer_config.get_wavelengths()

    def step_and_glue_acquisition(
            self,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Acquires a step and glue (wavelength sweep) over the specified range.
        Wavelength range must have two elements (both in nm), corresponding
        to the start and end wavelengths.
        Please note that the wavelength must be calibrated for this to be useful.

        Returns:
        Tuple[numpy.ndarray, numpy.ndarray]
        - spectrum (numpy.ndarray): The average spectrum obtained from the acquisition.
        - wavelength (numpy.ndarray): An array of wavelengths corresponding to the spectrum.
        """
        lambda_min = self.spectrometer_config.starting_wavelength
        lambda_max = self.spectrometer_config.ending_wavelength

        try:
            self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, True)
        except Exception as e:
            self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
            logger.error(f'Unable to perform step and glue due to error: {e}')

        if lambda_max - lambda_min < self.MIN_WAVELENGTH_DIFFERENCE:
            error_message = (f"End wavelength must be at least {self.MIN_WAVELENGTH_DIFFERENCE} units greater than the start wavelength.")
            raise ValueError(error_message)

        data = self.light.acquire()
        spectrum = np.sum(data, axis=1)  # this flattens the data so it is not 2D but rather, 1D
        wavelength = np.linspace(lambda_min, lambda_max,
                                 data.shape[0])  # just remember that this is not exact and just interpolates
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
        return spectrum, wavelength

    def stop_acquisition(self) -> None:
        """
        Stop/Pause the current acquisition.
        If you click "Start" you will be able to continue the scan.
        """
        # TODO: Might need to be worked on further.
        # There is a risk of it showing incorrect data on the GUI after stopping and the resuming.
        # Try click "Stop" on the GUI then "Start" again when you take a scan and you will be able to replicate the error.
        self.light.stop_flag = True
        self.light.experiment.Stop()
