import sys
import os

import clr

# Import System.IO for saving and opening files
from System.IO import *
from System.Threading import AutoResetEvent

# Import C compatible List and String
from System import String
from System.Collections.Generic import List

# Add needed dll references
sys.path.append(os.environ['LIGHTFIELD_ROOT'])
sys.path.append(os.environ['LIGHTFIELD_ROOT']+"\\AddInViews")
clr.AddReference('PrincetonInstruments.LightFieldViewV5')
clr.AddReference('PrincetonInstruments.LightField.AutomationV5')
clr.AddReference('PrincetonInstruments.LightFieldAddInSupportServices')

from PrincetonInstruments.LightField.Automation import Automation
from PrincetonInstruments.LightField.AddIns import SpectrometerSettings


class HSR750:
    def __init__(self):
        self._start_wavelength = 600.0
        self._end_wavelength = 700.0
        self._exposure_time = 0.1

        self.auto = Automation(True, List[String]())
        self.experiment = self.auto.LightFieldApplication.Experiment
        self.acquireCompleted = AutoResetEvent(False)

    @property
    def start_wavelength(self) -> float:
        return self._start_wavelength

    @start_wavelength.setter
    def start_wavelength(self, wavelength: float):
        self._start_wavelength = wavelength

    @property
    def end_wavelength(self) -> float:
        return self._end_wavelength

    @end_wavelength.setter
    def end_wavelength(self, wavelength: float):
        self._end_wavelength = wavelength

    @property
    def exposure_time(self) -> float:
        return self._exposure_time

    @exposure_time.setter
    def exposure_time(self, exposure_time: float):
        self._exposure_time = exposure_time

    def load_settings(self) -> None:
        """
        Load the settings for the spectrometer.
        """
        self.experiment.SetValue(SpectrometerSettings.GratingSelected, f'[{self.start_wavelength}nm, {self.end_wavelength}][1][0]')
        self.experiment.SetValue(SpectrometerSettings.SpectrometerTriggerMode, 'Internal')
        self.experiment.ExposureTime = self.exposure_time

    def take_spectrum(self) -> None:
        """
        Take a spectrum from the spectrometer.
        """
        self.experiment.Acquire()

    def get_current_spectrum(self) -> None:
        """
        Get the current spectrum from the spectrometer.
        """
        return self.experiment.GetData()
    
    def generate_data(self, exposure_times: List[float], num_spectra: int) -> List[List[float]]:
        """
        Generate data by taking multiple spectra with varying exposure times.
        :param exposure_times: a list of exposure times to use
        :param num_spectra: the number of spectra to take for each exposure time
        :return: a list of spectra, where each spectrum is a list of floats representing intensity values
        """
        data = []
        for exposure_time in exposure_times:
            self.exposure_time = exposure_time
            self.load_settings()
            spectra = []
            for i in range(num_spectra):
                self.take_spectrum()
                spectra.append(self.get_current_spectrum())
            data.append(spectra)
        return data