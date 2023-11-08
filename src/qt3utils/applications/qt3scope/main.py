import time
import argparse
import collections
import tkinter as Tk
import logging

import numpy as np
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import nidaqmx

import qt3utils.nidaq
import qt3utils.datagenerators as datasources

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='NI DAQ (PCIx 6363) digital input terminal count rate meter.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-d', '--daq-name', default = 'Dev1', type=str, metavar = 'daq_name',
                    help='NI DAQ Device Name')
parser.add_argument('-st', '--signal-terminal', metavar = 'terminal', default = 'PFI0', type=str,
                    help='NI DAQ terminal connected to input digital TTL signal')
parser.add_argument('-w', '--scope-width', metavar = 'width', default = 500, type=int,
                    help='Number of measurements to display in window.')
parser.add_argument('-c', '--clock-rate', metavar = 'rate (Hz)', default = 100000, type=int,
                    help='''Specifies the clock rate in Hz. If using an external clock,
                    you should specifiy the clock rate here so that the correct counts per
                    second are displayed. If using the internal NI DAQ clock (default behavior),
                    this value specifies the clock rate to use. Per the NI DAQ manual,
                    use a suitable clock rate for the device for best performance, which is an integer
                    multiple downsample of the digital sample clock.''')
parser.add_argument('-n', '--num-data-samples-per-batch', metavar = 'N', default = 1500, type=int,
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
parser.add_argument('-aut', '--animation-update-interval', metavar = 'milliseconds', default = 20,
                    help='''Sets the animation update period, t, (in milliseconds).
                    This is the time delay between calls to acquire new data.
                    You should be limited by the data acquisition time = N / clock_rate.''')

args = parser.parse_args()



class ScopeFigure:

    def __init__(self, width=50, fig = None, ax = None):
        if ax == None:
            fig, ax = plt.subplots()
            self.fig = fig
            self.ax = ax
        else:
            self.fig = fig
            self.ax = ax

        self.ydata = collections.deque(np.zeros(width))
        self.line, = self.ax.plot(self.ydata)
        self.ax.set_ylabel('counts / sec')
        self.ax.ticklabel_format(style='sci',scilimits=(-3,4),axis='y')

    def init(self):
        self.line.set_ydata(self.ydata)
        return self.line,


    def update(self, y):

        self.ydata.popleft()
        self.ydata.append(y)

        #this doesn't work with blit = True.
        #there's a workaround if we need blit = true
        #https://stackoverflow.com/questions/53423868/matplotlib-animation-how-to-dynamically-extend-x-limits
        #need to sporadically call
        #fig.canvas.resize_event()

        delta = 0.1*np.max(self.ydata)
        new_min = np.max([0, np.min(self.ydata) - delta])
        new_max = np.max(self.ydata) + delta
        current_min, current_max = self.ax.get_ylim()
        if (np.abs((new_min - current_min)/(current_min)) > 0.12) or (np.abs((new_max - current_max)/(current_max)) > 0.12):
            self.ax.set_ylim(np.max([0.01, np.min(self.ydata) - delta]), np.max(self.ydata) + delta)
        self.line.set_ydata(self.ydata)
        return self.line,



class MainApplicationView():
    def __init__(self, main_frame):
        frame = Tk.Frame(main_frame)
        frame.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=True)

        self.scope_view = ScopeFigure(args.scope_width)
        self.sidepanel = SidePanel(main_frame)

        self.canvas = FigureCanvasTkAgg(self.scope_view.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=Tk.TOP, fill=Tk.BOTH, expand=True)

        self.canvas.draw()


class SidePanel():
    def __init__(self, root):
        frame = Tk.Frame(root)
        frame.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=True)
        self.startButton = Tk.Button(frame, text="Start ")
        self.startButton.pack(side="top", fill=Tk.BOTH)
        self.stopButton = Tk.Button(frame, text="Stop")
        self.stopButton.pack(side="top", fill=Tk.BOTH)

class MainTkApplication():

    def __init__(self, data_model):
        self.root = Tk.Tk()
        self.model = data_model
        self.view = MainApplicationView(self.root)
        self.view.sidepanel.startButton.bind("<Button>", self.start_scope)
        self.view.sidepanel.stopButton.bind("<Button>", self.stop_scope)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.animation = None

    def run(self):
        self.root.title("QT3Scope: NIDAQ Digital Input Count Rate")
        self.root.deiconify()
        self.root.mainloop()

    def stop_scope(self, event = None):
        self.model.stop()
        if self.animation is not None:
            self.animation.pause()

    def start_scope(self, event = None):
        if self.animation is None:
            self.view.canvas.draw_idle()
            self.animation = animation.FuncAnimation(self.view.scope_view.fig,
                                                     self.view.scope_view.update,
                                                     self.model.yield_count_rate,
                                                     init_func = self.view.scope_view.init,
                                                     interval=args.animation_update_interval,
                                                     blit=False)
        self.model.start()
        self.animation.resume()

    def on_closing(self):
        try:
            self.stop_scope()
            self.model.close()
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            logger.debug(e)
            pass

def build_data_model():
    if args.randomtest:
        data_acquisition_model = datasources.RandomRateCounter()
    else:
        data_acquisition_model = datasources.NiDaqDigitalInputRateCounter(daq_name = args.daq_name,
                                                                          signal_terminal = args.signal_terminal,
                                                                          clock_rate = args.clock_rate,
                                                                          num_data_samples_per_batch = args.num_data_samples_per_batch,
                                                                          clock_terminal = args.clock_terminal,
                                                                          read_write_timeout = args.rwtimeout,
                                                                          signal_counter = args.signal_counter)
    return data_acquisition_model


def main():
    tkapp = MainTkApplication(build_data_model())
    tkapp.run()

if __name__ == '__main__':
    main()
