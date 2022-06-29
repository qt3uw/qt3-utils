import numpy as np
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.animation as animation

import nidaqmx
import ctypes
import nidaqmx._lib  # Due to NIDAQmx C-API bug needed to bypass property getter (according to qudi)
import nidaqmx.stream_readers
import time


def configure_tasks(post_fix_task_name = None,
                    device_name = 'Dev1',
                    clock_counter = 'ctr1',
                    clock_di_line = 'port0',
                    edge_input_channel = 'PFI12',
                    edge_input_counter = 'ctr2',
                    clock_rate = 1000,
                    N_data_samples_to_acquire = 100,
                    trigger_input = None,
                    new_edge_task = False,
                    new_clock_task = False):

    clock_task_name = f'sample_clock{post_fix_task_name}'
    clock_task = nidaqmx.Task(clock_task_name)

    if new_clock_task:
        clock_task.di_channels.add_di_chan(f'{device_name}/{clock_di_line}')
        clock_task.timing.cfg_samp_clk_timing(clock_rate,
                                    sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)

        clock_channel = f'/{device_name}/di/SampleClock'

    else:
        #this adds the clock signal to the output channel
        #is this necessary?
        clock_task.co_channels.add_co_pulse_chan_freq(
                '/{0}/{1}'.format(device_name, clock_counter),
                freq=clock_rate,
                idle_state=nidaqmx.constants.Level.LOW)

        # clock_task.timing.cfg_implicit_timing(
        #     sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
        #     samps_per_chan=n_steps+2) #qudi configures with n_steps + 1, should recheck why. suspicious extra "1" floating around (n_steps = 101)

        clock_task.timing.cfg_implicit_timing(
            sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
            samps_per_chan=clock_rate) #qudi configures with n_steps + 1, should recheck why. suspicious extra "1" floating around (n_steps = 101)

        clock_channel = '/{0}InternalOutput'.format(clock_task.channel_names[0])

    edge_detector_task_name = f'edge_input{post_fix_task_name}'

    edge_detector_task = nidaqmx.Task(edge_detector_task_name)

    #todo -- try to replace all of this with edge_detector_task.add_ci_count_edges_chan



    ctr_name = f'/{device_name}/{edge_input_counter}'
    chnl_name = f'/{device_name}/{edge_input_channel}'

    if new_edge_task: #following nspyre recipe
        edge_detector_task.ci_channels.add_ci_count_edges_chan(
                                    ctr_name,
                                    edge=nidaqmx.constants.Edge.RISING,
                                    initial_count=0,
                                    count_direction=nidaqmx.constants.CountDirection.COUNT_UP)
        edge_detector_task.ci_channels.all.ci_count_edges_term = chnl_name
        edge_detector_task.timing.cfg_samp_clk_timing(clock_rate,
                                                      source=clock_channel,
                                                      active_edge=nidaqmx.constants.Edge.RISING,
                                                      sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
        # edge_detector_task.timing.cfg_samp_clk_timing(clock_rate,
        #                                               source=clock_channel,
        #                                               active_edge=nidaqmx.constants.Edge.RISING,
        #                                               sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
        #                                               samps_per_chan=N_data_samples_to_acquire )

    else:
        # why does qudi count the period of signal? In units of "ticks" -- is that the same as edge counting?

        edge_detector_task.ci_channels.add_ci_period_chan(
                            ctr_name,
                            min_val=0,
                            max_val=100000000,
                            units=nidaqmx.constants.TimeUnits.TICKS,
                            edge=nidaqmx.constants.Edge.RISING)
        # I get no data when I swap out the line above for this line
        # edge_detector_task.ci_channels.add_ci_count_edges_chan(
        #                             ctr_name,
        #                             edge=nidaqmx.constants.Edge.RISING,
        #                             initial_count=0,
        #                             count_direction=nidaqmx.constants.CountDirection.COUNT_UP)

        # from qudi -- apparently this overcomes some kind of bug in the C-library, according to comments in qudi code
        print('here')
        try:
            # this sets the counter to read from the appropriate terminal
            nidaqmx._lib.lib_importer.windll.DAQmxSetCIPeriodTerm(
                edge_detector_task._handle,
                ctypes.c_char_p(ctr_name.encode('ascii')),
                ctypes.c_char_p(clock_channel.encode('ascii')))

            #this tells the counter which clock to use
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

        edge_detector_task.timing.cfg_implicit_timing(sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                                      samps_per_chan=N_data_samples_to_acquire)

    if trigger_input:
        edge_detector_task.triggers.arm_start_trigger.trig_type =  nidaqmx.constants.TriggerType.DIGITAL_EDGE
        edge_detector_task.triggers.arm_start_trigger.dig_edge_edge =  nidaqmx.constants.Edge.RISING
        edge_detector_task.triggers.arm_start_trigger.dig_edge_src = f'/{device_name}/{trigger_input}'


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

#Configure the NI DAQ
device_name = 'Dev1'
read_write_timeout = 10
clock_counter = 'ctr1'
edge_input_channel = 'PFI12'
edge_input_counter = 'ctr2'
clock_rate = 10000 #Hz
N_data_samples_to_acquire = 100
daq_time = N_data_samples_to_acquire / clock_rate

clock_task, edge_detector_task, edge_detector_reader = configure_tasks('_oscilloscope',
                                                                        device_name = device_name,
                                                                        clock_counter = clock_counter,
                                                                        clock_di_line = 'port0',
                                                                        edge_input_channel = edge_input_channel,
                                                                        edge_input_counter = edge_input_counter,
                                                                        clock_rate = clock_rate,
                                                                        N_data_samples_to_acquire = N_data_samples_to_acquire,
                                                                        trigger_input = None,
                                                                        new_edge_task = True,
                                                                        new_clock_task = True
)

print('starting clock')
clock_task.start()


def run_once(detector_task, detector_reader, clock_rate,  N_samples,  read_write_timeout=10, pulser = None):

    detector_task.wait_until_done()
    detector_task.start()
    data_buffer = np.zeros(N_samples)

    if pulser:
        pulser.software_trigger()

    read_samples = detector_reader.read_many_sample_double(
                            data_buffer,
                            number_of_samples_per_channel=N_samples,
                            timeout=read_write_timeout)
    detector_task.stop()
    try:
        assert read_samples == N_samples
    except Exception as e:
        print(e)
        print(f'{read_samples} != {N_samples}')
        raise e

    return data_buffer

def emitter():
    """return counts per second """
    while True:
        #data_sample = run_once(edge_detector_task, edge_detector_reader)
        data_sample = run_once(edge_detector_task, edge_detector_reader, clock_rate, N_data_samples_to_acquire, read_write_timeout = 10, pulser = None)
        yield data_sample.sum()/daq_time



fig, ax = plt.subplots()
scope = Scope(ax)

# pass a generator in "emitter" to produce data for the update func
ani = animation.FuncAnimation(fig, scope.update, emitter, interval=20,
                              blit=True)

plt.show()


#clean up
print('cleaning up')
clock_task.stop()
clock_task.close()
edge_detector_task.close()
