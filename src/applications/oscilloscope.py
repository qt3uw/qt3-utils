import argparse
import collections
import tkinter as Tk
import logging

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import src.qt3utils.datagenerators as datasources
from src.qt3utils.math_utils import get_rolling_mean

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='NI DAQ (PCIx 6363) digital input terminal count rate meter.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-d', '--daq-name', default='Dev1', type=str, metavar='daq_name',
                    help='NI DAQ Device Name')
parser.add_argument('-st', '--signal-terminal', metavar='terminal', default='PFI0', type=str,
                    help='NI DAQ terminal connected to input digital TTL signal')
parser.add_argument('-w', '--scope-width', metavar='width', default=500, type=int,
                    help='Number of measurements to display in window.')
parser.add_argument('-c', '--clock-rate', metavar='rate (Hz)', default=100000, type=int,
                    help='''Specifies the clock rate in Hz. If using an external clock,
                    you should specifiy the clock rate here so that the correct counts per
                    second are displayed. If using the internal NI DAQ clock (default behavior),
                    this value specifies the clock rate to use. Per the NI DAQ manual,
                    use a suitable clock rate for the device for best performance, which is an integer
                    multiple downsample of the digital sample clock.''')
parser.add_argument('-n', '--num-data-samples-per-batch', metavar='N', default=1500, type=int,
                    help='''Number of data points to acquire per DAQ batch request.
                           Note that only ONE data point is shown in the scope.
                           After each request to the NI DAQ for data, the mean count
                           rate from the batch is computed and displayed. Increasing
                           the "num-data-samples-per-batch" should reduce your noise, but
                           slow the response of the scope. Increase this value if the
                           scope appears too noisy.''')
parser.add_argument('-ct', '--clock-terminal', metavar='terminal', default=None, type=str,
                    help='''Specifies the digital input terminal to the NI DAQ to use for a clock.
                            If None, which is the default, the internal NI DAQ clock is used.''')
parser.add_argument('-to', '--rwtimeout', metavar='seconds', default=10, type=int,
                    help='NI DAQ read/write timeout in seconds.')
parser.add_argument('-sc', '--signal-counter', metavar='ctrN', default='ctr2', type=str,
                    help='NI DAQ interal counter (ctr1, ctr2, ctr3, ctr4)')
parser.add_argument('-r', '--randomtest', action='store_true',
                    help='When true, program will run showing random numbers. This is for development testing.')
parser.add_argument('-aut', '--animation-update-interval', metavar='milliseconds', default=20, type=float,
                    help='''Sets the animation update period, t, (in milliseconds).
                    This is the time delay between calls to acquire new data.
                    You should be limited by the data acquisition time = N / clock_rate.''')
parser.add_argument('-rmw', '--rolling-mean-window', metavar='milliseconds', default=400, type=float,
                    help='''Sets the displayed rolling mean window size, w, (in milliseconds).
                    Actual value will set as the ceil(rmw/aut) * aut.''')
parser.add_argument('-srm', '--show-rolling-mean', default='Υ',
                    help='''Show (Y) or hide (N) the rolling mean line.''')
parser.add_argument('-srt', '--show-reading-text', default='Υ',
                    help='''Show (Y) or hide (N) the reading text. 
                    If rolling mean is enabled, rolling mean, rolling standard
                    deviation (STD) and expected STD (from Poison distribution) 
                    text will also be displayed.''')

parser.add_argument('--console', action='store_true',
                    help='Run as console app -- just the figure without buttons.')
args = parser.parse_args()


class ScopeFigure:

    def __init__(self, width: int = 50, rolling_mean_window_size: int = 20,
                 show_rolling_mean: bool = True, show_reading_text: bool = True,
                 fig: plt.Figure = None, ax: plt.Axes = None):

        # setting up the figure and main axis
        if ax is None:
            fig, ax = plt.subplots()
            self.fig = fig
            self.ax = ax
        else:
            self.fig = fig
            self.ax = ax
        self.fig.set_layout_engine('compressed')

        # display settings
        self.show_rolling_mean = show_rolling_mean
        self.show_reading_text = show_reading_text

        # setting up primary data plot
        self.ydata = collections.deque(np.zeros(width))
        self.line, = self.ax.plot(self.ydata)
        self.line: plt.Line2D

        # Setting up axis preferences
        # TODO: Put all axis preferences to .mplstyle and load through terminal or gui.
        self.ax.set_ylabel('Reading (counts / sec)')
        self.ax.ticklabel_format(style='sci', scilimits=(-3, 4), axis='y')
        self.ax.set_xlabel('Acquisition Number')

        if self.show_rolling_mean:
            self._add_rolling_mean(rolling_mean_window_size)
        if self.show_reading_text:
            self._add_reading_text()

    def _add_rolling_mean(self, rolling_mean_window_size: int):
        self.rolling_mean_window_size = rolling_mean_window_size
        self.half_window_size = int(np.ceil(self.rolling_mean_window_size / 2))
        self.rolling_mean = self.get_rolling_mean()
        self.rolling_mean_line, = self.ax.plot(self.rolling_mean)
        self.rolling_mean_line: plt.Line2D

    def _add_reading_text(self):
        self.text_font_size = 30  # TODO: Add to .mplstyle file
        fig_width = self.fig.get_size_inches()[0]
        fig_height = self.fig.get_size_inches()[1]
        if self.show_rolling_mean:
            self.fig.set_size_inches(fig_width, fig_height * 1.3)
            displayed_values = 'NaN\nNaN\nNaN (NaN)'
            displayed_labels = 'Cur. Val.\nMean\nSTD'
        else:
            self.fig.set_size_inches(fig_width, fig_height * 1.1)
            displayed_values = 'NaN'
            displayed_labels = 'Cur. Val.'
        self.current_value_text: plt.Text = self.ax.text(
            1, 1.05, displayed_values, fontsize=self.text_font_size, transform=self.ax.transAxes, ha='right')
        self.ax.text(
            0, 1.05, displayed_labels, fontsize=self.text_font_size, transform=self.ax.transAxes, ha='left')

    def init(self):
        self.line.set_ydata(self.ydata)
        if self.show_rolling_mean:
            self.rolling_mean_line.set_ydata(self.rolling_mean)
        if self.show_reading_text:
            self.current_value_text.set_text('NaN\nNaN\nNaN (NaN)' if self.show_rolling_mean else 'NaN')
        return self.line,

    def update(self, y):

        self.ydata.popleft()
        self.ydata.append(y)

        # this doesn't work with blit = True.
        # there's a workaround if we need blit = true
        # https://stackoverflow.com/questions/53423868/matplotlib-animation-how-to-dynamically-extend-x-limits
        # need to sporadically call
        # fig.canvas.resize_event()

        delta = 0.1 * np.max(self.ydata)
        new_min = np.max([0, np.min(self.ydata) - delta])
        new_max = np.max(self.ydata) + delta
        current_min, current_max = self.ax.get_ylim()

        if (np.abs((new_min - current_min) / current_min) > 0.12) \
                or (np.abs((new_max - current_max) / current_max) > 0.12):
            self.ax.set_ylim(np.max([0.01, np.min(self.ydata) - delta]), np.max(self.ydata) + delta)

        self.line.set_ydata(self.ydata)

        if self.show_rolling_mean:
            new_rm_value = self.update_rolling_mean()
            self.rolling_mean_line.set_ydata(self.rolling_mean)

        if self.show_reading_text:
            text = self._get_text_value(y)
            if self.show_rolling_mean:
                text = f'{text}\n {self._get_text_value(new_rm_value)}'
                measured_stdev = self.get_new_rolling_stdev_val()
                expected_stdev = np.sqrt(new_rm_value)
                text = f'{text}\n {self._get_text_value(measured_stdev)} ({self._get_text_value(expected_stdev)})'
            self.current_value_text.set_text(text)

        return self.line,

    def get_new_rolling_mean_val(self):
        values_of_interest = list(self.ydata)[len(self.ydata) - 2 * self.half_window_size:
                                              len(self.ydata)]
        return np.mean(values_of_interest)

    def get_new_rolling_stdev_val(self):
        values_of_interest = list(self.ydata)[len(self.ydata) - 2 * self.half_window_size:
                                              len(self.ydata)]
        return np.std(values_of_interest)

    def update_rolling_mean(self):
        rm = collections.deque(self.rolling_mean[self.half_window_size: len(self.ydata) - self.half_window_size])
        rm.popleft()
        new_rm_value = self.get_new_rolling_mean_val()
        rm.append(new_rm_value)
        self.rolling_mean[self.half_window_size: len(self.ydata) - self.half_window_size] = list(rm)
        return new_rm_value

    def get_rolling_mean(self):
        rolling_mean = get_rolling_mean(self.ydata, self.rolling_mean_window_size)
        rolling_mean[:self.half_window_size] = np.nan
        rolling_mean[len(self.ydata) - self.half_window_size:] = np.nan
        return rolling_mean

    @staticmethod
    def _get_text_value(value: float):
        rounded_value = np.around(value, 1)
        return f'{rounded_value:,}'


class MainApplicationView:
    def __init__(self, main_frame):
        frame = Tk.Frame(main_frame)
        frame.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=True)

        rolling_mean_window_size = np.ceil(args.rolling_mean_window / args.animation_update_interval)
        self.scope_view = ScopeFigure(args.scope_width, int(rolling_mean_window_size))
        self.sidepanel = SidePanel(main_frame)

        self.canvas = FigureCanvasTkAgg(self.scope_view.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=Tk.TOP, fill=Tk.BOTH, expand=True)

        self.canvas.draw()


class SidePanel:
    def __init__(self, root):
        frame = Tk.Frame(root)
        frame.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=True)
        self.startButton = Tk.Button(frame, text="Start ")
        self.startButton.pack(side="top", fill=Tk.BOTH)
        self.stopButton = Tk.Button(frame, text="Stop")
        self.stopButton.pack(side="top", fill=Tk.BOTH)


class MainTkApplication:

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

    def stop_scope(self, event=None):
        self.model.stop()
        if self.animation is not None:
            self.animation.pause()

    def start_scope(self, event=None):
        if self.animation is None:
            self.view.canvas.draw_idle()
            self.animation = animation.FuncAnimation(
                self.view.scope_view.fig,
                self.view.scope_view.update,
                self.model.yield_count_rate,
                init_func=self.view.scope_view.init,
                interval=args.animation_update_interval,
                blit=False,
                cache_frame_data=False,
            )
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
        data_acquisition_model = datasources.NiDaqDigitalInputRateCounter(
            daq_name=args.daq_name,
            signal_terminal=args.signal_terminal,
            clock_rate=args.clock_rate,
            num_data_samples_per_batch=args.num_data_samples_per_batch,
            clock_terminal=args.clock_terminal,
            read_write_timeout=args.rwtimeout,
            signal_counter=args.signal_counter
        )
    return data_acquisition_model


def run_console():
    rolling_mean_window_size = np.ceil(args.rolling_mean_window / args.animation_update_interval)
    view = ScopeFigure(args.scope_width, int(rolling_mean_window_size))
    model = build_data_model()
    model.start()
    ani = animation.FuncAnimation(
        view.fig,
        view.update,
        model.yield_count_rate,
        init_func=view.init,
        interval=args.animation_update_interval,
        blit=False,
        cache_frame_data=False,
    )
    plt.show()
    model.close()


def run_gui():
    tkapp = MainTkApplication(build_data_model())
    tkapp.run()


def main():
    if args.console:
        run_console()
    else:
        run_gui()


if __name__ == '__main__':
    main()
