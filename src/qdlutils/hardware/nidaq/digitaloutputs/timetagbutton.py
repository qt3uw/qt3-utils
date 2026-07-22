# this file is to control the digital outputs on the SiV computer for the flip mirror and g(2) switch
# line 3 is the spectrometer flip mirror 
# line 2 is the time tagger IDQ (g2)

# Import Module
from tkinter import *
import nidaqmx
# Create Object
root = Tk()
 
# Add Title
root.title('On/Off Switch!')
 
# Add Geometry
root.geometry("500x300")
 
# Keep track of the button state on/off
#global is_on
is_on = True
spec_on = True
 
# Create Label
my_label = Label(root,
    text = "Time tag Switch Is On!",
    fg = "green",
    font = ("Helvetica", 16))
 
my_label.pack(pady = 20)
 
# Define our switch function
def switch():
    global is_on
     
    # Determine is on or off
    if is_on:
        on_button.config(image = off)
        my_label.config(text = "Time tag Switch is Off",
                        fg = "grey")
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan('Dev1/port1/line2')
            task.write(False)
        is_on = False
    else:
        on_button.config(image = on)
        my_label.config(text = "Time tag Switch is On", fg = "green")
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan('Dev1/port1/line2')
            task.write(True)
        is_on = True
 
# Define Our Images
on = PhotoImage(file = "C:/Users/SiV Microscope/Documents/qdl-utils-qdots/src/qdlutils/hardware/nidaq/digitaloutputs/on.png")
off = PhotoImage(file = "C:/Users/SiV Microscope/Documents/qdl-utils-qdots/src/qdlutils/hardware/nidaq/digitaloutputs/off.png")
 
# Create A Button
on_button = Button(root, image = on, bd = 0,
                   command = switch)
on_button.pack(pady = 10)

# spec button
my_label_spec = Label(root,
    text = "Spec mirror Switch Is On!",
    fg = "green",
    font = ("Helvetica", 16))
 
my_label_spec.pack(pady = 20)

# Define our switch function
def specswitch():
    global spec_on
     
    # Determine is on or off
    if spec_on:
        spec_on_button.config(image = off)
        my_label_spec.config(text = "spec Switch is Off",
                        fg = "grey")
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan('Dev1/port1/line3')
            task.write(False)
        spec_on = False
    else:
        spec_on_button.config(image = on)
        my_label_spec.config(text = "spec Switch is On", fg = "green")
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan('Dev1/port1/line3')
            task.write(True)
        spec_on = True

# Create A Button
spec_on_button = Button(root, image = on, bd = 0,
                   command = specswitch)
spec_on_button.pack(pady = 10)

# Execute Tkinter
root.mainloop()