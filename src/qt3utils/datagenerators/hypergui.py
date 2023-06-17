import tkinter as tk
from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib
import numpy as np
from princeton import Spectrometer
import nipiezojenapy

matplotlib.use('TKAgg')

piezo_write_channels = 'ao0,ao1,ao2'
piezo_read_channels = 'ai0,ai1,ai2' 

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
        self.labels = {}
        self.text_fields = {}

        labels_list = ["exposure_time", "sensor_setpoint", "center_wavelength", "z", "xs_start", "xs_end", "ys_start", "ys_end", "num"]
        for label in labels_list:
            self.labels[label] = tk.Label(self)
            self.labels[label]["text"] = label
            self.labels[label].pack(side="top")

            self.text_fields[label] = tk.Entry(self)
            self.text_fields[label].pack(side="top")

        self.run = tk.Button(self)
        self.run["text"] = "Run scan"
        self.run["command"] = self.run_scan
        self.run.pack(side="top")

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.master)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side="top")

    def run_scan(self):
        try:
            s.exposure_time = float(self.text_fields["exposure_time"].get())
            s.num_frames = "1"
            s.sensor_setpoint = float(self.text_fields["sensor_setpoint"].get())
            s.center_wavelength = float(self.text_fields["center_wavelength"].get())
            z = float(self.text_fields["z"].get())
            xs_start = float(self.text_fields["xs_start"].get())
            xs_end = float(self.text_fields["xs_end"].get())
            ys_start = float(self.text_fields["ys_start"].get())
            ys_end = float(self.text_fields["ys_end"].get())
            num = int(self.text_fields["num"].get())
            if num <= 0:
                raise ValueError("num must be a positive integer")
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return

        xs = np.linspace(xs_start, xs_end, num=num)
        ys = np.linspace(ys_start, ys_end, num=num)
        hyperspectral_im = None

        for i, x in enumerate(xs):
            for j, y in enumerate(ys):
                controller.go_to_position(x,y,z)
                spectrum, wavelength = s.acquire_step_and_glue([600.0, 850.0])
                if i==0 and j==0:
                    hyperspectral_im = np.zeros((xs.shape[0], ys.shape[0], spectrum.shape[0]))
                hyperspectral_im[i, j, :] = spectrum

        mean_spectrum = np.mean(hyperspectral_im, axis=2)

        self.fig.clear()

        ax = self.fig.add_subplot(111)
        ax.imshow(mean_spectrum, cmap='Reds', interpolation='nearest')

        self.canvas.draw()

root = tk.Tk()
app = Application(master=root)
app.mainloop()
s.finalize()
