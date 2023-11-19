from typing import Union, Protocol, runtime_checkable
import numpy as np
import tkinter as Tk


@runtime_checkable
class QT3ScopeDAQControllerInterface(Protocol):

    def __init__(self, logger_level):
        pass

    def configure(self, config_dict: dict):
        """
        This method is used to configure the data controller.
        """
        pass

    def start(self) -> Union[dict, type(None)]:
        pass

    def stop(self) -> Union[dict, type(None)]:
        pass

    def close(self) -> Union[dict, type(None)]:
        pass

    def yield_count_rate(self) -> np.ndarray:
        """
        This method is used to yield data from the data controller.

        todo: alternatively, this method could be used to return an object
        that yeilds the data.
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
