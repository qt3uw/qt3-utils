import logging

import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

import tkinter as tk

matplotlib.use('Agg')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LauncherApplicationView:

    '''
    Main application GUI view, loads SidePanel and ScanImage
    '''
    def __init__(self, main_window: tk.Tk) -> None:
        main_frame = tk.Frame(main_window)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=40, pady=30)

        self.control_panel = LauncherControlPanel(main_frame)

class LauncherControlPanel:

    def __init__(self, main_frame: tk.Frame):

        # Define frame for scan configuration and control
        scan_frame = tk.Frame(main_frame)
        scan_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Add buttons and text
        row = 0
        tk.Label(scan_frame, 
                 text='Scan control', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Confocal image section
        row += 1
        tk.Label(scan_frame, 
                 text='Confocal image', 
                 font='Helvetica 12').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Range of scan
        row += 1
        tk.Label(scan_frame, text='Range (μm)').grid(row=row, column=0, padx=5, pady=2)
        self.image_range_entry = tk.Entry(scan_frame, width=10)
        self.image_range_entry.insert(0, 80)
        self.image_range_entry.grid(row=row, column=1, padx=5, pady=2)
        # Number of pixels
        row += 1
        tk.Label(scan_frame, text='Number of pixels').grid(row=row, column=0, padx=5, pady=2)
        self.image_pixels_entry = tk.Entry(scan_frame, width=10)
        self.image_pixels_entry.insert(0, 80)
        self.image_pixels_entry.grid(row=row, column=1, padx=5, pady=2)
        # Scan speed
        row += 1
        tk.Label(scan_frame, text='Time per row (s)').grid(row=row, column=0, padx=5, pady=2)
        self.image_time_entry = tk.Entry(scan_frame, width=10)
        self.image_time_entry.insert(0, 1)
        self.image_time_entry.grid(row=row, column=1, padx=5, pady=2)
        # Start button
        row += 1
        self.image_start_button = tk.Button(scan_frame, text='Start scan', width=20)
        self.image_start_button.grid(row=row, column=0, columnspan=2, pady=5)

        # Single axis scan section
        row += 1
        tk.Label(scan_frame, 
                 text='Position optimization', 
                 font='Helvetica 12').grid(row=row, column=0, pady=[10,5], columnspan=2)
        # Range of scan
        row += 1
        tk.Label(scan_frame, text='Range XY (μm)').grid(row=row, column=0, padx=5, pady=2)
        self.line_range_xy_entry = tk.Entry(scan_frame, width=10)
        self.line_range_xy_entry.insert(0, 3)
        self.line_range_xy_entry.grid(row=row, column=1, padx=5, pady=2)
        # Number of pixels
        row += 1
        tk.Label(scan_frame, text='Range Z (μm)').grid(row=row, column=0, padx=5, pady=2)
        self.line_range_z_entry = tk.Entry(scan_frame, width=10)
        self.line_range_z_entry.insert(0, 20)
        self.line_range_z_entry.grid(row=row, column=1, padx=5, pady=2)
        # Number of pixels
        row += 1
        tk.Label(scan_frame, text='Number of pixels').grid(row=row, column=0, padx=5, pady=2)
        self.line_pixels_entry = tk.Entry(scan_frame, width=10)
        self.line_pixels_entry.insert(0, 50)
        self.line_pixels_entry.grid(row=row, column=1, padx=5, pady=2)
        # Scan speed
        row += 1
        tk.Label(scan_frame, text='Time (s)').grid(row=row, column=0, padx=5, pady=2)
        self.line_time_entry = tk.Entry(scan_frame, width=10)
        self.line_time_entry.insert(0, 1)
        self.line_time_entry.grid(row=row, column=1, padx=5, pady=2)
        # Start buttons
        row += 1
        self.line_start_x_button = tk.Button(scan_frame, text='Optimize X', width=20)
        self.line_start_x_button.grid(row=row, column=0, columnspan=2, pady=[5,1])
        row += 1
        self.line_start_y_button = tk.Button(scan_frame, text='Optimize Y', width=20)
        self.line_start_y_button.grid(row=row, column=0, columnspan=2, pady=1)
        row += 1
        self.line_start_z_button = tk.Button(scan_frame, text='Optimize Z', width=20)
        self.line_start_z_button.grid(row=row, column=0, columnspan=2, pady=[1,5])

        # Define frame for DAQ and control
        daq_frame = tk.Frame(main_frame)
        daq_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Add buttons and text
        row = 0
        tk.Label(daq_frame, 
                 text='DAQ control', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[15,5], columnspan=2)
        # X axis
        row += 1
        self.x_axis_set_button = tk.Button(daq_frame, text='Set X (μm)', width=10)
        self.x_axis_set_button.grid(row=row, column=0, columnspan=1, padx=5, pady=[5,1])
        self.x_axis_set_entry = tk.Entry(daq_frame, width=10)
        self.x_axis_set_entry.insert(0, 0)
        self.x_axis_set_entry.grid(row=row, column=1, padx=5, pady=[5,1])
        # Y axis
        row += 1
        self.y_axis_set_button = tk.Button(daq_frame, text='Set Y (μm)', width=10)
        self.y_axis_set_button.grid(row=row, column=0, columnspan=1, padx=5, pady=1)
        self.y_axis_set_entry = tk.Entry(daq_frame, width=10)
        self.y_axis_set_entry.insert(0, 0)
        self.y_axis_set_entry.grid(row=row, column=1, padx=5, pady=1)
        # Z axis
        row += 1
        self.z_axis_set_button = tk.Button(daq_frame, text='Set Z (μm)', width=10)
        self.z_axis_set_button.grid(row=row, column=0, columnspan=1, padx=5, pady=[1,5])
        self.z_axis_set_entry = tk.Entry(daq_frame, width=10)
        self.z_axis_set_entry.insert(0, 0)
        self.z_axis_set_entry.grid(row=row, column=1, padx=5, pady=1)
        # Get button
        row += 1
        self.get_position_button = tk.Button(daq_frame, text='Get current position', width=20)
        self.get_position_button.grid(row=row, column=0, columnspan=2, pady=[1,5])
        # Get button
        row += 1
        self.open_counter_button = tk.Button(daq_frame, text='Open counter', width=20)
        self.open_counter_button.grid(row=row, column=0, columnspan=2, pady=[5,5])

        ''' I do not think that we need to implement this since most people will not
            change settings dynamically. But, it can be added back in by uncommenting
            this section and defining the proper callback function and binding it
            in main.py

        # Define frame for DAQ and control
        config_frame = tk.Frame(main_frame)
        config_frame.pack(side=tk.TOP, padx=0, pady=0)
        row = 0
        tk.Label(config_frame, text="Hardware Configuration", font='Helvetica 14').grid(row=row, column=0, pady=[15,5], columnspan=1)
        # Dialouge button to pick the YAML config
        row += 1
        self.hardware_config_from_yaml_button = tk.Button(config_frame, text="Load YAML Config")
        self.hardware_config_from_yaml_button.grid(row=row, column=0, columnspan=1, pady=5)
        '''




class LineScanApplicationView:

    def __init__(self, 
                 window: tk.Toplevel, 
                 application,   # LineScanApplication
                 settings_dict: dict):
        
        self.application = application
        self.settings_dict = settings_dict

        self.data_viewport = LineDataViewport(window=window)
        self.control_panel = LineFigureControlPanel(window=window, settings_dict=settings_dict)

        # tkinter right click menu
        self.rclick_menu = tk.Menu(window, tearoff = 0) 

        # Initalize the figure
        self.initialize_figure()

    def initialize_figure(self) -> None:
        # Clear the axis
        self.data_viewport.ax.clear()

        # Get the y_axis limits to draw the position lines
        y_axis_limits = self.data_viewport.ax.get_ylim()
        self.data_viewport.ax.plot([self.application.start_position_axis,]*2, 
                                   y_axis_limits,
                                   color='#bac8ff',
                                   linewidth=1.5)
        
        self.data_viewport.ax.set_xlim(self.application.min_position, self.application.max_position)
        self.data_viewport.ax.set_ylim(y_axis_limits)

        self.data_viewport.ax.set_xlabel(f'{self.application.axis} position (μm)', fontsize=14)
        self.data_viewport.ax.set_ylabel(f'Intensity (cts/s)', fontsize=14)
        self.data_viewport.ax.grid(alpha=0.3)

        self.data_viewport.canvas.draw()

    def update_figure(self) -> None:
        '''
        Update the figure
        '''
        # Clear the axis
        self.data_viewport.ax.clear()

        # Plot the data line
        self.data_viewport.ax.plot(self.application.data_x, 
                                   self.application.data_y,
                                   color='k',
                                   linewidth=1.5)
        
        # Get the y_axis limits to draw the position lines
        y_axis_limits = self.data_viewport.ax.get_ylim()
        self.data_viewport.ax.plot([self.application.start_position_axis,]*2, 
                                   y_axis_limits,
                                   color='#bac8ff',
                                   linewidth=1.5)
        self.data_viewport.ax.plot([self.application.final_position_axis,]*2, 
                                   y_axis_limits,
                                   color='#1864ab',
                                   linewidth=1.5)
        
        self.data_viewport.ax.set_xlim(self.application.min_position, self.application.max_position)
        self.data_viewport.ax.set_ylim(y_axis_limits)

        self.data_viewport.ax.set_xlabel(f'{self.application.axis} position (μm)', fontsize=14)
        self.data_viewport.ax.set_ylabel(f'Intensity (cts/s)', fontsize=14)
        self.data_viewport.ax.grid(alpha=0.3)

        self.data_viewport.canvas.draw()

class LineDataViewport:

    def __init__(self, window):

        # Parent frame for control panel
        frame = tk.Frame(window)
        frame.pack(side=tk.LEFT, padx=0, pady=0)

        self.fig = plt.figure()
        self.ax = plt.gca()
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.draw()

class LineFigureControlPanel:

    def __init__(self, window: tk.Toplevel, settings_dict: dict):

        # Parent frame for control panel
        frame = tk.Frame(window)
        frame.pack(side=tk.TOP, padx=30, pady=20)

        # Frame for saving/modifying data viewport
        command_frame = tk.Frame(frame)
        command_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Add buttons and text
        row = 0
        tk.Label(command_frame, 
                 text='Scan control', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Save button
        row += 1
        self.save_button = tk.Button(command_frame, text='Save scan', width=15)
        self.save_button.grid(row=row, column=0, columnspan=2, pady=[5,1])
        # ===============================================================================
        # Add more buttons or controls here
        # ===============================================================================

        # Scan settings view
        settings_frame = tk.Frame(frame)
        settings_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Single axis scan section
        row = 0
        tk.Label(settings_frame, 
                 text='Scan settings', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[10,5], columnspan=2)
        # Range of scan
        row += 1
        tk.Label(settings_frame, text='Range XY (μm)').grid(row=row, column=0, padx=5, pady=2)
        self.line_range_xy_entry = tk.Entry(settings_frame, width=10)
        self.line_range_xy_entry.insert(10, settings_dict['line_range_xy'])
        self.line_range_xy_entry.grid(row=row, column=1, padx=5, pady=2)
        self.line_range_xy_entry.config(state='readonly')
        # Number of pixels
        row += 1
        tk.Label(settings_frame, text='Range Z (μm)').grid(row=row, column=0, padx=5, pady=2)
        self.line_range_z_entry = tk.Entry(settings_frame, width=10)
        self.line_range_z_entry.insert(10, settings_dict['line_range_z'])
        self.line_range_z_entry.grid(row=row, column=1, padx=5, pady=2)
        self.line_range_z_entry.config(state='readonly')
        # Number of pixels
        row += 1
        tk.Label(settings_frame, text='Number of pixels').grid(row=row, column=0, padx=5, pady=2)
        self.line_pixels_entry = tk.Entry(settings_frame, width=10)
        self.line_pixels_entry.insert(10, settings_dict['line_pixels'])
        self.line_pixels_entry.grid(row=row, column=1, padx=5, pady=2)
        self.line_pixels_entry.config(state='readonly')
        # Scan speed
        row += 1
        tk.Label(settings_frame, text='Time (s)').grid(row=row, column=0, padx=5, pady=2)
        self.line_time_entry = tk.Entry(settings_frame, width=10)
        self.line_time_entry.insert(10, settings_dict['line_time'])
        self.line_time_entry.grid(row=row, column=1, padx=5, pady=2)
        self.line_time_entry.config(state='readonly')




class ImageScanApplicationView:

    def __init__(self, 
                 window: tk.Toplevel, 
                 application,   # LineScanApplication
                 settings_dict: dict):
        
        self.application = application
        self.settings_dict = settings_dict

        self.data_viewport = ImageDataViewport(window=window)
        self.control_panel = ImageFigureControlPanel(window=window, settings_dict=settings_dict)

        # Normalization for the figure
        self.norm_min = None
        self.norm_max = None

        # tkinter right click menu
        self.rclick_menu = tk.Menu(window, tearoff = 0) 

        # Initalize the figure
        self.update_figure()

    def update_figure(self) -> None:
        # Clear the axis
        self.data_viewport.fig.clear()
        # Create a new axis
        self.data_viewport.ax = self.data_viewport.fig.add_subplot(111)

        pixel_width = self.application.range / self.application.n_pixels
        extent = [self.application.min_position_1 - pixel_width/2, 
                  self.application.max_position_1 + pixel_width/2,
                  self.application.min_position_2 - pixel_width/2,
                  self.application.max_position_2 + pixel_width/2]
        
        # Plot the frame
        img = self.data_viewport.ax.imshow(self.application.data_z,
                                           extent = extent,
                                           cmap = self.application.cmap,
                                           origin = 'lower',
                                           aspect = 'equal',
                                           interpolation = 'none')
        self.data_viewport.cbar = self.data_viewport.fig.colorbar(img, ax=self.data_viewport.ax)

        self.data_viewport.ax.set_xlabel(f'{self.application.axis_1} position (μm)', fontsize=14)
        self.data_viewport.ax.set_ylabel(f'{self.application.axis_2} position (μm)', fontsize=14)
        self.data_viewport.cbar.ax.set_ylabel('Intensity (cts/s)', fontsize=14, rotation=270, labelpad=15)
        self.data_viewport.ax.grid(alpha=0.3)

        # Normalize the figure if not already normalized
        if (self.norm_min is not None) and (self.norm_max is not None):
            img.set_norm(plt.Normalize(vmin=self.norm_min, vmax=self.norm_max))

        # Plot the current position marker
        x, y, _ = self.application.application_controller.get_position()
        self.data_viewport.ax.plot(x,y,'o', fillstyle='none', markeredgecolor='#1864ab', markeredgewidth=2)

        self.data_viewport.canvas.draw()


class ImageDataViewport:

    def __init__(self, window):

        # Parent frame for control panel
        frame = tk.Frame(window)
        frame.pack(side=tk.LEFT, padx=0, pady=0)

        self.fig = plt.figure()
        self.ax = plt.gca()
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas.draw()


class ImageFigureControlPanel:

    def __init__(self, window: tk.Toplevel, settings_dict: dict):

        # Parent frame for control panel
        frame = tk.Frame(window)
        frame.pack(side=tk.TOP, padx=30, pady=20)

        # Frame for saving/modifying data viewport
        command_frame = tk.Frame(frame)
        command_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Add buttons and text
        row = 0
        tk.Label(command_frame, 
                 text='Scan control', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Pause button
        row += 1
        self.pause_button = tk.Button(command_frame, text='Pause scan', width=15)
        self.pause_button.grid(row=row, column=0, columnspan=2, pady=[5,1])
        # Continue button
        row += 1
        self.continue_button = tk.Button(command_frame, text='Continue scan', width=15)
        self.continue_button.grid(row=row, column=0, columnspan=2, pady=[5,1])
        # Continue button
        row += 1
        self.save_button = tk.Button(command_frame, text='Save scan', width=15)
        self.save_button.grid(row=row, column=0, columnspan=2, pady=[5,1])

        # ===============================================================================
        # Add more buttons or controls here
        # ===============================================================================

        # Scan settings view
        settings_frame = tk.Frame(frame)
        settings_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Single axis scan section
        row = 0
        tk.Label(settings_frame, 
                 text='Scan settings', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[10,5], columnspan=2)
        row += 1
        tk.Label(settings_frame, text='Range (μm)').grid(row=row, column=0, padx=5, pady=2)
        self.image_range_entry = tk.Entry(settings_frame, width=10)
        self.image_range_entry.insert(0, settings_dict['image_range'])
        self.image_range_entry.grid(row=row, column=1, padx=5, pady=2)
        self.image_range_entry.config(state='readonly')
        # Number of pixels
        row += 1
        tk.Label(settings_frame, text='Number of pixels').grid(row=row, column=0, padx=5, pady=2)
        self.image_pixels_entry = tk.Entry(settings_frame, width=10)
        self.image_pixels_entry.insert(0, settings_dict['image_pixels'])
        self.image_pixels_entry.grid(row=row, column=1, padx=5, pady=2)
        self.image_pixels_entry.config(state='readonly')
        # Scan speed
        row += 1
        tk.Label(settings_frame, text='Time per row (s)').grid(row=row, column=0, padx=5, pady=2)
        self.image_time_entry = tk.Entry(settings_frame, width=10)
        self.image_time_entry.insert(0, settings_dict['image_time'])
        self.image_time_entry.grid(row=row, column=1, padx=5, pady=2)
        self.image_time_entry.config(state='readonly')

        # Scan settings view
        image_settings_frame = tk.Frame(frame)
        image_settings_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Single axis scan section
        row = 0
        tk.Label(image_settings_frame, 
                 text='Image settings', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[10,5], columnspan=2)
        # Minimum
        row += 1
        tk.Label(image_settings_frame, text='Minimum (cts/s)').grid(row=row, column=0, padx=5, pady=2)
        self.image_minimum = tk.Entry(image_settings_frame, width=10)
        self.image_minimum.insert(0, 0)
        self.image_minimum.grid(row=row, column=1, padx=5, pady=2)
        # Maximum
        row += 1
        tk.Label(image_settings_frame, text='Maximum (cts/s)').grid(row=row, column=0, padx=5, pady=2)
        self.image_maximum = tk.Entry(image_settings_frame, width=10)
        self.image_maximum.insert(0, 10000)
        self.image_maximum.grid(row=row, column=1, padx=5, pady=2)
        # Set normalization button
        row += 1
        self.norm_button = tk.Button(image_settings_frame, text='Normalize', width=15)
        self.norm_button.grid(row=row, column=0, columnspan=2, pady=[5,1])
        # Autonormalization button
        row += 1
        self.autonorm_button = tk.Button(image_settings_frame, text='Auto-normalize', width=15)
        self.autonorm_button.grid(row=row, column=0, columnspan=2, pady=[1,1])

        # ===============================================================================
        # Add more buttons or controls here
        # ===============================================================================
