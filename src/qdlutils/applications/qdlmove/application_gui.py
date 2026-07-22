import tkinter as tk

class PositionControllerApplicationView():
    '''
    Main Application GUI which houses the individual controller GUIs.
    '''

    def __init__(self, main_window: tk.Tk):
        # Get the frame to pack the GUI
        frame = tk.Frame(main_window)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=16, pady=16)

        # ===============================================================================
        # Edit here to add more controllers
        # ===============================================================================
        # 2. ADD APPLICATION CONTROLLER GUIs HERE
        # Edit here to add more movement control
        # This creates a GUI element for the specified axes with the provided names.
        # You must make a controller of the right type and with correct associations
        # in order for the GUI to work properly.
        # self.micros_view = TwoAxisApplicationView(root_frame=frame, 
        #                                           title='Micros', 
        #                                           axis_1_label='X axis', 
        #                                           axis_2_label='Y axis')
        self.piezos_view = ThreeAxisApplicationView(root_frame=frame, 
                                                    title='Piezos', 
                                                    axis_1_label='X axis', 
                                                    axis_2_label='Y axis',
                                                    axis_3_label='Z axis')


        # ===============================================================================
        # No edits below here!
        # ===============================================================================


class TwoAxisApplicationView():
    '''
    Application control for two-axis movement
    '''
    def __init__(self, root_frame: tk.Frame, title: str, axis_1_label: str, axis_2_label: str):
        
        # Frame to house this subwindow
        self.base_frame = tk.Frame(root_frame)
        self.base_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=8)


        row = 0
        tk.Label(self.base_frame, text=title, font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=5)
        
        row += 1
        # Enable/disable the stepper
        self.stepping_active = tk.IntVar()
        self.stepping_laser_toggle = tk.Checkbutton ( self.base_frame, var=self.stepping_active, text='Enable stepping')
        self.stepping_laser_toggle.grid(row=row, column=0, pady=[0,0], columnspan=2)
        tk.Label(self.base_frame, text='Set value', font='Helvetica 10', width=10).grid(row=row, column=2, pady=[0,0], columnspan=1)
        tk.Label(self.base_frame, text='Step', font='Helvetica 10', width=10).grid(row=row, column=3, pady=[0,0], columnspan=1)
        tk.Label(self.base_frame, text='Current', font='Helvetica 10', width=10).grid(row=row, column=4, pady=[0,0], columnspan=1)

        row += 1
        tk.Label(self.base_frame, text=axis_1_label, font='Helvetica 10', width=10).grid(row=row, column=0, pady=[0,0], columnspan=1)
        self.axis_1_set_button = tk.Button(self.base_frame, text='Set position', width=10)
        self.axis_1_set_button.grid(row=row, column=1, columnspan=1, padx=0)
        self.axis_1_set_entry = tk.Entry(self.base_frame, width=10)
        self.axis_1_set_entry.insert(0, 0)
        self.axis_1_set_entry.grid(row=row, column=2)
        self.axis_1_step_entry = tk.Entry(self.base_frame, width=10)
        self.axis_1_step_entry.insert(0, 0)
        self.axis_1_step_entry.grid(row=row, column=3)
        self.axis_1_readout_entry = tk.Entry(self.base_frame, width=10)
        self.axis_1_readout_entry.insert(0, 0)
        self.axis_1_readout_entry.config(state='readonly')
        self.axis_1_readout_entry.grid(row=row, column=4)

        row += 1
        tk.Label(self.base_frame, text=axis_2_label, font='Helvetica 10', width=10).grid(row=row, column=0, pady=[0,0], columnspan=1)
        self.axis_2_set_button = tk.Button(self.base_frame, text='Set position', width=10)
        self.axis_2_set_button.grid(row=row, column=1, columnspan=1, padx=0)
        self.axis_2_set_entry = tk.Entry(self.base_frame, width=10)
        self.axis_2_set_entry.insert(0, 0)
        self.axis_2_set_entry.grid(row=row, column=2)
        self.axis_2_step_entry = tk.Entry(self.base_frame, width=10)
        self.axis_2_step_entry.insert(0, 0)
        self.axis_2_step_entry.grid(row=row, column=3)
        self.axis_2_readout_entry = tk.Entry(self.base_frame, width=10)
        self.axis_2_readout_entry.insert(0, 0)
        self.axis_2_readout_entry.config(state='readonly')
        self.axis_2_readout_entry.grid(row=row, column=4)


class ThreeAxisApplicationView():
    '''
    Application control for two-axis movement
    '''
    def __init__(self, root_frame: tk.Frame, title: str, axis_1_label: str, axis_2_label: str, axis_3_label: str):
        
        # Frame to house this subwindow
        self.base_frame = tk.Frame(root_frame)
        self.base_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=8)


        row = 0
        tk.Label(self.base_frame, text=title, font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=5)
        
        row += 1
        # Enable/disable the stepper
        self.stepping_active = tk.IntVar()
        self.stepping_laser_toggle = tk.Checkbutton ( self.base_frame, var=self.stepping_active, text='Enable stepping')
        self.stepping_laser_toggle.grid(row=row, column=0, pady=[0,0], columnspan=2)
        tk.Label(self.base_frame, text='Set value', font='Helvetica 10', width=10).grid(row=row, column=2, pady=[0,0], columnspan=1)
        tk.Label(self.base_frame, text='Step', font='Helvetica 10', width=10).grid(row=row, column=3, pady=[0,0], columnspan=1)
        tk.Label(self.base_frame, text='Current', font='Helvetica 10', width=10).grid(row=row, column=4, pady=[0,0], columnspan=1)

        row += 1
        tk.Label(self.base_frame, text=axis_1_label, font='Helvetica 10', width=10).grid(row=row, column=0, pady=[0,0], columnspan=1)
        self.axis_1_set_button = tk.Button(self.base_frame, text='Set position', width=10)
        self.axis_1_set_button.grid(row=row, column=1, columnspan=1, padx=0)
        self.axis_1_set_entry = tk.Entry(self.base_frame, width=10)
        self.axis_1_set_entry.insert(0, 0)
        self.axis_1_set_entry.grid(row=row, column=2)
        self.axis_1_step_entry = tk.Entry(self.base_frame, width=10)
        self.axis_1_step_entry.insert(0, 0)
        self.axis_1_step_entry.grid(row=row, column=3)
        self.axis_1_readout_entry = tk.Entry(self.base_frame, width=10)
        self.axis_1_readout_entry.insert(0, 0)
        self.axis_1_readout_entry.config(state='readonly')
        self.axis_1_readout_entry.grid(row=row, column=4)

        row += 1
        tk.Label(self.base_frame, text=axis_2_label, font='Helvetica 10', width=10).grid(row=row, column=0, pady=[0,0], columnspan=1)
        self.axis_2_set_button = tk.Button(self.base_frame, text='Set position', width=10)
        self.axis_2_set_button.grid(row=row, column=1, columnspan=1, padx=0)
        self.axis_2_set_entry = tk.Entry(self.base_frame, width=10)
        self.axis_2_set_entry.insert(0, 0)
        self.axis_2_set_entry.grid(row=row, column=2)
        self.axis_2_step_entry = tk.Entry(self.base_frame, width=10)
        self.axis_2_step_entry.insert(0, 0)
        self.axis_2_step_entry.grid(row=row, column=3)
        self.axis_2_readout_entry = tk.Entry(self.base_frame, width=10)
        self.axis_2_readout_entry.insert(0, 0)
        self.axis_2_readout_entry.config(state='readonly')
        self.axis_2_readout_entry.grid(row=row, column=4)

        row += 1
        tk.Label(self.base_frame, text=axis_3_label, font='Helvetica 10', width=10).grid(row=row, column=0, pady=[0,0], columnspan=1)
        self.axis_3_set_button = tk.Button(self.base_frame, text='Set position', width=10)
        self.axis_3_set_button.grid(row=row, column=1, columnspan=1, padx=0)
        self.axis_3_set_entry = tk.Entry(self.base_frame, width=10)
        self.axis_3_set_entry.insert(0, 0)
        self.axis_3_set_entry.grid(row=row, column=2)
        self.axis_3_step_entry = tk.Entry(self.base_frame, width=10)
        self.axis_3_step_entry.insert(0, 0)
        self.axis_3_step_entry.grid(row=row, column=3)
        self.axis_3_readout_entry = tk.Entry(self.base_frame, width=10)
        self.axis_3_readout_entry.insert(0, 0)
        self.axis_3_readout_entry.config(state='readonly')
        self.axis_3_readout_entry.grid(row=row, column=4)