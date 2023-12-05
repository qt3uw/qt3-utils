from typing import Protocol, runtime_checkable, Generator
import numpy as np
import tkinter as Tk


@runtime_checkable
class QT3ScopeDAQControllerInterface(Protocol):

    def __init__(self, logger_level):
        pass

    def configure(self, config_dict: dict) -> None:
        """
        This method is used to configure the data controller.
        """
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass

    def yield_count_rate(self) -> Generator[np.floating, None, None]:
        """
        This method is used to yield data from the data controller.
        This can either return a generator function or is a generator function itself.
        """
        pass

    def configure_view(self, gui_root: Tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the data controller.
        """
        pass

    def print_config(self) -> None:
        """
        This method prints the current configuration of the data controller to standard out.
        """
        pass
