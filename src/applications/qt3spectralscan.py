import sys
import os

import pickle
import threading

import argparse
import tkinter as tk
from tkinter import messagebox
import tkinter.filedialog as filedialog

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib

import numpy as np
import nipiezojenapy

# Add the path to the qt3utils folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'qt3utils', 'datagenerators')))

from princeton import Spectrometer

matplotlib.use('TKAgg')

parser = argparse.ArgumentParser(description="A tool for controlling piezo channels.")
parser.add_argument('--piezo-write-channels', metavar='<ch0,ch1,ch2>', default='ao0,ao1,ao2', type=str,
                    help='List of analog output channels used to control the piezo position')
parser.add_argument('--piezo-read-channels', metavar='<ch0,ch1,ch2>', default='ai0,ai1,ai2', type=str,
                    help='List of analog input channels used to read the piezo position')
args = parser.parse_args()
write_channels = args.piezo_write_channels.split(',')
read_channels = args.piezo_read_channels.split(',')

# constants
MIN_WAVELENGTH_DIFFERENCE = 117

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.grid()
        self.create_widgets()
        self.colors = ['Reds', 'Blues', 'Greens', 'Greys', 'Purples']
        self.color_var = tk.StringVar(self)
        self.color_var.set('Reds')  
    

    def create_widgets(self):
        '''
        Creates all the necessary widgets for the tkinter GUI such as the
        frame, labels, entry fields, a button, and a matplotlib
        figure for displaying the data.
        '''

        self.text_fields = {}
        text_frame = tk.Frame(self)
        text_frame.grid(column=1, row=0, padx=20)  

        row=0
        bold_font = ('Helvetica', 16, 'bold')
        tk.Label(text_frame, text = "Spectrometer Scan Settings", font=bold_font).grid(row=row, column=1, pady=10)

        row+=1
        tk.Label(text_frame, text="Exposure Time (ms)").grid(row=row, column=0, pady=5)
        self.text_fields["Exposure Time (ms)"] = tk.Entry(text_frame, width=10)
        self.text_fields["Exposure Time (ms)"].grid(row=row, column=1, pady=5)
        self.text_fields["Exposure Time (ms)"].insert(0, "2000") 
    
        row += 1
        tk.Label(text_frame, text="Temperature Sensor Setpoint (°C)").grid(row=row, column=0, pady=5)
        self.text_fields["Temperature Sensor Setpoint (°C)"] = tk.Entry(text_frame, width=10)
        self.text_fields["Temperature Sensor Setpoint (°C)"].grid(row=row, column=1, pady=5)
        self.text_fields["Temperature Sensor Setpoint (°C)"].insert(0, "-70")

        row += 1
        tk.Label(text_frame, text="Center Wavelength (nm)").grid(row=row, column=0, pady=5)
        self.text_fields["Center Wavelength (nm)"] = tk.Entry(text_frame, width=10)
        self.text_fields["Center Wavelength (nm)"].grid(row=row, column=1, pady=5)
        self.text_fields["Center Wavelength (nm)"].insert(0, "700")

        row += 1
        tk.Label(text_frame, text="Wavelength Range (nm)").grid(row=row, column=0, pady=5)
        self.text_fields["Wave Start (nm)"] = tk.Entry(text_frame, width=10)
        self.text_fields["Wave Start (nm)"].grid(row=row, column=1, pady=5)
        self.text_fields["Wave Start (nm)"].insert(0, "600")

        self.text_fields["Wave End (nm)"] = tk.Entry(text_frame, width=10)
        self.text_fields["Wave End (nm)"].grid(row=row, column=2, pady=5)
        self.text_fields["Wave End (nm)"].insert(0, "850")

        row += 1
        tk.Label(text_frame, text="X Range (um)").grid(row=row, column=0, pady=5)
        self.text_fields["X Start (um)"] = tk.Entry(text_frame, width=10)
        self.text_fields["X Start (um)"].grid(row=row, column=1, pady=5)
        self.text_fields["X Start (um)"].insert(0, "50")

        self.text_fields["X End (um)"] = tk.Entry(text_frame, width=10)
        self.text_fields["X End (um)"].grid(row=row, column=2, pady=5)
        self.text_fields["X End (um)"].insert(0, "60")

        row += 1
        tk.Label(text_frame, text="Y Range (um)").grid(row=row, column=0, pady=5)
        self.text_fields["Y Start (um)"] = tk.Entry(text_frame, width=10)
        self.text_fields["Y Start (um)"].grid(row=row, column=1, pady=5)
        self.text_fields["Y Start (um)"].insert(0, "45")

        self.text_fields["Y End (um)"] = tk.Entry(text_frame, width=10)
        self.text_fields["Y End (um)"].grid(row=row, column=2, pady=5)
        self.text_fields["Y End (um)"].insert(0, "55")

        row += 1
        tk.Label(text_frame, text="Z (um)").grid(row=row, column=0, pady=5)
        self.text_fields["Z (um)"] = tk.Entry(text_frame, width=10)
        self.text_fields["Z (um)"].grid(row=row, column=1, pady=5)
        self.text_fields["Z (um)"].insert(0, "43")

        row += 1
        tk.Label(text_frame, text="Step Size (um)").grid(row=row, column=0, pady=5)
        self.text_fields["Step Size (um)"] = tk.Entry(text_frame, width=10)
        self.text_fields["Step Size (um)"].grid(row=row, column=1, pady=5)
        self.text_fields["Step Size (um)"].insert(0, "5")

        row += 1
        tk.Label(text_frame, text="Select scan color").grid(row=row, column=0, pady=5)
        self.color_var = tk.StringVar()  # Stores the selected color map
        self.color_var.set('Reds')  # Default color displayed in GUI
        color_map_choices = ['Reds', 'Blues', 'Greens', 'Greys', 'Purples', 'Oranges']  # Available choices for color maps
        self.color_map = tk.OptionMenu(text_frame, self.color_var, *color_map_choices, command=self.update_color)
        self.color_map.grid(row=row, column=1, pady=5)

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(column=0, row=0)  # Places the scan canvas to the left of text fields

        row += 1
        self.run = tk.Button(text_frame)
        self.run["text"] = "Start Scan"
        self.run["command"] = self.run_scan
        self.run["font"] = ("Helvetica", 10, "bold")
        self.run.grid(row=row, column=0, pady=10)

        row += 1
        bold_font = ('Helvetica', 16, 'bold')
        tk.Label(text_frame, text = "Save Options", font=bold_font).grid(row=row, column=1, pady=10)
        
        row += 1
        tk.Label(text_frame, text="Enter Data File Name").grid(row=row, column=0, pady=5)
        self.text_fields["Save Data"] = tk.Entry(text_frame, width=10)
        self.text_fields["Save Data"].grid(row=row, column=1, pady=5)
        self.save_data_button = tk.Button(text_frame, text="Save Data", command=self.save_data)
        self.save_data_button.grid(row=row, column=2, pady=10)

        row += 1 
        tk.Label(text_frame, text="Enter Image File Name").grid(row=row, column=0, pady=5)
        self.text_fields["Save Image"] = tk.Entry(text_frame, width=10)
        self.text_fields["Save Image"].grid(row=row, column=1, pady=5)
        self.save_button = tk.Button(text_frame, text="Save Image", command=self.save_image)
        self.save_button.grid(row=row, column=2, pady=10)

    def update_color(self, value):
        '''
        Updates the value of the color variable when the user
        selects a different color from the dropdown menu.
        '''

        self.color_var.set(value)
    
    def run_scan(self):
        """
        Called when the user clicks the 'Start Scan' button.
        It disables all input fields to prevent changes during the scan and starts a new thread to run the scan.
        Note: Threading is implemented to help stop the GUI from glitching during the scan and remain responsive.
        """

        # Disable all the text fields and buttons
        for widget in self.text_fields.values():
            widget.config(state='disabled')
        self.run.config(state='disabled')
        self.save_button.config(state='disabled')
        self.save_data_button.config(state='disabled')
        self.color_map.config(state='disabled')

        # Start the thread
        self.scan_thread = threading.Thread(target=self._run_scan_thread)
        self.scan_thread.start()

    def _run_scan_thread(self):
        '''
        This function runs the actual scan. It is called in a separate thread
        to keep the GUI responsive. It collects user inputs, validates them,
        and controls the piezo device and spectrometer to perform the scan.
        Finally, it plots the mean spectrum.
        '''
        
        try:
            
            #Note: The # of frames is hard coded to 1 as people most likely never use anything else
            #Note: Right now the GUI pulls the current grating thats set in the "LF_Control" file in lightfield

            s.num_frames = "1"

            s.exposure_time = float(self.text_fields["Exposure Time (ms)"].get())
            s.temperature_sensor_setpoint = float(self.text_fields["Temperature Sensor Setpoint (°C)"].get())
            s.center_wavelength = float(self.text_fields["Center Wavelength (nm)"].get())

            z = float(self.text_fields["Z (um)"].get())

            xs_start = float(self.text_fields["X Start (um)"].get())
            xs_end = float(self.text_fields["X End (um)"].get())

            ys_start = float(self.text_fields["Y Start (um)"].get())
            ys_end = float(self.text_fields["Y End (um)"].get())
            
            num = int(self.text_fields["Step Size (um)"].get())

            if num <= 0:
                raise ValueError("Step Size must be a positive integer")
            
            wave_start = float(self.text_fields["Wave Start (nm)"].get())
            wave_end = float(self.text_fields["Wave End (nm)"].get())
            
            if wave_end - wave_start < MIN_WAVELENGTH_DIFFERENCE:
                raise ValueError(f"End wavelength must be at least {MIN_WAVELENGTH_DIFFERENCE} units greater than start wavelength.")
            

            xs = np.linspace(xs_start, xs_end, num=num)
            ys = np.linspace(ys_start, ys_end, num=num)
            self.hyperspectral_im = None

            for i, x in enumerate(xs):
                for j, y in enumerate(ys):
                    controller.go_to_position(x,y,z)
                    spectrum, self.wavelength = s.acquire_step_and_glue([wave_start, wave_end])
                    if i==0 and j==0:
                        self.hyperspectral_im = np.zeros((xs.shape[0], ys.shape[0], spectrum.shape[0]))
                    self.hyperspectral_im[i, j, :] = spectrum

            mean_spectrum = np.mean(self.hyperspectral_im, axis=2)

            self.fig.clear()
            ax = self.fig.add_subplot(111)
            ax.imshow(mean_spectrum, cmap=self.color_var.get(), interpolation='nearest')
            self.canvas.draw()
            
        except Exception as e:
            # Error message shown before the specific error is displayed
            messagebox.showerror("Error", "Error: " + str(e))

        finally:
            """
                Re-enable all the text fields and buttons at the end of the function.
                Use the tkinter's `after` method to safely perform UI operations 500ms from the new thread.
                The "after" value is 500ms instead of 0ms as this allows the GUI remember to allow the user 
                to retry their values and fix their error.

            """
            self.master.after(500, self._enable_widgets)
        
    def _enable_widgets(self):
        '''
        This function is called at the end of the scan to re-enable all input fields
        and buttons, allowing the user to perform another scan or save the data.
        '''

        for widget in self.text_fields.values():
            widget.config(state='normal')
        self.run.config(state='normal')
        self.save_button.config(state='normal')
        self.save_data_button.config(state='normal')
        self.color_map.config(state='normal')

    def save_data(self):
        '''
        This function is called when the user clicks the 'Save Data' button.
        It prompts the user for a filename and saves the scan data in pickle format.
        '''

        filename = self.text_fields["Save Data"].get()
        if filename:
            default_file_path = f"{filename}.pkl"  # Default filename, adjust as you see fit
            filetypes = [("Pickle files", "*.pkl")]
            file_path = filedialog.asksaveasfilename(defaultextension=".pkl", initialfile=default_file_path, filetypes=filetypes)
            if file_path: 
                d = {"wavelength": self.wavelength, "im": self.hyperspectral_im}
                with open(file_path, 'wb') as f:
                    pickle.dump(d, f)
                messagebox.showinfo("Info", "Data saved successfully!")
        else:
            messagebox.showerror("Invalid input", "Please fix your file name, do not put a file extension.")

    def save_image(self):
        '''
        This function is called when the user clicks the 'Save Image' button.
        It prompts the user for a filename and saves the plot as an image.
        '''

        filename = self.text_fields["Save Image"].get()
        if filename:
            default_file_path = f"{filename}.png"  # Default filename, adjust as you see fit
            filetypes = [("PNG files", "*.png"), ("JPEG files", "*.jpg")]
            file_path = filedialog.asksaveasfilename(defaultextension=".png", initialfile=default_file_path, filetypes=filetypes)
            if file_path:  
                self.fig.savefig(file_path)
                messagebox.showinfo("Info", "Image saved successfully!")
        else:
            messagebox.showerror("Invalid input", "Please fix your file name, do not put a file extension.")

def main():

    # Initialize spectrometer
    s = Spectrometer()
    s.initialize()

    # Initializing tkinter app
    root = tk.Tk()
    app = Application(master=root)
    app.mainloop()

    #Finalizing the spectrometer
    s.finalize()

if __name__ == "__main__":
    main()
