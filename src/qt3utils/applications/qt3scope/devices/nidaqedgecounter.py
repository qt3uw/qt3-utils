from typing import Union
import numpy as np
import tkinter as Tk

import qt3utils.datagenerators.daqsamplers as daqsamplers
from qt3utils.applications.qt3scope.interface import QT3ScopeDataControllerInterface


class QT3ScopeNIDAQEdgeCounterController(QT3ScopeDataControllerInterface):

    def __init__(self, logger):
        super().__init__(logger)

    def configure(self, config_dict: dict):
        """
        This method is used to configure the data controller.
        """
        self.logger.debug("calling configure on the nidaq edge counter data controller")
        self.last_config_dict = config_dict

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
        self.logger.info('Not Implemented')

    def print_config(self) -> None:
        print('NIDAQ edge counter config')
        print(self.last_config_dict)  # we dont' use the logger because we want to be sure this is printed to stdout
