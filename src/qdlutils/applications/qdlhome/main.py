import logging
import tkinter as tk

import qdlutils.applications.qdlmove.main as qdlmove
import qdlutils.applications.qdlple.main as qdlple
import qdlutils.applications.qdlscan.main as qdlscan
import qdlutils.applications.qdlscope.main as qdlscope
import qdlutils.applications.qt3mirror.main as qt3mirror
import qdlutils.applications.qt3power.main as qt3power

logger = logging.getLogger(__name__)
logging.basicConfig()

class HomeApplication:
    '''
    This is the base application for qdlhome.

    It serves as basic lanucher for each of the different applications. Note that there
    are no special protections coded into the application to prevent user error due to 
    improper usage (e.g. attempting to set the same DAQ output in two different apps
    simultaneously). This is not programmed in directly since how each app handles the
    hardware is slightly different and was not intended to be shared between multiple
    apps at the same time. Nevertheless, the applications are generally designed not to
    hold onto the hardware unecessarily and so interleaved calls are generally 
    permissible --- and improper calls should generally just throw errors (although it
    might do weird things if you're in the middle of a scan, for example).

    This application is a later addition to the qdlutils package and the individual
    apps were not initially designed to be operated in this way. Thus some bugs are
    inevitable. Please post an issue to the github page if you encounter any unusual
    interactions. 
     
    If you want to add new applications to this launcher, ensure that the structure of
    the relevant application is appropritate (able to run as the root tk.Tk, or as a 
    tk.Toplevel).

    If you wish to include additional controls in this app specifically (such as simple
    DAQ controls to flip optical components or toggle hardware), then you should separate
    this script into the standard main.py/application_controller.py/application_gui.py
    structure of the other applications.
    '''

    def __init__(self):
        # Initialize the root tkinter widget (window housing GUI)
        self.root = tk.Tk()
        # Create the main application GUI
        self.view = HomeApplicationView(main_window=self.root)

        # Bind the buttons in the GUI
        self.view.qdlmove_button.bind('<Button>', self.open_qdlmove)
        self.view.qdlple_button.bind('<Button>', self.open_qdlple)
        self.view.qdlscan_button.bind('<Button>', self.open_qdlscan)
        self.view.qdlscope_button.bind('<Button>', self.open_qdlscope)
        self.view.qt3mirror_button.bind('<Button>', self.open_qt3mirror)
        self.view.qt3power_button.bind('<Button>', self.open_qt3power)

    def run(self) -> None:
        '''
        This function launches the application including the GUI
        '''
        # Set the title of the app window
        self.root.title("qdlhome")
        # Display the window (not in task bar)
        self.root.deiconify()
        # Launch the main loop
        self.root.mainloop()

    def open_qdlmove(self, tkinter_event=None) -> None:
        try:
            logger.info('Launching qdlmove...')
            # Launches the application as a subprocess (the application opens a
            # tk.Toplevel instead of a tk.Tk (root) window). The software also skips
            # some steps that are necessary if running as the root.
            qdlmove.main(is_root_process=False)
        except Exception as e:
            logger.warning(f'{e}')

    def open_qdlple(self, tkinter_event=None) -> None:
        try:
            logger.info('Launching qdlple...')
            qdlple.main(is_root_process=False)
        except Exception as e:
            logger.warning(f'{e}')

    def open_qdlscan(self, tkinter_event=None) -> None:
        try:
            logger.info('Launching qdlscan...')
            qdlscan.main(is_root_process=False)
        except Exception as e:
            logger.warning(f'{e}')

    def open_qdlscope(self, tkinter_event=None) -> None:
        try:
            logger.info('Launching qdlscope...')
            qdlscope.main(is_root_process=False)
        except Exception as e:
            logger.warning(f'{e}')
    
    def open_qt3mirror(self, tkinter_event=None) -> None:
        try:
            logger.info('Launching qt3mirror...')
            #qt3mirror.main(is_root_process=False)
            qt3mirror.main()
        except Exception as e:
            logger.warning(f'{e}')

    def open_qt3power(self, tkinter_event=None) -> None:
        try:
            logger.info('Launching qt3power...')
            #qt3power.main(is_root_process=False)
            qt3power.main()
        except Exception as e:
            logger.warning(f'{e}')


class HomeApplicationView:
    '''
    Main application GUI view
    '''
    def __init__(self, main_window: tk.Tk) -> None:
        main_frame = tk.Frame(main_window)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=40, pady=30)

        # Define frame for scan configuration and control
        app_frame = tk.Frame(main_frame)
        app_frame.pack(side=tk.TOP, padx=0, pady=0)
        # Add buttons and text
        row = 0
        tk.Label(app_frame, 
                 text='Launch apps', 
                 font='Helvetica 14').grid(row=row, column=0, pady=[0,5], columnspan=2)
        # Start buttons
        row += 1
        self.qdlmove_button = tk.Button(app_frame, text='qdlmove', width=20)
        self.qdlmove_button.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1
        self.qdlple_button = tk.Button(app_frame, text='qdlple', width=20)
        self.qdlple_button.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1
        self.qdlscan_button = tk.Button(app_frame, text='qdlscan', width=20) 
        self.qdlscan_button.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1
        self.qdlscope_button = tk.Button(app_frame, text='qdlscope', width=20)
        self.qdlscope_button.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1
        self.qt3mirror_button = tk.Button(app_frame, text='qt3mirror', width=20)
        self.qt3mirror_button.grid(row=row, column=0, columnspan=2, pady=5)
        row += 1
        self.qt3power_button = tk.Button(app_frame, text='qt3power', width=20)
        self.qt3power_button.grid(row=row, column=0, columnspan=2, pady=5)

def main():
    tkapp = HomeApplication()
    tkapp.run()

if __name__ == '__main__':
    main()
