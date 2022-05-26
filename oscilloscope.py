import numpy as np
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.animation as animation

import nidaqmx
import ctypes
import nidaqmx._lib  # Due to NIDAQmx C-API bug needed to bypass property getter (according to qudi)
import nidaqmx.stream_readers
import time

#Configure the NI DAQ
device_name = 'Dev1'
read_write_timeout = 10
clock_counter = 'ctr1'
edge_input_channel = 'PFI0'
edge_input_counter = 'ctr2'
clock_rate = 10000 #Hz
N_data_samples_to_acquire = 100

def configure_tasks(post_fix_task_name = None):

    clock_task_name = f'sample_clock{post_fix_task_name}'
    clock_task = nidaqmx.Task(clock_task_name)

    #this adds the clock singal to the output channel
    clock_task.co_channels.add_co_pulse_chan_freq(
            '/{0}/{1}'.format(device_name, clock_counter),
            freq=clock_rate,
            idle_state=nidaqmx.constants.Level.LOW)

    # clock_task.timing.cfg_implicit_timing(
    #     sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
    #     samps_per_chan=n_steps+2) #qudi configures with n_steps + 1, should recheck why. suspicious extra "1" floating around (n_steps = 101)

    clock_task.timing.cfg_implicit_timing(
        sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
        samps_per_chan=1000) #qudi configures with n_steps + 1, should recheck why. suspicious extra "1" floating around (n_steps = 101)


    edge_detector_task_name = f'edge_input{post_fix_task_name}'

    edge_detector_task = nidaqmx.Task(edge_detector_task_name)

    ctr_name = '/{0}/{1}'.format(device_name, edge_input_counter)
    edge_detector_task.ci_channels.add_ci_period_chan(
                        ctr_name,
                        min_val=0,
                        max_val=100000000,
                        units=nidaqmx.constants.TimeUnits.TICKS,
                        edge=nidaqmx.constants.Edge.RISING)

    # from qudi -- apparently this overcomes some kind of bug in the C-library, according to comments in qudi code
    chnl_name = '/{0}/{1}'.format(device_name, edge_input_channel)
    clock_channel = '/{0}InternalOutput'.format(clock_task.channel_names[0])

    try:
        nidaqmx._lib.lib_importer.windll.DAQmxSetCIPeriodTerm(
            edge_detector_task._handle,
            ctypes.c_char_p(ctr_name.encode('ascii')),
            ctypes.c_char_p(clock_channel.encode('ascii')))
        nidaqmx._lib.lib_importer.windll.DAQmxSetCICtrTimebaseSrc(
            edge_detector_task._handle,
            ctypes.c_char_p(ctr_name.encode('ascii')),
            ctypes.c_char_p(chnl_name.encode('ascii')))
    except:
        nidaqmx._lib.lib_importer.cdll.DAQmxSetCIPeriodTerm(
            edge_detector_task._handle,
            ctypes.c_char_p(ctr_name.encode('ascii')),
            ctypes.c_char_p(clock_channel.encode('ascii')))
        nidaqmx._lib.lib_importer.cdll.DAQmxSetCICtrTimebaseSrc(
            edge_detector_task._handle,
            ctypes.c_char_p(ctr_name.encode('ascii')),
            ctypes.c_char_p(chnl_name.encode('ascii')))

    edge_detector_task.timing.cfg_implicit_timing(
        sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
        samps_per_chan=N_data_samples_to_acquire)

    edge_detector_reader = nidaqmx.stream_readers.CounterReader(edge_detector_task.in_stream)

    return clock_task, edge_detector_task, edge_detector_reader

class Scope:
    def __init__(self, ax, maxt=1000, dt=1):
        self.ax = ax
        self.dt = dt
        self.maxt = maxt
        self.tdata = []
        self.ydata = []
        self.line = Line2D(self.tdata, self.ydata)
        self.ax.add_line(self.line)
        self.ax.set_xlim(0, self.maxt)

    def update(self, y):
        if len(self.tdata) > 0:
            lastt = self.tdata[-1]
            if lastt > self.tdata[0] + self.maxt:  # reset the arrays
                self.tdata = [self.tdata[-1]]
                self.ydata = [self.ydata[-1]]
                self.ax.set_xlim(self.tdata[0], self.tdata[0] + self.maxt)
                self.ax.figure.canvas.draw()

        if len(self.tdata) > 0:
            t = self.tdata[-1] + self.dt
        else:
            t = self.dt
        self.tdata.append(t)
        self.ydata.append(y)
        self.ax.set_ylim(np.min(self.ydata)*.95, 1.1*np.max(self.ydata))

        self.line.set_data(self.tdata, self.ydata )
        return self.line,


print('configuring tasks')
clock_task, edge_detector_task, edge_detector_reader = configure_tasks('_oscilloscope')

print('starting clock')
clock_task.start()

def run_once(detector_task, detector_reader):
    detector_task.start()
    data_buffer = np.zeros(N_data_samples_to_acquire)
    read_samples = detector_reader.read_many_sample_double(
                            data_buffer,
                            number_of_samples_per_channel=N_data_samples_to_acquire,
                            timeout=read_write_timeout)
    detector_task.stop()
    assert read_samples == N_data_samples_to_acquire
    return data_buffer

def emitter():
    """return the mean value """
    while True:
        data_sample = run_once(edge_detector_task, edge_detector_reader)
        yield data_sample.mean()*clock_rate



fig, ax = plt.subplots()
scope = Scope(ax)

# pass a generator in "emitter" to produce data for the update func
ani = animation.FuncAnimation(fig, scope.update, emitter, interval=50,
                              blit=True)

plt.show()


#clean up
print('cleaning up')
clock_task.stop()
clock_task.close()
edge_detector_task.close()
