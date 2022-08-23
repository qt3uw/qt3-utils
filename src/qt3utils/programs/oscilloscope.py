import time
import argparse
import collections

import numpy as np
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import nidaqmx

import qt3utils.nidaq

parser = argparse.ArgumentParser(description='Oscilloscope for the SPCM.')
parser.add_argument('--daq',default = 'Dev1', type=str,
                    help='NI DAQ Device Name')
parser.add_argument('--signal-terminal',default = 'PFI0', type=str,
                    help='NI DAQ terminal connected to input digital TTL signal')
parser.add_argument('--signal-counter',default = 'ctr2', type=str,
                    help='NI DAQ interal counter')
parser.add_argument('--clock-terminal', default = None, type=str,
                    help='Clock Terminal. If None (default) uses internal NI DAQ clock')
parser.add_argument('--scope-width', default = 250, type=int,
                    help='NI DAQ read/write timeout in seconds.')
parser.add_argument('--clock-rate', default = 10000, type=int,
                    help='In Hz. Only used when using internal clock')
parser.add_argument('--num-data-samples-per-batch', default = 1000, type=int,
                    help='Number of data points to acquire per daq request.')
parser.add_argument('--rwtimeout', default = 10, type=int,
                    help='NI DAQ read/write timeout in seconds.')
parser.add_argument('--randomtest', action = 'store_true',
                    help='When true, program will run showing random numbers. This is for development testing.')
args = parser.parse_args()

#TODO entry points in setup.py should be defined (perhaps: qt3utils-scope) for easy launch



class Scope:
    def __init__(self, ax, width=50):
        self.ax = ax
        self.ydata = collections.deque(np.zeros(width))
        self.line, = self.ax.plot(np.arange(width), self.ydata)

    def update(self, y):
        self.ydata.popleft()
        self.ydata.append(y)

        #this doesn't work with blit = True.
        #there's a workaround if we need blit = true
        #https://stackoverflow.com/questions/53423868/matplotlib-animation-how-to-dynamically-extend-x-limits
        #need to sporadically call
        #fig.canvas.resize_event()

        #could add code here to resize if 10% of the data are outside of the
        #current range. or if the average of the most recent 10% is outside
        #of the current min or max.
        delta = 0.1*np.max(self.ydata)
        self.ax.set_ylim(np.max([0, np.min(self.ydata) - delta]), np.max(self.ydata) + delta)
        self.line.set_ydata(self.ydata)
        return self.line,


def read_daq_buffer(counter_task, detector_reader,  N_samples,  read_write_timeout):

    data_buffer = np.zeros(N_samples)
    counter_task.start()

    samples_read = detector_reader.read_many_sample_double(
                            data_buffer,
                            number_of_samples_per_channel=N_samples,
                            timeout=read_write_timeout)

    counter_task.stop()
    return data_buffer, samples_read


def run():
    fig, ax = plt.subplots()
    scope = Scope(ax, args.scope_width)

    if args.randomtest is False:
        print('configuring nidaq tasks')

        nidaq_config = qt3utils.nidaq.EdgeCounter(args.daq)
        nidaq_config.reset_daq()

        if args.clock_terminal is None:
            nidaq_config.configure_di_clock(clock_rate = args.clock_rate)
            clock_terminal = nidaq_config.clock_task_config['clock_terminal']
        else:
            clock_terminal = args.clock_terminal

        nidaq_config.configure_counter_period_measure(
            daq_counter = args.signal_counter,
            source_terminal = args.signal_terminal,
            N_samples_to_acquire_or_buffer_size = args.num_data_samples_per_batch,
            clock_terminal = args.clock_terminal,
            trigger_terminal = None,
            sampling_mode = nidaqmx.constants.AcquisitionType.FINITE)

        nidaq_config.create_counter_reader()


        # pass a generator in "emitter" to produce data for the update func
        print('starting clock')
        nidaq_config.clock_task.start()

        def emitter():
            """return counts per second """
            while True:
                #data_sample = run_once(edge_detector_task, edge_detector_reader)
                data_sample, samples_read = read_daq_buffer(nidaq_config.counter_task,
                                                            nidaq_config.counter_reader,
                                                            args.num_data_samples_per_batch,
                                                            args.rwtimeout)
                yield data_sample.sum()/(samples_read / args.clock_rate)
    else: #random test
        def emitter():
            offset = 100
            while True:
                if np.random.random(1)[0] < 0.01:
                    offset = np.random.choice(np.arange(100, 100000, 500))

                yield 0.2*offset*np.random.random(1)[0] + offset

    ani = animation.FuncAnimation(fig, scope.update, emitter, interval=50,
                                  blit=False)

    plt.show()


    if args.randomtest is False:
        #clean up
        print('cleaning up')
        nidaq_config.clock_task.stop()
        nidaq_config.clock_task.close()
        nidaq_config.counter_task.stop()
        nidaq_config.counter_task.close()

if __name__ == '__main__':
    run()
