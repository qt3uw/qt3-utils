import abc
from typing import Union
import numpy as np
import tkinter as Tk


class QT3ScopeDataControllerInterface(abc.ABC):

    def __init__(self, logger):
        self.logger = logger

    @abc.abstractmethod
    def configure(self, config_dict: dict):
        """
        This method is used to configure the data controller.
        """
        pass

    @abc.abstractmethod
    def start(self) -> Union[dict, type(None)]:
        pass

    @abc.abstractmethod
    def stop(self) -> Union[dict, type(None)]:
        pass

    @abc.abstractmethod
    def close(self) -> Union[dict, type(None)]:
        pass

    @abc.abstractmethod
    def yield_count_rate(self) -> np.ndarray:
        """
        This method is used to yield data from the data controller.

        todo: alternatively, this method could be used to return an object
        that yeilds the data. 
        """
        pass

    @abc.abstractmethod
    def configure_view(self, gui_root: Tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the data controller.
        """
        pass

    @abc.abstractmethod
    def print_config(self) -> None:
        """
        This method prints the current configuration of the data controller to standard out.
        """
        pass
