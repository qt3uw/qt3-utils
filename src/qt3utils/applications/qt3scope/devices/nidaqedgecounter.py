from typing import Union
import numpy as np
import tkinter as Tk

import qt3utils.datagenerators.daqsamplers as daqsamplers
from qt3utils.applications.qt3scope.interface import QT3ScopeDataControllerInterface


class QT3ScopeNIDAQEdgeCounterController(QT3ScopeDataControllerInterface):

    def __init__(self):
        pass

    def configure(self, **kw_config):
        """
        This method is used to configure the data controller.
        """
        print("calling configure on the nidaq edge counter data controller")
        self.last_config = kw_config

    def start(self) -> Union[dict, type(None)]:
        pass

    def stop(self) -> Union[dict, type(None)]:
        pass

    def close(self) -> Union[dict, type(None)]:
        pass

    def yield_count_rate(self) -> np.ndarray:
        """
        This method is used to yield data from the data controller.
        """
        pass

    def configure_view(self, gui_root: Tk.Toplevel) -> None:
        """
        This method launches a GUI window to configure the data controller.
        """
        print('nidaq edge counter configure view')

    def print_config(self) -> None:
        print(self.last_config)

    def configure_from_yaml(self) -> None:
        """
        This method launches a GUI window to allow the user to select a yaml file to configure the data controller.
        """
        pass
