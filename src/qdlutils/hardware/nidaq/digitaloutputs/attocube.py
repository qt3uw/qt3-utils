# This file is a test file to try and get the attocube to work
# connect through serial on COM4 through the SiV computer. Manual on dropbox
# REMEMBER THAT THIS IS OPEN LOOP SO THERE IS NO READ OF THE POSITION
# make sure the attocubes are in the CCOM mode
# axis 3 is z and is not connected to anything

import serial
import time
# settings for serial: 38400 baud, 8 data bits, no parity, 1 stop bit, no flow control. 
ser = serial.Serial(port='COM4', baudrate=38400, timeout = 0.1) # timeout is for readline
ser.write(b'stepd 1 5\r\n') # you need both \r\n to do an accurate command, b is for bytes
lists = []
while True: 
    a= ser.readline().decode('utf-8') # utf decode from bytes into ascii
    print(a)
    lists.append(a)
    if a == '> ':
        break
print(lists)
ser.close()

# write a gui to control the attocube
command1 = b'stepd 1 5\r\n'

# write a function for stepping up and down for each axis with the attocube

# write a function for continous stepping up and down for each axis with the attocube

# on startup, set Voltage to 30V and freq to 1000 Hz. Set mode to stp

