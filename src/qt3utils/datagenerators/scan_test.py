import clr
import numpy

# Import the HSR750 class from the princeton_spectrometers module
from princeton_scanner import Spectrometer

spectrometer = Spectrometer()


spectrometer.initialize()

exposure_time = 20
spectrometer.set_exposure_time(exposure_time)

data, wavelengths = spectrometer.acquire_frame()

print(data)
print(wavelengths)

spectrometer.finalize()