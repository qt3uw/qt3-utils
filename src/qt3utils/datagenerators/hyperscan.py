import matplotlib
import pickle
from argparse import Namespace
import nipiezojenapy
matplotlib.use('TKAgg')
import matplotlib.pyplot as plt
import numpy as np
from princeton import Spectrometer


piezo_write_channels='ao0,ao1,ao2'
piezo_read_channels='ai0,ai1,ai2' 

controller = nipiezojenapy.PiezoControl(device_name = 'Dev1',
                                  write_channels = piezo_write_channels.split(','),
                                  read_channels = piezo_read_channels.split(','))

s = Spectrometer()
s.initialize()
#set all the settings you need
s.exposure_time = 2000.0 
print('Exposure time: {}ms'.format(s.exposure_time))
s.num_frames = "1"
print('Sensor temperature setpoint: {} C'.format(s.sensor_setpoint))
s.sensor_setpoint = -70.0
print('Sensor temperature: {} C'.format(s.sensor_temperature))
s.center_wavelength = 700.0
print('Number of frames: {}'.format(s.num_frames))

print('Grating: {}'.format(s.grating))

hyperspectral_im = None
z = 43
xs = np.linspace(7, 12, num=11)
ys = np.linspace(10, 15, num=11)
for i, x in enumerate(xs):
    for j, y in enumerate(ys):
        controller.go_to_position(x,y,z)
        spectrum, wavelength = s.acquire_step_and_glue([600.0, 850.0])
        if i==0 and j==0:
            hyperspectral_im = np.zeros((xs.shape[0], ys.shape[0], spectrum.shape[0]))
        hyperspectral_im[i, j, :] = spectrum

mean_spectrum = np.mean(hyperspectral_im, axis=2)

d = {"wavelength":wavelength, "im":hyperspectral_im}

with open('Date: __, Mordi_Data.pkl', 'wb') as f:
    pickle.dump(d, f)

plt.imshow(mean_spectrum, cmap='Reds', interpolation='nearest')
plt.show()

s.finalize()