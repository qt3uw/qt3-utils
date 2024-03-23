import tkinter as tk
from tkinter import ttk
import logging

from qt3utils.pulsers.pulseblaster import PulseBlasterHoldAOM

# Set up logging
logging.basicConfig(level=logging.INFO)


class QT3PulseBlasterProgrammer(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title('QT3 Pulse Blaster Programmer')

        # Board Number
        row = 0
        ttk.Label(self, text="PB Board Number", font='Helvetica 16')\
            .grid(row=row, column=0, padx=5, pady=5)
        self.board_number = tk.IntVar(value=1)
        ttk.Entry(self, textvariable=self.board_number).grid(row=0, column=1, padx=5, pady=5)

        # Hold Channel High Button
        row += 1
        ttk.Button(self, text='Hold Channel High', command=self.hold_pb_channel_high)\
            .grid(row=row, column=0, padx=5, pady=5)

        self.hold_channel_number = tk.IntVar(value=0)
        ttk.Entry(self, textvariable=self.hold_channel_number)\
            .grid(row=row, column=1, padx=5, pady=5)

    def hold_pb_channel_high(self):
        # Get the value from the input field
        channel_value = int(self.hold_channel_number.get())
        board_number = int(self.board_number.get())

        logging.info(f"PB board number: {board_number}")
        logging.info(f"hold voltage high on channel: {channel_value}")
        try:
            pb = PulseBlasterHoldAOM(board_number, channel_value)
            pb.program_pulser_state()
            pb.start()
        except Exception as e:
            logging.error(e)


def main():
    app = QT3PulseBlasterProgrammer()
    app.mainloop()


if __name__ == '__main__':
    main()
