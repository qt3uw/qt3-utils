import clr
import numpy as np
import matplotlib
matplotlib.use('TKAgg')
import matplotlib.pyplot as plt

# Import the HSR750 class from the princeton_spectrometers module
from princeton import Spectrometer

s = Spectrometer()
s.initialize()

s.exposure_time = 2.0
print('Exposure time: {}ms'.format(s.exposure_time))

s.sensor_setpoint = -70.0
print('Sensor temperature setpoint: {} C'.format(s.sensor_setpoint))

print('Sensor temperature: {} C'.format(s.sensor_temperature))

print('Grating: {}'.format(s.grating)) #Grating still needs to be fixed

s.center_wavelength = 700.0
print('Center wavelength:{}'.format(s.center_wavelength))

"""
print('Acquiring a single frame')
s.num_frames = "1"
data, wavelength = s.acquire_frame()
print(data.shape)
"""

"""
print('Acquiring 10 frames')
s.num_frames = "10"
data, wavelength = s.acquire_frame()
print(data.shape)
"""

s.num_frames = "3"
print('Number of frames: {}'.format(s.num_frames))

#below code plots your 3D np array (data and wavelength)

im_data, wavelength = s.acquire_step_and_glue([400.0, 450.0])
spectrum = np.sum(im_data, axis=1)
plt.plot(wavelength, spectrum)
plt.show()

s.finalize()

