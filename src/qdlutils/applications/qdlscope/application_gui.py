import logging

import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

import tkinter as tk

matplotlib.use('Agg')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ScopeApplicationView:
    '''
    Main application GUI view, loads ScopeControlPanel and ScopeDataViewport which
    show the parameters and buttons for controlling the application, and the data view.
    '''
    def __init__(self, 
                 main_window: tk.Tk, 
                 application # scope application 
                 ) -> None:
        main_frame = tk.Frame(main_window)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)

        self.application = application

        self.y_label = None

        self.data_viewport = ScopeDataViewport(main_frame)
        self.control_panel = ScopeControlPanel(main_frame)

        # Initalize the figure
        self.initialize_figure()

    def initialize_figure(self) -> None:
        '''
        Initializes the data viewport figure to be ready for a sampling.
        '''

        # Clear the axis
        self.data_viewport.ax.clear()

        # Get the y_axis limits to draw the position lines
        y_axis_limits = self.data_viewport.ax.get_ylim()
        
        self.data_viewport.ax.set_xlim(0, self.application.max_samples_to_plot)
        self.data_viewport.ax.set_ylim(y_axis_limits)

        self.data_viewport.ax.set_xlabel(f'Sample index', fontsize=14)
        if self.application.daq_parameters['get_rate']:
            self.y_label = 'Intensity (cts/s)'
        else:
            self.y_label = 'Intensity (cts)'
        self.data_viewport.ax.set_ylabel(self.y_label, fontsize=14)            
        self.data_viewport.ax.grid(alpha=0.3)

        self.data_viewport.canvas.draw()

    def update_figure(self) -> None:
        '''
        Update the figure with the current data
        '''
        # Clear the axis
        self.data_viewport.ax.clear()

        # Plot the data line
        self.data_viewport.ax.plot(self.application.data_y[-self.application.max_samples_to_plot:],
                                   color='k',
                                   linewidth=1.5)
        
        self.data_viewport.ax.set_xlim(0, self.application.max_samples_to_plot)

        self.data_viewport.ax.set_xlabel(f'Sample index', fontsize=14)
        self.data_viewport.ax.set_ylabel(self.y_label, fontsize=14)
        self.data_viewport.ax.grid(alpha=0.3)

        self.data_viewport.canvas.draw()

class ScopeControlPanel:

    def __init__(self, main_frame: tk.Frame):
        '''
        Initializes the control panel for the scope application window.

        Parameters
        ----------
        main_frame : tk.Frame
            The frame of the main window to pack the control pannel into.
        '''

        # Define frame for scan configuration and control
        control_frame = tk.Frame(main_frame)
        control_frame.pack(side=tk.TOP, padx=20, pady=20)
        # Add buttons and text
        row = 0
        tk.Label(control_frame, 
                 text='Sampling parameters', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Scan speed
        row += 1
        tk.Label(control_frame, text='Time per sample (s)').grid(row=row, column=0, padx=5, pady=2)
        self.sample_time_entry = tk.Entry(control_frame, width=10)
        self.sample_time_entry.insert(0, 0.005)
        self.sample_time_entry.grid(row=row, column=1, padx=5, pady=2)
        # Scan speed
        row += 1
        self.raw_counts_toggle = tk.IntVar()
        tk.Label(control_frame, text='Raw counts').grid(row=row, column=0, padx=5, pady=2)
        self.raw_counts_checkbutton = tk.Checkbutton(control_frame, variable=self.raw_counts_toggle,
                                               onvalue=1, offvalue=0)
        self.raw_counts_checkbutton.grid(row=row, column=1, padx=5, pady=2)
        # Start button
        row += 1
        self.start_button = tk.Button(control_frame, text='Start', width=20)
        self.start_button.grid(row=row, column=0, columnspan=2, pady=[5,1])
        # Pause button
        row += 1
        self.pause_button = tk.Button(control_frame, text='Pause', width=20)
        self.pause_button.grid(row=row, column=0, columnspan=2, pady=1)
        # Reset button
        row += 1
        self.reset_button = tk.Button(control_frame, text='Reset', width=20)
        self.reset_button.grid(row=row, column=0, columnspan=2, pady=1)
        # Save button
        row += 1
        self.save_button = tk.Button(control_frame, text='Save', width=20)
        self.save_button.grid(row=row, column=0, columnspan=2, pady=[1,5])

class ScopeDataViewport:

    def __init__(self, main_frame: tk.Frame):
        '''
        Initializes the data viewport for the scope application window.

        Parameters
        ----------
        main_frame : tk.Frame
            The frame of the main window to pack the control pannel into.
        '''
        # Parent frame for control panel
        frame = tk.Frame(main_frame)
        frame.pack(side=tk.LEFT, padx=0, pady=0)

        self.fig = plt.figure()
        self.ax = plt.gca()
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.draw()

        
