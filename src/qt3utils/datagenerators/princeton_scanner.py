import numpy as np
import clr
import os
from time import sleep
from System.Collections.Generic import List
from System import String
from System.IO import FileAccess

lf_root = os.environ['LIGHTFIELD_ROOT']
automation_path = lf_root + '\PrincetonInstruments.LightField.AutomationV4.dll'
addin_path = lf_root + '\AddInViews\PrincetonInstruments.LightFieldViewV4.dll'
support_path = lf_root + '\PrincetonInstruments.LightFieldAddInSupportServices.dll'

addin_class = clr.AddReference(addin_path)
automation_class = clr.AddReference(automation_path)
support_class = clr.AddReference(support_path)

import PrincetonInstruments.LightField as lf

class LightFieldM:
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
        self.automation.Dispose()
        print('Closed AddInProcess.exe')
    

    def set(self, setting, value):
        if self.experiment.Exists(setting):
            if self.experiment.IsValid(setting, value):
                self.experiment.SetValue(setting, value)
            else:
                print('Invalid value: {} for setting: {}.'.format(value, setting))
        else:
            print('Invalid setting: {}'.format(setting))

    def get(self, setting):
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

        
        acquisition_time = self.get(lf.AddIns.CameraSettings.ShutterTimingExposureTime)
        num_frames = self.get(lf.AddIns.ExperimentSettings.FrameSettingsFramesToStore)

        self.experiment.Acquire()

        sleep(0.001 * acquisition_time * num_frames)

        while self.experiment.IsRunning:
            sleep(0.1)

        last_file = self.application.FileManager.GetRecentlyAcquiredFileNames().GetItem(0)

        image_set = self.application.FileManager.OpenFile(last_file, FileAccess.Read)

        if image_set.Regions.Length == 1:
            if image_set.Frames == 1:
                frame = image_set.GetFrame(0, 0)
                data = np.reshape(np.fromiter(frame.GetData(), 'uint16'), [frame.Width, frame.Height], order='F')
            else:
                data = np.array([])
                for i in range(0, image_set.Frames):
                    frame = image_set.GetFrame(0, i)
                    new_frame = np.reshape(np.fromiter(frame.GetData(), 'uint16'), [frame.Width, frame.Height], order='F')
                    data = np.dstack((data, new_frame)) if data.size else new_frame
            return data
        else:
            print('image_set.Regions not 1! this needs to be figured out!')

    
    def close(self):
        self.automation.Dispose()
        print('Closed AddInProcess.exe')

    
class Spectrometer:
    GRATINGS = ['[500nm,600][0][0]', '[1.2um,300][1][0]',
                '[500nm,150][2][0]']  # TODO: make it pull gratings from SW directly

    def initialize(self):
        """
        Sets up LightField
        """
        self.lfm = LightFieldM(True)
        self.lfm.load_experiment('LF_Control')

    def finalize(self):
        """
        Closes the application
        """
        self.lfm.close()

    def get_center_wavelength(self):
        """
        Returns the center wavelength in nanometers.
        """
        return self.lfm.Application.Experiment.Spectrometer.GratingCenterWavelength.Value

    def set_center_wavelength(self, nanometers):
        """
        Sets the spectrometer center wavelength to nanometers.
        """
        self.lfm.Application.Experiment.Spectrometer.GratingCenterWavelength.Value = nanometers

    def get_wavelengths(self):
        """
        Returns the wavelength calibration for a single frame.
        """
        return self.lfm.Application.Experiment.SystemColumnCalibration

    def get_grating(self):
        """
        Returns the current grating.
        """
        return self.lfm.Application.Experiment.Spectrometer.GratingSelected.Value

    def set_grating(self, grating):
        """
        Sets the current grating to be the one specified by parameter grating.
        """
        # TODO: figure out the format for setting this
        print('Figure out the format for this')

    def get_gratings(self):
        """
        Returns a list of all installed gratings.
        """
        return self.GRATINGS

    def get_num_frames(self):
        """
        Returns the number of frames taken during the acquisition.
        """
        return self.lfm.Application.Experiment.FrameSettings.FramesToStore.Value

    def set_num_frames(self, num_frames):
        """
        Sets the number of frames to be taken during acquisition to number.
        """
        self.lfm.Application.Experiment.FrameSettings.FramesToStore.Value = num_frames

    def get_exposure_time(self):
        """
        Returns the single frame exposure time (in ms).
        """
        return self.lfm.Application.Experiment.CameraSettings.ShutterTimingExposureTime.Value

    def set_exposure_time(self, ms):
        """
        Sets the single frame exposure time to be ms (in milliseconds).
        """
        self.lfm.Application.Experiment.CameraSettings.ShutterTimingExposureTime.Value = ms

    def acquire_frame(self):
        """
        Acquires a frame (or series of frames) from the spectrometer, and the
        corresponding wavelength data.
        """
        return self.lfm.Acquire(), self.get_wavelengths()

    def acquire_step_and_glue(self, wavelength_range):
        lambda_min = wavelength_range[0]
        lambda_max = wavelength_range[1]

        try:
            self.lfm.Experiment.StepAndGlueEnabled = True
        except:
            self.lfm.Experiment.StepAndGlueEnabled = False
            print('Unable to perform step and glue, check settings.')
            return

        self.lfm.Experiment.StepAndGlueStartingWavelength = lambda_min
        self.lfm.Experiment.StepAndGlueEndingWavelength = lambda_max

        data = self.lfm.acquire()

        wavelength = np.linspace(lambda_min, lambda_max, data.shape[0])

        print('Wavelength data is not strictly correct, this just interpolates.')
        print('TODO: figure out how step and glue determines which wavelengths are used. This might be done in post processing.')
        print('If you want the true values, use the actual .spe file that is generated.')

        self.lfm.Experiment.StepAndGlueEnabled = False

        return data, wavelength
    

"""
Note for Emmanuel, no clue if the code below works but its there to try call the class to run it. Might be better way to do it

if __name__ == "__main__":
    spectrometer = Spectrometer()
    spectrometer.initialize()

    spectrometer.finalize()
"""

