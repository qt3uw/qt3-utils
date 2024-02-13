import time

import numpy as np

from src.qt3utils.devices.acquisition import AcquisitionMixin
from src.qt3utils.devices.devices import Device


# On Mixing classes:
# https://stackoverflow.com/questions/9575409/calling-parent-class-init-with-multiple-inheritance-whats-the-right-way

# On random generators:
# https://realpython.com/numpy-random-number-generator/

class RandomDevice(Device, AcquisitionMixin):

    DEFAULT_GENERATOR_FUNCTION_NAME = 'poison'
    DEFAULT_GENERATOR_FUNCTION_PARAMETERS = {'lam': 3, 'size': None}

    def __init__(self):
        ...  # TODO: define super of classes later
        self._connection = False
        self._random_generator = np.random.default_rng()
        self._generator_function_name = self.DEFAULT_GENERATOR_FUNCTION_NAME
        self._generator_parameters = self.DEFAULT_GENERATOR_FUNCTION_PARAMETERS

    @property
    def generator_function_name(self):
        return self._generator_function_name

    @generator_function_name.setter
    def generator_function_name(self, value: str):
        # if value is not None:
        if callable(getattr(self._random_generator, value, None)):
            self._generator_function_name = value

    @property
    def generator_parameters(self):
        return self._generator_parameters

    @generator_parameters.setter
    def generator_parameters(self, parameters: dict):
        try:
            self.generator_function(**parameters)
            self._generator_parameters = parameters
        finally:
            pass

    @property
    def generator_function(self):
        return getattr(self._random_generator, self._generator_function_name)

    def connect(self):
        self.log('Connecting.')
        with self._lock:
            self._connection = True
            time.sleep(1)
        self.log('Connected.')

    def disconnect(self):
        self.log('Disconnecting.')
        with self._lock:
            self._connection = False
            time.sleep(0.3)
        self.log('Disconnected.')

    def is_connected(self):
        return self._connection

    def clear(self):
        self.log('Clearing.')
        with self._lock:
            time.sleep(0.1)
        self.log('Cleared.')

    def setup_acquisition(
            self, 
            ts_acquisition_interval: float = None, 
            ts_idle_timeout: float = None,
            generator_function_name: str = None,
            generator_function_parameters: dict = None,
    ):
        ...  # TODO: define supers
        self.generator_function_name = generator_function_name
        self.generator_parameters = generator_function_parameters

    def single_acquisition(self) -> list:
        return self.generator_function(**self.generator_parameters)  # TODO: Make sure it is a list.
