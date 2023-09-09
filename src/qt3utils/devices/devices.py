import abc
import logging
import time
from dataclasses import dataclass
from typing import final, Type, Any

import numpy as np
from pyvisa import ResourceManager
from pyvisa.attributes import Attribute
from pyvisa.resources import MessageBasedResource

import threading

import queue

from src.qt3utils.devices.utils import force_clear_message_based_resource, MessageBasedResourceType, ResourceType, \
    find_available_resources_by_idn, auto_detect_read_termination, find_available_resources_by_visa_attribute
from src.qt3utils.logger import get_configured_logger

# TODO: Must have only one pyvisa resource manager, resources are bound to said manager.

resource_manager = ResourceManager()
logger = get_configured_logger(__name__)  # TODO: lear more about logging applications from pyvisa logging.


def _str_is_float(string: str) -> bool:
    try:
        float(string)
        return True
    except ValueError:
        return False


def _convert_str(string: str) -> int | float | str:
    if string.isdigit():
        return int(string)
    elif _str_is_float(string):
        return float(string)
    else:
        return string


class Device(abc.ABC):
    """
    Interface class for all device implementations.
    """

    DEVICE_PY_ALIAS: str
    """ Device alias for logging purposes."""

    # TODO: add loaded dll, ni daq task etc for mediator?
    #  it can also be an arbitrary class defined by the manufacturer or user?
    # TODO: Figure out which information I want to retain about each device and the acquisition process itself, so that
    #  I can save it in the data. I would prefer using a Dataclass for data saving.

    def __init__(self, mediator: ResourceType | None = None):
        self._lock = threading.Lock()
        self.mediator = mediator
        # TODO: Add a device lock, and use it as a decorator every time you access the hardware.
        #  Each function that calls the hardware needs to wait for the lock to be ready.
        #  This might be inefficient in the case of the time series. For the time-series we only need to do it before
        #  and after thread initialization and completion?

    @abc.abstractmethod
    def connect(self):
        pass

    @abc.abstractmethod
    def disconnect(self):
        pass

    @abc.abstractmethod
    def is_connected(self):
        pass

    @abc.abstractmethod
    def clear(self):
        pass

    # @abc.abstractmethod
    # def send_command(self, command):
    #     pass
    #
    # @abc.abstractmethod
    # def receive_data(self):
    #     pass
    #
    # @abc.abstractmethod
    # def get_device_info(self):
    #     pass
    #
    # @abc.abstractmethod
    # def get_device_name(self):
    #     pass
    #
    # @abc.abstractmethod
    # def get_device_type(self):
    #     pass
    #
    # @abc.abstractmethod
    # def get_device_id(self):
    #     pass

    @final
    def _log(self, message, subject: str = None, level: int = logging.INFO):
        name = getattr(self, 'DEVICE_PY_ALIAS', self.__class__.__name__)
        logger.log(level, message, extra={'title': name, 'subtitle': subject}, exc_info=True)

    def __del__(self):
        self.disconnect()


class AcquisitionMixin(abc.ABC):
    """
    AcquisitionMixin is a mixin that provides the ability to acquire single and time-series data from a device.
    Must be used as a subclass. Must be the first in order of the Device definition,
    e.g., `class MyDevice(AcquisitionMixin, Device): ...`
    """

    @dataclass
    class TimeSeriesData:
        """
        Data class for time-series data accumulation storage.
        """
        start_time: np.ndarray = np.array([], dtype=float)
        end_time: np.ndarray = np.array([], dtype=float)
        values: np.ndarray = np.array([], dtype=object)

        def append(self, data: tuple[float, float, list] | 'AcquisitionMixin.TimeSeriesData'):
            if isinstance(data, tuple):
                st, et, vs = data
                self.start_time = np.append(self.start_time, st)
                self.end_time = np.append(self.end_time, et)
                self.values = np.append(self.values, vs)
            elif isinstance(data, AcquisitionMixin.TimeSeriesData):
                self.start_time = np.append(self.start_time, data.start_time)
                self.end_time = np.append(self.end_time, data.end_time)
                self.values = np.append(self.values, data.values)
            else:
                raise ValueError(f'Invalid data type: {type(data)}')

    def __init__(self):
        self._acquisition_thread: threading.Thread | None = None
        self._acquisition_thread_force_stop: bool = False

        self._acquisition_pipeline = queue.Queue()
        self._data_streaming_thread: threading.Thread | None = None

        self.time_series_data: AcquisitionMixin.TimeSeriesData | None = None

        self._acquisition_sleep_time = 0.1  # seconds
        self._acquisition_slow_sleep_time = 1  # seconds

    @abc.abstractmethod
    def setup_acquisition(
            self,
            acquisition_sleep_time: float = None,
            acquisition_slow_sleep_time: float = None
    ):
        if acquisition_sleep_time is not None:
            self._acquisition_sleep_time = acquisition_sleep_time
        if acquisition_slow_sleep_time is not None:
            self._acquisition_slow_sleep_time = acquisition_slow_sleep_time

    @abc.abstractmethod
    def single_acquisition(self) -> list:
        """ Returns a list of values acquired from the device. """
        pass

    @final
    def timed_single_acquisition(self) -> tuple[float, float, list]:
        """ Returns a list of values acquired from the device. Includes start and end time. """
        acq_start_time = time.time()
        single_acq_values = self.single_acquisition()
        acq_end_time = time.time()

        return acq_start_time, acq_end_time, single_acq_values

    @final
    def time_series_acquisition(
            self,
            start_event: threading.Event,
            stop_event: threading.Event,
            resume_event: threading.Event,
            pipeline_mode: str,
    ):
        self._log_acquisition_thread('Entering.')

        if pipeline_mode == 'at_end':
            self._log_acquisition_thread('Setting data pipeline. '
                                         'Data will be accumulated once acquisition thread exits.')
            time_start_array = np.array([], dtype=float)
            time_end_array = np.array([], dtype=float)
            values_array = np.array([], dtype=object)

            def acquire():
                nonlocal time_start_array, time_end_array, values_array
                acq_start_time, acq_end_time, single_acq_values = self.timed_single_acquisition()

                time_start_array = np.append(time_start_array, acq_start_time)
                time_end_array = np.append(time_end_array, acq_end_time)
                values_array = np.append(values_array, single_acq_values)

                return acq_start_time
        else:
            self._log_acquisition_thread('Setting data pipeline. Data will be accumulated continuously.')

            def acquire():
                acq_start_time, acq_end_time, single_acq_values = self.timed_single_acquisition()
                self._acquisition_pipeline.put((acq_start_time, acq_end_time, single_acq_values))

                return acq_start_time

        while not start_event.is_set():
            self._check_acquisition_pause_request(resume_event)
            if self._acquisition_thread_force_stop:
                self._log_acquisition_thread('Force stopped before starting data accumulation.')
                break
            start_event.wait(self._acquisition_slow_sleep_time)
            # TODO: Define own thread-wait function to take into
            #  account other conditions passed as args (e.g. the force stop flag)

        self._log_acquisition_thread('Starting data accumulation.')

        while not stop_event.is_set():  # TODO: Put this in a method called acquisition loop?
            self._check_acquisition_pause_request(resume_event)
            if self._acquisition_thread_force_stop:
                self._log_acquisition_thread('Force stopped after starting data accumulation.')
                break
            try:
                acquisition_start_time = acquire()
                self._sleep_between_acquisitions(acquisition_start_time)
            except Exception as e:
                self._sleep_between_acquisitions()

        self._log_acquisition_thread('Stopping data accumulation.')

        if pipeline_mode == 'at_end':
            self._acquisition_pipeline.put(
                AcquisitionMixin.TimeSeriesData(time_start_array, time_end_array, values_array))

        self._log_acquisition_thread('Accumulated data inserted in pipeline.')
        self._log_acquisition_thread('Exiting.')

    @final
    def start_time_series_acquisition(
            self,
            start_time: float,  # TODO: Add metadata attribute
            start_event: threading.Event,
            stop_event: threading.Event,
            pause_event: threading.Event,
            pipeline_mode: str = 'at_end',
            daemon_thread: bool = False,
            clear_data: bool = True,
    ):

        # TODO: assert pipeline_mode in ['at_end', 'stream']

        if self._acquisition_thread is not None:
            self._log_acquisition_thread('Already running.', level=logging.ERROR)
            raise RuntimeError('Acquisition thread already running.')  # TODO: change

        if self._data_streaming_thread is not None:
            self._log_acquisition_thread('Data streaming is running.', level=logging.ERROR)
            raise RuntimeError('Data streaming is running.')  # TODO: change

        self._acquisition_thread_force_stop = False
        if clear_data:
            self.time_series_data = AcquisitionMixin.TimeSeriesData()

        self._acquisition_thread = threading.Thread(
            target=self.time_series_acquisition,
            args=(start_event, stop_event, pause_event, pipeline_mode),
            daemon=daemon_thread,
        )

        if pipeline_mode == 'stream':
            self._data_streaming_thread = threading.Thread(target=self.catch_streaming_data, daemon=daemon_thread)

        self._acquisition_thread.start()
        if pipeline_mode == 'stream':
            self._data_streaming_thread.start()

        self._log_acquisition_thread('Starting.')

    @final
    def stop_time_series_acquisition(self, force_stop=False):
        if force_stop:
            self._acquisition_thread_force_stop = True

        self._log_acquisition_thread('Stopping.')
        if self._acquisition_thread is not None:
            self._acquisition_thread.join()
            self._log_acquisition_thread('Stopped.')
            del self._acquisition_thread
            self._acquisition_thread = None
        else:
            self._log_acquisition_thread('Already stopped. Nothing changed.')

        if self._data_streaming_thread is not None:
            self._data_streaming_thread.join()
            self._log_acquisition_thread('Stopped streaming data.')
        else:
            try:
                new_data = self._acquisition_pipeline.get()
                self.time_series_data.append(new_data)
                self._acquisition_pipeline.task_done()
                self._log_acquisition_thread('Retrieved data.')
            except queue.Empty:
                self._log_acquisition_thread('Already stopped streaming data. Nothing changed.')

    @final
    def save_time_series_data(self, file_path: str):
        # TODO: Decide how to save time series to file.
        pass

    def catch_streaming_data(self):
        while self._acquisition_thread is not None or self._acquisition_pipeline.qsize() > 0:
            start_time = time.time()
            try:
                new_data = self._acquisition_pipeline.get()
                self.time_series_data.append(new_data)
                self._acquisition_pipeline.task_done()
            except queue.Empty:
                continue
            self._sleep_between_acquisitions(start_time, slow_sleep=True)

    @final
    def _sleep_between_acquisitions(self, start_time: float = None, slow_sleep: bool = False):
        sleep_time = self._acquisition_sleep_time if not slow_sleep else self._acquisition_slow_sleep_time
        if start_time is not None:
            sleep_time = max([0., sleep_time - (time.time() - start_time)])
        time.sleep(sleep_time)

    @final
    def _check_acquisition_pause_request(self, resume_event: threading.Event):
        was_paused = False
        while not resume_event.is_set() and not self._acquisition_thread_force_stop:
            if not was_paused:
                was_paused = True
                self._log_acquisition_thread('Pausing.')
            resume_event.wait(self._acquisition_slow_sleep_time)
            continue  # cames back to this loop as long as pause remains
        self._log_acquisition_thread('Resuming.')

    @final
    def _log_acquisition_thread(self, message, level: int = logging.INFO):
        name = getattr(self, 'DEVICE_PY_ALIAS', self.__class__.__name__)
        logger.log(level, message, extra={'title': name, 'subtitle': 'Acquisition thread'}, exc_info=True)


class MessageBasedDevice(Device, abc.ABC):

    DEFAULT_WRITE_TERMINATION = r'\r\n'
    DEFAULT_READ_TERMINATION = r'\n'

    DEFAULT_QUERY_DELAY = 10 ** -9  # s, even the smallest delay will help your device-read from crushing on you.
    DEFAULT_POST_COMMUNICATION_DELAY = 10 ** -9  # same communication issue when device is not ready to move forward.

    def __init__(
            self,
            mediator: MessageBasedResourceType,
            post_communication_delay: float = DEFAULT_POST_COMMUNICATION_DELAY):
        super(MessageBasedDevice).__init__(mediator)
        super(Device).__init__(mediator)

        self._post_communication_delay = post_communication_delay

    def connect(self):
        with self._lock:
            self.mediator.open()
        self.clear()

    def disconnect(self):
        self.clear()
        with self._lock:
            self.mediator.before_close()
            self.mediator.close()

    def is_connected(self):
        # Accessing the session property itself will raise an InvalidSession exception if the session is not open.
        with self._lock:
            return self.mediator._session is not None

    def clear(self, force: bool = False):
        with self._lock:
            self.clear()
            time.sleep(self.DEFAULT_POST_COMMUNICATION_DELAY)

        if force:
            self.safe_write('*CLS')
            force_clear_message_based_resource(self.mediator, lock=self._lock)

    def safe_query(self, message: str, delay: float | None = None) -> str:
        with self._lock:
            response = self.mediator.query(message, delay)
            time.sleep(self.DEFAULT_POST_COMMUNICATION_DELAY)
        return response

    def safe_write(self, message: str, termination: str | None = None, encoding: str | None = None):
        with self._lock:
            self.mediator.write(message, termination, encoding)
            time.sleep(self.DEFAULT_POST_COMMUNICATION_DELAY)

    def safe_read(self, termination: str | None = None, encoding: str | None = None) -> str:
        with self._lock:
            response = self.mediator.read(termination, encoding)
            time.sleep(self.DEFAULT_POST_COMMUNICATION_DELAY)
        return response

    @property
    def post_communication_delay(self):
        return self._post_communication_delay

    @post_communication_delay.setter
    def post_communication_delay(self, value: float):
        self._post_communication_delay = value

    @staticmethod
    def parse_response(response: str) -> list[int | float | str] | int | float | str:
        response = response.strip()
        response_list: list[str] = response.split(',')
        response_list = [_convert_str(r.strip()) for r in response_list]

        return response_list if len(response_list) > 1 else response_list[0]

    @staticmethod
    def _set_rm_kwargs_defaults(method):
        def wrapper(cls, **rm_kwargs):
            rm_kwargs.setdefault('write_termination', cls.DEFAULT_WRITE_TERMINATION)
            rm_kwargs.setdefault('read_termination', cls.DEFAULT_READ_TERMINATION)
            rm_kwargs.setdefault('query_delay', cls.DEFAULT_QUERY_DELAY)
            return method(cls, **rm_kwargs)
        return wrapper

    @classmethod
    @_set_rm_kwargs_defaults
    def from_resource_name(
            cls,
            resource_name: str,
            post_communication_delay: float = DEFAULT_POST_COMMUNICATION_DELAY,
            **rm_kwargs,
    ) -> 'MessageBasedDevice':

        resource = resource_manager.open_resource(resource_name, **rm_kwargs)

        if not isinstance(resource, MessageBasedResource):
            # TODO: Change message
            raise ValueError(f'Resource {resource} with resource_name {resource_name} is not a MessageBasedResource.')

        return cls(resource, post_communication_delay)

    @classmethod
    @_set_rm_kwargs_defaults
    def from_visa_attribute(
            cls,
            visa_attribute: Type[Attribute],
            desired_attr_value: str,
            is_partial=False,
            post_communication_delay: float = DEFAULT_POST_COMMUNICATION_DELAY,
            **rm_kwargs,
    ) -> 'MessageBasedDevice':

        resource_list = find_available_resources_by_visa_attribute(
            resource_manager, visa_attribute, desired_attr_value, is_partial, **rm_kwargs)

        if len(resource_list) == 0:
            raise ValueError(f'No resource found with visa_attribute {visa_attribute}.')  # TODO: Change message
        elif len(resource_list) > 1:
            raise ValueError(f'Multiple resources found with visa_attribute {visa_attribute}.')  # TODO: Change message

        resource = resource_list[0]
        if not isinstance(resource, MessageBasedResource):
            # TODO: Change message
            raise ValueError(f'Resource {resource} is not a MessageBasedResource.')

        return cls(resource, post_communication_delay)

    @classmethod
    @_set_rm_kwargs_defaults
    def from_idn(
            cls,
            idn: str,
            is_partial: bool = False,
            post_communication_delay: float = DEFAULT_POST_COMMUNICATION_DELAY,
            **rm_kwargs,
    ) -> 'MessageBasedDevice':

        resource_list = find_available_resources_by_idn(resource_manager, idn, is_partial, **rm_kwargs)

        if len(resource_list) == 0:
            raise ValueError(f'No resource found with idn {idn}.')  # TODO: Change message
        elif len(resource_list) > 1:
            raise ValueError(f'Multiple resources found with idn {idn}.')  # TODO: Change message

        return cls(resource_list[0], post_communication_delay)
