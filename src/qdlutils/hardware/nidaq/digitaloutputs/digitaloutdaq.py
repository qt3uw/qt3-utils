# this file is to control the digital outputs on the SiV computer for the flip mirror and g(2) switch
# line 3 is the spectrometer flip mirror 
# line 2 is the time tagger IDQ (g2)
import nidaqmx

with nidaqmx.Task() as task:
                task.do_channels.add_do_chan('Dev1/port1/line2')
                task.write(True)