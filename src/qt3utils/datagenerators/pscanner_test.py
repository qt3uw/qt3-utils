import clr
import numpy as np
import matplotlib
matplotlib.use('TKAgg')
import matplotlib.pyplot as plt

# Import the HSR750 class from the princeton_spectrometers module
from pscanner import Spectrometer


s = Spectrometer()
s.initialize()

print('Exposure time: {}ms'.format(s.exposure_time))
s.exposure_time = 2.0
print('Exposure time: {}ms'.format(s.exposure_time))
s.exposure_time = 1.5
print('Exposure time: {}ms'.format(s.exposure_time))

print('Number of frames: {}'.format(s.num_frames))
s.num_frames = "1"
print('Number of frames: {}'.format(s.num_frames))
s.num_frames = "10"
print('Number of frames: {}'.format(s.num_frames))

print('Sensor temperature setpoint: {} C'.format(s.sensor_setpoint))
s.sensor_setpoint = -60.0
print('Sensor temperature setpoint: {} C'.format(s.sensor_setpoint))
s.sensor_setpoint = -70.0
print('Sensor temperature setpoint: {} C'.format(s.sensor_setpoint))

print('Sensor temperature: {} C'.format(s.sensor_temperature))

print('Grating: {}'.format(s.grating))

print('Center wavelength:{}'.format(s.center_wavelength))
s.center_wavelength = 700.0
print('Center wavelength:{}'.format(s.center_wavelength))
s.center_wavelength = 730.0
print('Center wavelength:{}'.format(s.center_wavelength))

"""
print('Acquiring a single frame')
s.num_frames = "1"
data, wavelength = s.acquire_frame()
print(data.shape)
"""


s.num_frames = "3"
# print('Acquiring 10 frames')
# data, wavelength = s.acquire_frame()
# print(data.shape)

im_data, wavelength = s.acquire_step_and_glue([400.0, 450.0])
spectrum = np.sum(im_data, axis=1)
plt.plot(wavelength, spectrum)
plt.show()


s.finalize()

