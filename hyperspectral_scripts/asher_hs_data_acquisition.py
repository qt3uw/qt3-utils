import matplotlib
import pickle
from argparse import Namespace
import nipiezojenapy
from princeton import Spectrometer
matplotlib.use('TKAgg')
import matplotlib.pyplot as plt
import numpy as np

piezo_write_channels = 'ao0,ao1,ao2'
piezo_read_channels = 'ai0,ai1,ai2'

controller = nipiezojenapy.PiezoControl(device_name = 'Dev1',
                                  write_channels = piezo_write_channels.split(','),
                                  read_channels = piezo_read_channels.split(','))

s = Spectrometer()
s.initialize()

# User settings
data_path = 'asher_20230526_corner.pkl'

s.exposure_time = 5E3  # ms
wavelength_range = (600., 850.)  # in nm
spectrometer_bin = (195, 205) # min, max row for spectrometer image binning

x_lin = np.linspace(50, 60, num=5)  # in micron
y_lin = np.linspace(45, 55, num=5)  # in micron
z = 40 # in micron


s.sensor_setpoint = -70.0 # °C
s.center_wavelength = 700.0


#Print settings
print('Exposure time: {}ms'.format(s.exposure_time))
s.num_frames = "1"
print('Sensor temperature setpoint: {} C'.format(s.sensor_setpoint))
print('Sensor temperature: {} C'.format(s.sensor_temperature))
print('Number of frames: {}'.format(s.num_frames))

print('Grating: {}'.format(s.grating))

hyperspectral_im = None


xs, ys = np.meshgrid(x_lin, y_lin)

for i, x in enumerate(x_lin):
    for j, y in enumerate(y_lin):
        controller.go_to_position(x, y, z)
        spectrum, wavelength = s.acquire_step_and_glue(wavelength_range, bin=spectrometer_bin)
        if i == 0 and j == 0:
            hyperspectral_im = np.zeros((y_lin.shape[0], x_lin.shape[0], spectrum.shape[0]))
        hyperspectral_im[j, i, :] = spectrum

mean_spectrum = np.mean(hyperspectral_im, axis=2)

d = {"wavelength":wavelength, "im":hyperspectral_im, 'x':xs, 'y':ys, 'z':z}

with open(data_path, 'wb') as f:
    pickle.dump(d, f)

s.finalize()

plt.imshow(mean_spectrum, cmap='Reds', interpolation='nearest')
plt.show()