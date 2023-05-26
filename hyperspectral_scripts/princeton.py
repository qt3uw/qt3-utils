import os
import numpy as np
from time import sleep

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
    print(f"Exception occurred during import: {e}")


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
        print('Closed AddInProcess.exe')

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
                print('Invalid value: {} for setting: {}.'.format(value, setting))

        else:

            # TODO: might need to add a proper exception
            print('Invalid setting:{}'.format(setting))

        return

    def get(self, setting):
        """
        Helper function for getting experiment parameters with a basic check
        to see if a specific setting is valid.
        """

        if self.experiment.Exists(setting):

            value = self.experiment.GetValue(setting)

        else:

            value = []
            print('Invalid setting: {}'.format(setting))

        return value

    def load_experiment(self, value):
        self.experiment.Load(value)

    def acquire(self):
        """
        Helper function to acquire the data from the PIXIS-style cameras.
        Need to check array reorganization since there is only a single vertical pixel.
        For a single frame, the data is returned as a 2D array (just raw counts
        from each pixel). Taking a section in the vertical (400-pixel) direction
        corresponds to wavelength averaging.
        For multiple frames, each exposure is stacked in a third dimension, so
        averaging can be performed simply by summing over the different planes.
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

                    new_frame = np.reshape(np.fromiter(frame.GetData(), 'uint16'), [frame.Width, frame.Height],
                                           order='F')
                    data = np.dstack((data, new_frame)) if data.size else new_frame

            return data


        else:
            
            print('frame_count.Regions is not. Please retry.')
            print(frame_count.Frames)
        

    def close(self):
        """
        Similar to finalize as seen a few lines below. 
        """
        self.automation.Dispose()
        print('Closed AddInProcess.exe')


class Spectrometer():
    GRATINGS = ['[500nm,600][0][0]', '[1.2um,300][1][0]',
                '[500nm,150][2][0]']  # TODO: make it so that it automatically scrapes the grating settings

    def initialize(self):
        """
        Sets up LightField and loads an empty experiment called 
        "LF_Control that we use for automation purposes.
        """
        self.light = LightfieldApp(True)
        self.light.load_experiment('SiV-FIB')

    #TODO:Need to create a setting that automatically deletes all saved scans on pc.
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
        # this avoids bug where if step and glue is selected, doesn't allow setting center wavelength
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)

        return self.light.set(lf.AddIns.SpectrometerSettings.GratingCenterWavelength, nanometers)

    @property
    def grating(self):
        """
        Returns the current grating.
        """
        return self.light.get(lf.AddIns.SpectrometerSettings.GratingSelected)

    @grating.setter
    def grating(self, grating):
        """
        Sets the current grating to be the one specified by parameter grating.
        """
        # TODO: figure out the format for setting this

        print('still need to figure out the format for this')

    @property
    def gratings(self):
        """
        Returns a list of all installed gratings.
        """
        break_down = False

        if break_down:

            import re

            for g in GRATINGS:
                match = re.search(r"\[(\d+\.?\d+[nu]m),(\d+)\]\[(\d+)\]\[(\d+)\])", g)
                blaze, g_per_mm, slot, turret = match.groups()

        return GRATINGS

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
    def sensor_setpoint(self):
        """
        Returns the sensor setpoint temperature (celcius).
        """
        return self.light.get(lf.AddIns.CameraSettings.SensorTemperatureSetPoint)

    @sensor_setpoint.setter
    def sensor_setpoint(self, deg_C):
        """
        Sets the sensor target temperature (in degrees Celsius) to deg_C.
        """
        return self.light.set(lf.AddIns.CameraSettings.SensorTemperatureSetPoint, deg_C)

    def acquire_frame(self):
        """
        Acquires a frame (or series of frames) from the spectrometer, and the
        corresponding wavelength data.
        """
        return self.light.acquire(), self.get_wavelengths()

    def acquire_step_and_glue(self, wavelength_range, bin=(0, 400)):
        """
        Acquires a step and glue (wavelength sweep) over the specified range.
        Wavelength range must have two elements (both in nm), corresponding
        to the start and end wavelengths.
        Please note that the wavelength must be calibrated for this to be useful.

        Note: Wavelength data is not strictly correct, this just interpolates.
        If you want the true values, use the actual .spe file that is generated.
        TODO: figure out how step and glue determines which wavelengths are used. 
        Theory is that this might be done in post processing.

        bin = (min, max) for binned image rows, defaults to entire image
        """

        lambda_min = wavelength_range[0]
        lambda_max = wavelength_range[1]

        try:

            self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, True)

        except:

            self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEnabled, False)
            print('Unable to perform step and glue, please check settings.')

            return

        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueStartingWavelength, lambda_min)
        self.light.set(lf.AddIns.ExperimentSettings.StepAndGlueEndingWavelength, lambda_max)

        data = self.light.acquire()
        if data.shape[-1] == 1:
            spectrum = data.flatten()
        else:
            spectrum = np.sum(data[:, bin[0]:bin[1]], axis=1)

        wavelength = np.linspace(lambda_min, lambda_max, data.shape[0])

        return spectrum, wavelength


