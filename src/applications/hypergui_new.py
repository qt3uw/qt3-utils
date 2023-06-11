import tkinter as tk
from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib
import pickle
from argparse import Namespace
import nipiezojenapy
matplotlib.use('TKAgg')
import numpy as np
from princeton import Spectrometer

piezo_write_channels='ao0,ao1,ao2'
piezo_read_channels='ai0,ai1,ai2' 

controller = nipiezojenapy.PiezoControl(device_name = 'Dev1',
                                  write_channels = piezo_write_channels.split(','),
                                  read_channels = piezo_read_channels.split(','))

s = Spectrometer()
s.initialize()

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()

    def create_widgets(self):
        # create the necessary labels and text fields
        self.labels = {}
        self.text_fields = {}
        for label in ["exposure_time", "num_frames", "sensor_setpoint", "sensor_temperature", "center_wavelength", "grating", "x", "y", "z", "xs_start", "xs_end", "xs_step", "ys_start", "ys_end", "ys_step"]:
            self.labels[label] = tk.Label(self)
            self.labels[label]["text"] = label
            self.labels[label].pack(side="top")

            self.text_fields[label] = tk.Entry(self)
            self.text_fields[label].pack(side="top")

        self.run = tk.Button(self)
        self.run["text"] = "Run scan"
        self.run["command"] = self.run_scan
        self.run.pack(side="top")

        # create a figure to hold the plot
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)  # A tk.DrawingArea.
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side="top")

    def run_scan(self):
        # get the settings from the text fields
        try:
            s.exposure_time = float(self.text_fields["exposure_time"].get())
            s.num_frames = int(self.text_fields["num_frames"].get())
            s.sensor_setpoint = float(self.text_fields["sensor_setpoint"].get())
            s.center_wavelength = float(self.text_fields["center_wavelength"].get())
            s.grating = int(self.text_fields["grating"].get())
            x = float(self.text_fields["x"].get())
            y = float(self.text_fields["y"].get())
            z = float(self.text_fields["z"].get())
            xs_start = float(self.text_fields["xs_start"].get())
            xs_end = float(self.text_fields["xs_end"].get())
            xs_step = float(self.text_fields["xs_step"].get())
            ys_start = float(self.text_fields["ys_start"].get())
            ys_end = float(self.text_fields["ys_end"].get())
            ys_step = float(self.text_fields["ys_step"].get())
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return

        xs = np.linspace(xs_start, xs_end, num=int((xs_end-xs_start)/xs_step)+1)
        ys = np.linspace(ys_start, ys_end, num=int((ys_end-ys_start)/ys_step)+1)
        hyperspectral_im = None

        for i, xi in enumerate(xs):
            for j, yi in enumerate(ys):
                controller.go_to_position(xi, yi, z)
                spectrum, wavelength = s.acquire_step_and_glue([600.0, 850.0])
                if i == 0 and j == 0:
                    hyperspectral_im = np.zeros((xs.shape[0], ys.shape[0], spectrum.shape[0]))
                hyperspectral_im[i, j, :] = spectrum

        mean_spectrum = np.mean(hyperspectral_im, axis=2)

        d = {"wavelength": wavelength, "im": hyperspectral_im}
        with open('Date: __, Mordi_Data.pkl', 'wb') as f:
            pickle.dump(d, f)

        # clear the previous plot if it exists
        self.fig.clear()

        # create a new plot in the figure
        ax = self.fig.add_subplot(111)
        ax.imshow(mean_spectrum, cmap='Reds', interpolation='nearest')

        # update the canvas to show the new plot
        self.canvas.draw()

root = tk.Tk()
app = Application(master=root)
app.mainloop()
s.finalize()
