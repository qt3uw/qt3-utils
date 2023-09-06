import abc
import logging
import time

import numpy as np
from pyvisa.resources import Resource, SerialInstrument, USBInstrument, GPIBInstrument

import threading

import queue


# TODO: Must have only one pyvisa resource manager, resources are bound to said manager.

logger = logging.getLogger(__name__)


class Device(abc.ABC):
    """
    Interface class for all device implementations.
    """
    mediator: Resource | SerialInstrument | USBInstrument | GPIBInstrument
    # TODO: add loaded dll, ni daq task etc?
    #  it can also be an arbitrary class defined by the manufacturer or user?
    # TODO: Figure out which information I want to retain about each device and the acquisition process itself, so that
    #  I can save it in the data. I would prefer using a Dataclass for data saving.

    verbose: int = 1

    def __init__(self, resource_name):
        self._lock = threading.Lock()
        # TODO: Add a device lock, and use it as a decorator every time you access the hardware.
        #  Each function that calls the hardware needs to wait for the lock to be ready.
        #  This would be inefficient in the case of the time series. For the time-series we only need to do it before
        #  and after thread initialization and completion.

    @abc.abstractmethod
    def connect(self):
        pass

    @abc.abstractmethod
    def disconnect(self):
        pass

    @abc.abstractmethod
    def is_connected(self):
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

    @abc.abstractmethod
    def clear(self):
        pass

    # TODO: Find universal way to import different kind of devices with the nice device utils I defined.


class AcquisitionMixin(abc.ABC):
    """
    AcquisitionMixin is a mixin that provides the ability to acquire single and time-series data from a device.
    Must be used as a subclass. Must be the first in order of the Device definition,
    e.g., `class MyDevice(AcquisitionMixin, Device): ...`
    """

    def __init__(self):
        # Time-series acquisition thread-related attributes
        self._acquisition_thread: threading.Thread | None = None
        self._acquisition_thread_force_stop: bool = False
        self._acquisition_pipeline = queue.Queue()
        self.latest_acquired_time_series: dict | None = None
        self._acquisition_sleep_time = 0.1  # seconds
        self._acquisition_pause_waiting_timeout = 1  # seconds

    @abc.abstractmethod
    def setup_acquisition(self, acquisition_sleep_time: float = None):
        if acquisition_sleep_time is not None:
            self._acquisition_sleep_time = acquisition_sleep_time

    @abc.abstractmethod
    def single_acquisition(self) -> list:
        """ Returns a list of values acquired from the device. """
        pass

    def timed_single_acquisition(self) -> tuple[float, float, list]:
        """ Returns a list of values acquired from the device. Includes start and end time. """
        acq_start_time = time.time()
        single_acq_values = self.single_acquisition()
        acq_end_time = time.time()

        return acq_start_time, acq_end_time, single_acq_values

    def time_series_acquisition(
            self, start_time: float,
            start_event: threading.Event,
            stop_event: threading.Event,
            resume_event: threading.Event,
    ):
        logging.info(f'Entering acquisition thread.')  # TODO: add object or thread id

        time_start_array = np.array([], dtype=float)
        time_end_array = np.array([], dtype=float)
        values_array = np.array([], dtype=object)  # TODO: type to float? maybe define on self.acquisition_value_type?

        while not start_event.is_set():
            self._check_acquisition_pause_request(resume_event)
            if self._acquisition_thread_force_stop:
                logging.info(f'Acquisition thread was force stopped before starting data accumulation.')
                # TODO: add object or thread id
                break
            self._sleep_between_acquisitions()

        logging.info(f'Acquisition thread starting data accumulation.')  # TODO: add object or thread id

        while not stop_event.is_set():  # TODO: Put this in a method called acquisition loop?
            self._check_acquisition_pause_request(resume_event)
            if self._acquisition_thread_force_stop:
                logging.info(f'Acquisition thread was force stopped after starting data accumulation.')
                # TODO: add object or thread id
                break

            try:
                acq_start_time, acq_end_time, single_acq_values = self.timed_single_acquisition()

                values_array = np.append(values_array, single_acq_values)
                time_start_array = np.append(time_start_array, acq_start_time)
                time_end_array = np.append(time_end_array, acq_end_time)

                self._sleep_between_acquisitions(acq_start_time)
            except Exception as e:
                self._sleep_between_acquisitions()

        stop_time = time.time()

        logging.info(f'Acquisition thread stopped data accumulation.')  # TODO: add object or thread id

        # TODO: convert to xarray and add metadata? Maybe handle outside of this method?
        self._acquisition_pipeline.put({'time_start': time_start_array, 'time_end': time_end_array,
                                       'values': values_array, 'start_time': start_time, 'stop_time': stop_time})

        logging.info(f'Acquisition thread put accumulated data in pipeline.')  # TODO: add object or thread id
        logging.info(f'Exiting acquisition thread.')  # TODO: add object or thread id

    # TODO: add acquisition to handle just the return of a value, instead of storing values over time (like
    #  when using a wavemeter to measure the wavelength for to stabilize a laser.

    def start_time_series_acquisition(self, start_time: float, start_event: threading.Event,
                                      stop_event: threading.Event, pause_event: threading.Event,
                                      daemon_thread: bool = False):

        if self._acquisition_thread is not None:
            message = f'Acquisition thread already running.'  # TODO: add object or thread id
            logging.exception(message)
            raise RuntimeError(message)

        self._acquisition_thread_force_stop = False

        self._acquisition_thread = threading.Thread(
            target=self.time_series_acquisition,
            args=(start_time, start_event, stop_event, pause_event),
            daemon=daemon_thread,
        )

        self._acquisition_thread.start()
        logging.info('Starting acquisition thread.')

    def stop_time_series_acquisition(self, force_stop=False):
        if force_stop:
            self._acquisition_thread_force_stop = True

        logging.info('Stopping acquisition thread.')
        if self._acquisition_thread is not None:
            self._acquisition_thread.join()
            logging.info('Stopped acquisition thread.')
            self.latest_acquired_time_series = self._acquisition_pipeline.get()
            logging.info('Acquisition thread accumulated data extracted from pipeline.')
            del self._acquisition_thread
            self._acquisition_thread = None
        else:
            logging.info('Acquisition thread was already stopped.')

    def save_latest_time_series(self, file_path: str):
        # TODO: Decide how to save time series to file.
        if self.latest_acquired_time_series is not None:
            pass

    def _sleep_between_acquisitions(self, start_time: float = None):
        if start_time is None:
            sleep_time = self._acquisition_sleep_time
        else:
            sleep_time = max([0., self._acquisition_sleep_time - (time.time() - start_time)])
        time.sleep(sleep_time)

    def _check_acquisition_pause_request(self, resume_event: threading.Event):
        was_paused = False
        while not resume_event.is_set() and not self._acquisition_thread_force_stop:
            if not was_paused:
                was_paused = True
                logging.info('Acquisition thread paused.')
            resume_event.wait(self._acquisition_pause_waiting_timeout)
            continue  # cames back to this loop as long as pause remains
        logging.info('Acquisition thread resumed.')


    # def disconnect(self):
    #     self.stop_time_series_acquisition(force_stop=True)
    #     super().disconnect()  # Refers to Device-inherited class.


# class PowerMeter(Device):
#     pass
#
#
#
# class NewportPowerMeter(PowerMeter):
#
#     IDN_PART = 'NewportCorp,2835-C'
#
#     def __init__(self):
#         pass
#
#     def connect(self):
#
#
























