import abc
from typing import Union
import numpy as np
import tkinter as Tk

class QT3ScopeDataControllerInterface(abc.ABC):

    def __init__(self):
        pass

    def configure(self, **kw_config):
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

    def configure_from_yaml(self) -> None:
        """
        This method launches a GUI window to allow the user to select a yaml file to configure the data controller.
        """
        pass