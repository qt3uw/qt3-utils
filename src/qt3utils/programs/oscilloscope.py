import time
import argparse
import collections

import numpy as np
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import nidaqmx

import qt3utils.nidaq

parser = argparse.ArgumentParser(description='Oscilloscope for the NI DAQ (PCIx 6363) digital input terminal.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-d', '--daq', default = 'Dev1', type=str, metavar = 'daq_name',
                    help='NI DAQ Device Name')
parser.add_argument('-st', '--signal-terminal', metavar = 'terminal', default = 'PFI0', type=str,
                    help='NI DAQ terminal connected to input digital TTL signal')
parser.add_argument('-w', '--scope-width', metavar = 'width', default = 250, type=int,
                    help='Number of measurements to display in window.')
parser.add_argument('-c', '--clock-rate', metavar = 'rate (Hz)', default = 10000, type=int,
                    help='''Specifies the clock rate in Hz. If using an external clock,
                    you should specifiy the clock rate here so that the correct counts per
                    second are displayed. If using the internal NI DAQ clock (default behavior),
                    this value specifies the clock rate to use. Per the NI DAQ manual,
                    use a suitable clock rate for the device for best performance, which is an integer
                    multiple downsample of the digital sample clock.''')
parser.add_argument('-n', '--num-data-samples-per-batch', metavar = 'N', default = 1000, type=int,
                    help='''Number of data points to acquire per DAQ batch request.
                           Note that only ONE data point is shown in the scope.
                           After each request to the NI DAQ for data, the mean count
                           rate from the batch is computed and displayed. Increasing
                           the "num-data-samples-per-batch" should reduce your noise, but
                           slow the response of the scope. Increase this value if the
                           scope appears too noisy.''')
parser.add_argument('-ct', '--clock-terminal', metavar = 'terminal', default = None, type=str,
                    help='''Specifies the digital input terminal to the NI DAQ to use for a clock.
                            If None, which is the default, the internal NI DAQ clock is used.''')
parser.add_argument('-to', '--rwtimeout', metavar = 'seconds', default = 10, type=int,
                    help='NI DAQ read/write timeout in seconds.')
parser.add_argument('-sc', '--signal-counter', metavar = 'ctrN', default = 'ctr2', type=str,
                    help='NI DAQ interal counter (ctr1, ctr2, ctr3, ctr4)')
parser.add_argument('-r', '--randomtest', action = 'store_true',
                    help='When true, program will run showing random numbers. This is for development testing.')
parser.add_argument('-aut', '--animation-update-interval', metavar = 'milliseconds', default = 25,
                    help='''Sets the animation update period, t, (in milliseconds).
                    This is the time delay between calls to acquire new data.
                    You should be limited by the data acquisition time = N / clock_rate.''')
args = parser.parse_args()

#TODO entry points in setup.py should be defined (perhaps: qt3utils-scope) for easy launch



class Scope:
    def __init__(self, fig, ax, width=50):
        self.fig = fig
        self.ax = ax
        self.ydata = collections.deque(np.zeros(width))
        self.line, = self.ax.plot(self.ydata)
        self.ax.set_ylabel('counts / sec')
        self.ax.ticklabel_format(style='sci',scilimits=(-3,4),axis='y')

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
        new_min = np.max([0, np.min(self.ydata) - delta])
        new_max = np.max(self.ydata) + delta
        current_min, current_max = self.ax.get_ylim()
        if (np.abs((new_min - current_min)/(current_min)) > 0.12) or (np.abs((new_max - current_max)/(current_max)) > 0.12):
            self.ax.set_ylim(np.max([0.01, np.min(self.ydata) - delta]), np.max(self.ydata) + delta)
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
    scope = Scope(fig, ax, args.scope_width)

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
            current_direction = 1
            while True:
                if np.random.random(1)[0] < 0.05:
                    if np.random.random(1)[0] < 0.1:
                        current_direction = -1 * current_direction
                    offset += current_direction*np.random.choice(np.arange(0, 1000, 50))

                    if offset < 100:
                        offset = 100
                        current_direction = 1

                yield 0.2*offset*np.random.random(1)[0] + offset

    ani = animation.FuncAnimation(fig, scope.update, emitter, interval=args.animation_update_interval, blit=False)

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
