import os
import logging
import numpy as np
from time import sleep

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import clr

    lf_root = os.environ['LIGHTFIELD_ROOT']
    automation_path = lf_root + '\PrincetonInstruments.LightField.AutomationV4.dll'
    addin_path = lf_root + '\AddInViews\PrincetonInstruments.LightFieldViewV4.dll'
    support_path = lf_root + '\PrincetonInstruments.LightFieldAddInSupportServices.dll'

    addin_class = clr.AddReference(addin_path)
    automation_class = clr.AddReference(automation_path)
    support_class = clr.AddReference(support_path)

    import PrincetonInstruments.LightField as lf

    clr.AddReference("System.Collections")
    clr.AddReference("System.IO")
    from System.Collections.Generic import List
    from System import String
    from System.IO import FileAccess
except Exception as e:
    logger.error(f"Exception occurred during import: {type(e)}")
    logger.error(f"Exception occurred during import: {e}")


class LightfieldApp:
    def __init__(self, visible):

        self._addinbase = lf.AddIns.AddInBase()
        self._automation = lf.Automation.Automation(visible, List[String]())
        self._application = self._automation.LightFieldApplication
        self._experiment = self._application.Experiment

    @property
    def automation(self):
        return self._automation

    @property
    def addinbase(self):
        return self._addinbase

    @property
    def application(self):
        return self._application

    @property
    def experiment(self):
        return self._experiment

    def __del__(self):
        """
        Uses Python garbage collection method used to terminate
        AddInProcess.exe, if this is not done, LightField will not reopen
        properly.
        """
        self.automation.Dispose()
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

    def acquire(self):
        """
        This function retrieves image data with special consideration for the unique configuration of the camera,
        which possesses a single vertical pixel. The following describes the data handling:

        - **Single Frame**:
        - Data is returned as a 2D array representing raw counts from each pixel.
        - A vertical section (spanning 400 pixels) represents a range for wavelength averaging.

        - **Multiple Frames**:
        - Data from successive exposures is added as a new dimension, resulting in a 3D array.
        - Averaging across frames can be done by summing over this additional dimension.
        """

        acquisition_time = self.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime) #to allow the camera to capture the desired amount of data during the specified exposure time.
        num_frames = self.get(lf.AddIns.ExperimentSettings.FrameSettingsFramesToStore)
        self.experiment.Acquire()

        sleep(0.001 * acquisition_time * num_frames)  #sleep delay that waits for the exposure duration of the camera

        while self.experiment.IsRunning:
            sleep(0.1)  #loop that repeatedly checks whether the experiment is still running so it decided when to move to next block of code

        last_file = self.application.FileManager.GetRecentlyAcquiredFileNames().get_Item(0)
        frame_count = self.application.FileManager.OpenFile(last_file, FileAccess.Read)

        if frame_count.Regions.Length == 1:
            if frame_count.Frames == 1:
                frame = frame_count.GetFrame(0, 0)
                data = np.reshape(np.fromiter(frame.GetData(), 'uint16'), [frame.Width, frame.Height], order='F')
            else:
                data = np.array([])
                for i in range(0, frame_count.Frames):
                    frame = frame_count.GetFrame(0, i)
                    new_frame = np.fromiter(frame.GetData(), 'uint16')
                    new_frame = np.reshape(np.fromiter(frame.GetData(), 'uint16'), [frame.Width, frame.Height],order='F')
                    data = np.dstack((data, new_frame)) if data.size else new_frame
            return data
        else:
            logger.warning('frame_count.Regions is not valid. Please retry.')
            logger.info('Frame count: %s', frame_count.Frames)
        return np.array([[]])  # Return an empty 2D numpy array by default

    def close(self):
        """
        Closes the Lightfield application without saving the settings.
        """
        self.automation.Dispose()
        logger.info('Closed AddInProcess.exe')


class Spectrometer():

    def __init__(self, experiment_name=None):
        self._experiment_name = experiment_name
        self.light = LightfieldApp(True)

    def finalize(self):
        """
        Closes the Lightfield application without saving the settings.
        """
        self.light.close()

    @property
    def center_wavelength(self):
        """
        Returns the center wavelength in nanometers.
        """
        return self.light.get(lf.AddIns.SpectrometerSettings.GratingCenterWavelength)

    def get_wavelengths(self):
        """
        Returns the wavelength calibration for a single frame.
        """
        size = self.light.experiment.SystemColumnCalibration.get_Length()
        result = np.empty(size)
        for i in range(size):
            result[i] = self.light.experiment.SystemColumnCalibration[i]
        return result

    @center_wavelength.setter
    def center_wavelength(self, nanometers):
        """
        Sets the spectrometer center wavelength to nanometers.
        """
        #NOTE: The line below addresses bug where if step and glue is selected, doesn't allow setting center wavelength
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
        return self.light.set(lf.AddIns.SpectrometerSettings.GratingCenterWavelength, nanometers)

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
            self._experiment_name = a_name
            self.light.load_experiment(self._experiment_name)

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
        if grating_string in self.gratings_options:
            self.light.set(lf.AddIns.SpectrometerSettings.GratingSelected, grating_string)
        else:
            logger.error(f"Grating {grating_string} is not an options. The options are: {self.gratings_options}")

    @property
    def gratings_options(self):
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
        return self.light.get(lf.AddIns.ExperimentSettings.FrameSettingsFramesToStore)

    @num_frames.setter
    def num_frames(self, num_frames):
        """
        Sets the number of frames to be taken during acquisition to number.
        """
        return self.light.set(lf.AddIns.ExperimentSettings.FrameSettingsFramesToStore, num_frames)

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
        return self.light.set(lf.AddIns.CameraSettings.ShutterTimingExposureTime, ms)

    @property
    def sensor_temperature(self):
        """
        Returns the current sensor temperature (in celcius).
        """
        return self.light.get(lf.AddIns.CameraSettings.SensorTemperatureReading)

    @property
    def temperature_sensor_setpoint(self):
        """
        Returns the sensor setpoint temperature (celcius).
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
        return self.light.set(lf.AddIns.CameraSettings.SensorTemperatureSetPoint, deg_C)

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
            print(f'Unable to perform step and glue due to error: {e}')
            return

        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueStartingWavelength, lambda_min)
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEndingWavelength, lambda_max)

        data = self.light.acquire()
        spectrum = np.mean(data, axis=1) #had to add this here to flatten data so it is not 2D but rather, 1D
        wavelength = np.linspace(lambda_min, lambda_max, data.shape[0])
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
        return spectrum, wavelength
