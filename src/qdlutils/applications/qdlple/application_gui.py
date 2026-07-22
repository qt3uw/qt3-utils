import logging

import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

import numpy as np
import tkinter as tk

from qdlutils.hardware.nidaq.counters.nidaqtimedratecounter import NidaqTimedRateCounter

matplotlib.use('Agg')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MainApplicationView():
    '''
    Main application GUI view, loads SidePanel and ScanImage
    '''
    def __init__(self, main_frame, scan_range=[0, 2]) -> None:
        frame = tk.Frame(main_frame.root)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.control_panel = ControlPanel(main_frame, scan_range)

class ControlPanel():
    '''
    This class handles the GUI for scan parameter configuration.
    '''

    def __init__(self, root, scan_range) -> None:

        # Define frame for the side panel
        # This encompasses the entire side pannel
        base_frame = tk.Frame(root.root)
        base_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Define command frame for start/stop/save buttons
        command_frame = tk.Frame(base_frame)
        command_frame.pack(side=tk.TOP, padx=20, pady=10)
        # Add buttons and text
        row = 0
        tk.Label(command_frame, text="PLE scan control", font='Helvetica 14').grid(row=row, column=0, pady=[0,10], columnspan=2)
        row += 1
        self.start_button = tk.Button(command_frame, text="Start Scan", width=12)
        self.start_button.grid(row=row, column=0, columnspan=1, padx=3)
        self.stop_button = tk.Button(command_frame, text="Stop Scan", width=12)
        self.stop_button.grid(row=row, column=1, columnspan=1, padx=3)

        # Define settings frame to set all scan settings
        settings_frame = tk.Frame(base_frame)
        settings_frame.pack(side=tk.TOP, padx=20, pady=10)
        # Min voltage
        row += 1
        tk.Label(settings_frame, text="Min voltage (V)").grid(row=row, column=0)
        self.voltage_start_entry = tk.Entry(settings_frame, width=10)
        self.voltage_start_entry.insert(10, scan_range[0])
        self.voltage_start_entry.grid(row=row, column=1)
        # Max voltage
        row += 1
        tk.Label(settings_frame, text="Max voltage (V)").grid(row=row, column=0)
        self.voltage_end_entry = tk.Entry(settings_frame, width=10)
        self.voltage_end_entry.insert(10, scan_range[1])
        self.voltage_end_entry.grid(row=row, column=1)
        # Number of pixels on upsweep
        row += 1
        tk.Label(settings_frame, text="# of pixels up").grid(row=row, column=0)
        self.num_pixels_up_entry = tk.Entry(settings_frame, width=10)
        self.num_pixels_up_entry.insert(10, 150)
        self.num_pixels_up_entry.grid(row=row, column=1)
        # Number of pixels on downsweep
        row += 1
        tk.Label(settings_frame, text="# of pixels down").grid(row=row, column=0)
        self.num_pixels_down_entry = tk.Entry(settings_frame, width=10)
        self.num_pixels_down_entry.insert(10, 10)
        self.num_pixels_down_entry.grid(row=row, column=1)
        # Number of scans
        row += 1
        tk.Label(settings_frame, text="# of scans").grid(row=row, column=0)
        self.scan_num_entry = tk.Entry(settings_frame, width=10)
        self.scan_num_entry.insert(10, 10)
        self.scan_num_entry.grid(row=row, column=1, padx=10)
        # Time for the upsweep min -> max
        row += 1
        tk.Label(settings_frame, text="Upsweep time (s)").grid(row=row, column=0)
        self.upsweep_time_entry = tk.Entry(settings_frame, width=10)
        self.upsweep_time_entry.insert(10, 3)
        self.upsweep_time_entry.grid(row=row, column=1)
        # Time for the downsweep max -> min
        row += 1
        tk.Label(settings_frame, text="Downsweep time (s)").grid(row=row, column=0)
        self.downsweep_time_entry = tk.Entry(settings_frame, width=10)
        self.downsweep_time_entry.insert(10, 1)
        self.downsweep_time_entry.grid(row=row, column=1, padx=10)
        # Adding advanced settings
        row += 1
        tk.Label(settings_frame, text="Advanced settings:", font='Helvetica 10').grid(row=row, column=0, pady=[8,0], columnspan=3)
        # Number of subpixels to sample (each pixel has this number of samples)
        # Note that excessively large values will slow the scan speed down due to
        # the voltage movement overhead.
        row += 1
        tk.Label(settings_frame, text="# of sub-pixels").grid(row=row, column=0)
        self.subpixel_entry = tk.Entry(settings_frame, width=10)
        self.subpixel_entry.insert(10, 4)
        self.subpixel_entry.grid(row=row, column=1)
        # Button to enable repump at start of scan?
        row += 1
        tk.Label(settings_frame, text="Reump time (ms)").grid(row=row, column=0)
        self.repump_entry = tk.Entry(settings_frame, width=10)
        self.repump_entry.insert(10, 0)
        self.repump_entry.grid(row=row, column=1)


        # Define control frame to modify DAQ settings
        control_frame = tk.Frame(base_frame)
        control_frame.pack(side=tk.TOP, padx=20, pady=10)
        # Label
        row += 1
        tk.Label(control_frame, text="DAQ control", font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Setter for the voltage
        row += 1
        self.goto_button = tk.Button(control_frame, text="Set voltage (V)", width=12)
        self.goto_button.grid(row=row, column=0)
        self.voltage_entry = tk.Entry(control_frame, width=10)
        self.voltage_entry.insert(10, 0)
        self.voltage_entry.grid(row=row, column=1, padx=10)
        # Getter for the voltage (based off of the latest set value)
        row += 1
        self.get_button = tk.Button(control_frame, text="Get voltage (V)", width=12)
        self.get_button.grid(row=row, column=0)
        self.voltage_show = tk.Entry(control_frame, width=10)
        self.voltage_show.insert(10, 0)
        self.voltage_show.grid(row=row, column=1)
        self.voltage_show.config(state='readonly') # Disable the voltage show
        # Getter for the voltage (based off of the latest set value)
        row += 1
        self.repump_laser_on = tk.IntVar()
        self.repump_laser_toggle_label = tk.Label(control_frame, text='Toggle repump laser')
        self.repump_laser_toggle_label.grid(row=row, column=0, pady=[5,0])
        self.repump_laser_toggle = tk.Checkbutton ( control_frame, var=self.repump_laser_on)
        self.repump_laser_toggle.grid(row=row, column=1, pady=[5,0])

        # Define config frame to set the config file
        config_frame = tk.Frame(base_frame)
        config_frame.pack(side=tk.TOP, padx=20, pady=10)
        tk.Label(config_frame, text="Hardware Configuration", font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=1)
        # Dialouge button to pick the YAML config
        row += 1
        self.hardware_config_from_yaml_button = tk.Button(config_frame, text="Load YAML Config")
        self.hardware_config_from_yaml_button.grid(row=row, column=0, columnspan=1)



class ScanPopoutApplicationView():
    '''
    Scan popout application GUI view, loads DataViewport and SidePanel (new)
    '''
    def __init__(self, main_frame, scan_settings: dict) -> None:
        frame = tk.Frame(main_frame)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.data_viewport = DataViewport()
        self.control_panel = DataViewportControlPanel(main_frame, scan_settings=scan_settings)

        self.canvas = FigureCanvasTkAgg(self.data_viewport.fig, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        self.canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas.draw()



class DataViewport:
    '''
    This class handles the GUI image of the PLE scan

    Currently it is hard coded for the standard image plot in a PLE scan.

    TODO: Handle internal logic for writing image vs. integrated data to the screen
    '''

    def __init__(self, mplcolormap='Blues') -> None:
        self.fig = plt.figure()
        self.ax = plt.gca()
        self.cbar = None
        self.cmap = mplcolormap
        self.norm_min = None
        self.norm_max = None
        self.cid = self.fig.canvas.mpl_connect('button_press_event', self.onclick)
        self.log_data = False

        self.integrate_scans = False


    def update_figure(self, model) -> None:
        '''
        Updates the ScanImage GUI element
        '''
        for ax in self.fig.axes:
            self.fig.delaxes(ax)
        num_readers = len(model.readers)
        grid = plt.GridSpec(1, num_readers)

        if self.integrate_scans:
            self.update_plot(model, grid)
        else:
            self.update_image(model, grid)

    def update_image(self, model, grid) -> None:
        '''
        Updates image data in the ScanImage GUI element
        '''
        # Quick fix to get it to run
        img_data = np.array([[]])

        # Look for the single DAQ reader and get the image data
        for reader in model.readers:
            if isinstance(model.readers[reader], NidaqTimedRateCounter):
                img_data = np.array([output[reader] for output in model.outputs])

        # Calculate the axis extent
        # Want to assign y axis values 0 -> 1 on the upscan, then 1 -> y_max on
        # the downscan. Because imshow scales all samples uniformly, we need
        # (y_max - 1) / 1 = n_pixels_down / n_pixels_up
        y_max = 1 + model.n_pixels_down / model.n_pixels_up

        # Plot the scan
        ax = self.fig.add_subplot()
        img = ax.imshow(img_data.T,
                        cmap=self.cmap, 
                        extent=[0.5,
                                img_data.shape[0]+0.5,
                                0,
                                y_max],
                        interpolation='none',
                        aspect='auto',
                        origin='lower')
        cbar = self.fig.colorbar(img, ax=ax)

        # Set the xtick labels
        # We set up some logic to make it readable
        n_scans = img_data.shape[0]
        if n_scans < 11:
            # Set the xticks on integer values for 1-10
            ax.set_xticks( np.arange(1,n_scans+1,1) )
        else:
            # Set on every 5 if more than 10 scans long
            ax.set_xticks( np.arange(5,n_scans+1,5) )
        # Set the ytick labels
        y_ticks = ax.get_yticks()
        ax.set_yticks( y_ticks, self.calculate_ytick_labels(y_ticks, model.min, model.max, y_max) ) # Set the yticks to match scan
        # Reset the extent
        ax.set_ylim(0,y_max)
        # Set the labels
        ax.set_xlabel('Scan number', fontsize=14)
        ax.set_ylabel('Voltage (V)', fontsize=14)
        cbar.ax.set_ylabel('Counts/sec', fontsize=14, rotation=270, labelpad=15)
        # Set the grid
        ax.grid(alpha=0.3, axis='y', linewidth=1, color='k')#, dashes=(5,5))

        # Normalize the figure if not already normalized
        if (self.norm_min is not None) and (self.norm_max is not None):
            img.set_norm(plt.Normalize(vmin=self.norm_min, vmax=self.norm_max))

    def calculate_ytick_labels(self, y, y_min, y_max, max_tick):
        '''
        Method to compute the ytick labels
        '''
        return np.round(np.where(y > 1, (y_min-y_max)*(y-max_tick)/(max_tick-1)+y_min, (y_max-y_min)*y+y_min), decimals=3)

    def update_plot(self, model, grid) -> None:
        '''
        Updates 2-d line plots, currently not in use.
        '''

        # Look for the single DAQ reader and get the image data
        for reader in model.readers:
            if isinstance(model.readers[reader], NidaqTimedRateCounter):
                img_data = np.array([output[reader] for output in model.outputs])

        # Calculate the axis extent
        # Want to assign y axis values 0 -> 1 on the upscan, then 1 -> y_max on
        # the downscan. Because imshow scales all samples uniformly, we need
        # (y_max - 1) / 1 = n_pixels_down / n_pixels_up
        y_max = 1 + model.n_pixels_down / model.n_pixels_up
        unitless_voltages = np.linspace(0, y_max, model.n_pixels_down + model.n_pixels_up)

        # Plot the scan
        ax = self.fig.add_subplot()
        ax.plot(unitless_voltages, np.sum(img_data.T, axis=-1)/len(img_data))
        ax.set_ylim(self.norm_min, self.norm_max)
        ax.set_xlabel('Voltage (V)', fontsize=14)
        ax.set_ylabel('Intensity (cts/s)', fontsize=14)
        x_ticks = ax.get_xticks()
        ax.set_xticks( x_ticks, self.calculate_ytick_labels(x_ticks, model.min, model.max, y_max) )
        ax.set_xlim(0,y_max)
        ax.grid(alpha=0.3)
        ax.set_title(f'Integrating {len(img_data)} scans')


    def reset(self) -> None:
        self.ax.cla()

    def set_onclick_callback(self, f) -> None:
        self.onclick_callback = f

    def onclick(self, event) -> None:
        pass

class DataViewportControlPanel():
    '''
    GUI elements to control or modify the viewport and save scans.
    '''
    def __init__(self, root, scan_settings: dict) -> None:

        base_frame = tk.Frame(root)
        base_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Define command frame for active buttons/control settings
        command_frame = tk.Frame(base_frame)
        command_frame.pack(side=tk.TOP, padx=20, pady=10)
        row = 0
        tk.Label(command_frame, text="PLE scan control", font='Helvetica 14').grid(row=row, column=0, pady=[0,10], columnspan=2)
        row += 1
        self.save_scan_button = tk.Button(command_frame, text="Save Scan", width=12)
        self.save_scan_button.grid(row=row, column=0, columnspan=2, padx=0)


        # Define settings frame to view scan settings
        settings_frame = tk.Frame(base_frame)
        settings_frame.pack(side=tk.TOP, padx=20, pady=10)
        row=0
        tk.Label(settings_frame, text="Scan settings", font='Helvetica 14').grid(row=row, column=0, pady=[0,10], columnspan=2)
        # Min voltage
        row += 1
        tk.Label(settings_frame, text="Min voltage (V)").grid(row=row, column=0)
        self.voltage_start_entry = tk.Entry(settings_frame, width=10)
        self.voltage_start_entry.insert(0, scan_settings['min'])
        self.voltage_start_entry.config(state='readonly')
        self.voltage_start_entry.grid(row=row, column=1)
        # Max voltage
        row += 1
        tk.Label(settings_frame, text="Max voltage (V)").grid(row=row, column=0)
        self.voltage_end_entry = tk.Entry(settings_frame, width=10)
        self.voltage_end_entry.insert(0, scan_settings['max'])
        self.voltage_end_entry.config(state='readonly')
        self.voltage_end_entry.grid(row=row, column=1)
        # Number of pixels on upsweep
        row += 1
        tk.Label(settings_frame, text="# of pixels up").grid(row=row, column=0)
        self.num_pixels_up_entry = tk.Entry(settings_frame, width=10)
        self.num_pixels_up_entry.insert(0, scan_settings['n_pixels_up'])
        self.num_pixels_up_entry.config(state='readonly')
        self.num_pixels_up_entry.grid(row=row, column=1)
        # Number of pixels on downsweep
        row += 1
        tk.Label(settings_frame, text="# of pixels down").grid(row=row, column=0)
        self.num_pixels_down_entry = tk.Entry(settings_frame, width=10)
        self.num_pixels_down_entry.insert(0, scan_settings['n_pixels_down'])
        self.num_pixels_down_entry.config(state='readonly')
        self.num_pixels_down_entry.grid(row=row, column=1)
        # Number of scans
        row += 1
        tk.Label(settings_frame, text="# of scans").grid(row=row, column=0)
        self.scan_num_entry = tk.Entry(settings_frame, width=10)
        self.scan_num_entry.insert(0, scan_settings['n_scans'])
        self.scan_num_entry.config(state='readonly')
        self.scan_num_entry.grid(row=row, column=1, padx=10)
        # Time for the upsweep min -> max
        row += 1
        tk.Label(settings_frame, text="Upsweep time (s)").grid(row=row, column=0)
        self.upsweep_time_entry = tk.Entry(settings_frame, width=10)
        self.upsweep_time_entry.insert(0, scan_settings['time_up'])
        self.upsweep_time_entry.config(state='readonly')
        self.upsweep_time_entry.grid(row=row, column=1)
        # Time for the downsweep max -> min
        row += 1
        tk.Label(settings_frame, text="Downsweep time (s)").grid(row=row, column=0)
        self.downsweep_time_entry = tk.Entry(settings_frame, width=10)
        self.downsweep_time_entry.insert(0, scan_settings['time_down'])
        self.downsweep_time_entry.config(state='readonly')
        self.downsweep_time_entry.grid(row=row, column=1, padx=10)
        # Adding advanced settings
        row += 1
        tk.Label(settings_frame, text="Advanced settings:", font='Helvetica 10').grid(row=row, column=0, pady=[8,0], columnspan=3)
        # Number of subpixels to sample (each pixel has this number of samples)
        # Note that excessively large values will slow the scan speed down due to
        # the voltage movement overhead.
        row += 1
        tk.Label(settings_frame, text="# of sub-pixels").grid(row=row, column=0)
        self.subpixel_entry = tk.Entry(settings_frame, width=10)
        self.subpixel_entry.insert(0, scan_settings['n_subpixels'])
        self.subpixel_entry.config(state='readonly')
        self.subpixel_entry.grid(row=row, column=1)
        # Button to enable repump at start of scan?
        row += 1
        tk.Label(settings_frame, text="Reump time (ms)").grid(row=row, column=0)
        self.repump_entry = tk.Entry(settings_frame, width=10)
        self.repump_entry.insert(0, scan_settings['time_repump'])
        self.repump_entry.config(state='readonly')
        self.repump_entry.grid(row=row, column=1)

        # Scan settings view
        image_settings_frame = tk.Frame(base_frame)
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
        self.image_maximum.insert(0, 5000)
        self.image_maximum.grid(row=row, column=1, padx=5, pady=2)
        # Set normalization button
        row += 1
        self.norm_button = tk.Button(image_settings_frame, text='Normalize', width=15)
        self.norm_button.grid(row=row, column=0, columnspan=2, pady=[5,1])
        # Autonormalization button
        row += 1
        self.autonorm_button = tk.Button(image_settings_frame, text='Auto-normalize', width=15)
        self.autonorm_button.grid(row=row, column=0, columnspan=2, pady=[1,1])
        # Image toggle
        row += 1
        self.integrate_scans = tk.IntVar()
        self.integrate_scans_toggle = tk.Checkbutton ( 
            image_settings_frame, var=self.integrate_scans, text='Integrate scans')
        self.integrate_scans_toggle.grid(row=row, column=0, pady=[0,0], columnspan=2)
