import abc
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import final, Callable

import numpy as np

from src.qt3utils.logger import get_configured_logger

logger = get_configured_logger(__name__)


def acquisition_sleep(acquisition_interval: float, start_time: float = None):
    """
    Sleep for a given amount of time, accounting for the time it took to acquire data.

    Parameters
    ----------
    acquisition_interval: float
        Time to sleep.
    start_time: float, optional
        Time at which the acquisition started. If None, sleep for full duration.

    Returns
    -------
    None
    """
    if start_time is not None:
        acquisition_interval = max([0., acquisition_interval - (time.time() - start_time)])
    time.sleep(acquisition_interval)


@dataclass
class TimeSeriesData:
    """
    Data class for time-series data accumulation storage.
    """
    start_time: np.ndarray = np.array([], dtype=float)
    end_time: np.ndarray = np.array([], dtype=float)
    values: np.ndarray = np.array([], dtype=object)

    def append(self, data: tuple[float, float, list] | 'TimeSeriesData'):
        if isinstance(data, tuple):
            st, et, vs = data
            self.start_time = np.append(self.start_time, st)
            self.end_time = np.append(self.end_time, et)
            self.values = np.append(self.values, vs)
        elif isinstance(data, TimeSeriesData):
            self.start_time = np.concatenate(self.start_time, data.start_time)
            self.end_time = np.concatenate(self.end_time, data.end_time)
            self.values = np.concatenate(self.values, data.values)
        else:
            raise ValueError(f'Invalid data type: {type(data)}')


class AcquisitionThread(threading.Thread):
    """
    A threaded data acquisition class for time-series data.

    This class provides functionality for collecting data
    from a device using a specified acquisition method.
    Data can be collected in different pipeline modes,
    {'stream' or 'aggregate'}, and can be paused or stopped
    as needed.
    """

    PIPELINE_MODES = ['stream', 'aggregate']  # TODO: assert

    def __init__(
            self,
            acquisition_interval: float,
            idle_timeout: float,
            acquisition_method: Callable,
            pipeline: queue.Queue,
            start_event: threading.Event,
            stop_event: threading.Event,
            resume_event: threading.Event,
            pipeline_mode: str = 'aggregate',
            collection_data_type: type = list,
            parent_identifier: str = 'Unknown',
    ):
        """
        Parameters
        ----------
        acquisition_interval : float
            The sleep time between data acquisitions (in seconds).
        idle_timeout : float
            The sleep time during waiting periods (in seconds).
        acquisition_method : Callable
            The method used for data acquisition.
        pipeline : queue.Queue
            The data pipeline where acquired data is sent.
        start_event : threading.Event
            An event to trigger the start of data acquisition.
        stop_event : threading.Event
            An event to signal the end of data acquisition.
        resume_event : threading.Event
            An event to handle pause-resume requests of data acquisition.
        pipeline_mode : str, optional
            The mode for data pipeline handling ('aggregate' or 'stream').
            Default is 'aggregate'.
        collection_data_type : type, optional
            The type of data collection container used only in 'aggregate' mode.
            Default is a list.
        parent_identifier : str, optional
            A unique identifier for the parent object (e.g., device name,
            python alias or class name).
        """

        super().__init__()
        # TODO: Define directly through parent?
        self.acquisition_interval = acquisition_interval
        self.idle_timeout = idle_timeout
        self.acquisition_method = acquisition_method
        self.pipeline = pipeline

        self.start_event = start_event
        self.stop_event = stop_event
        self.resume_event = resume_event
        self.pipeline_mode = pipeline_mode

        self.parent_identifier = parent_identifier

        self._force_stop = False
        self._data = collection_data_type() if self.pipeline_mode == 'aggregate' else None

        if pipeline_mode == 'stream':
            self._data_handling_method: Callable = self.pipeline.put
        else:  # pipeline_mode == 'aggregate' default
            self._data_handling_method: Callable = self._data.append

    def stop(self):
        """ Force-stops the data acquisition thread, ignoring the `stop_event`. """
        self._force_stop = True

    def stop_and_join(self):
        """ Force-stops the data acquisition thread, ignoring the
        `stop_event` and waits for the thread to exit. """
        self.stop()
        self.join()

    def run(self):
        """
        The main method for the data acquisition thread.

        This method runs the data acquisition loop, acquires data,
        and handles pause and exit conditions.
        """
        self._handle_entry()

        while not self._should_stop_acquisition():
            self._acquire()
            self._check_and_handle_pause_request()

        self._handle_exit()

    def _acquire(self):
        """ Acquire data using the specified acquisition and data
        handling methods according to pipeline mode. """
        pre_acquisition_timestamp = time.time()
        try:
            acquired_data = self.acquisition_method()
            self._data_handling_method(acquired_data)
        except Exception as e:
            pass

        acquisition_sleep(self.acquisition_interval, pre_acquisition_timestamp)

    def _should_start_acquisition(self):
        """
        Check if data acquisition should start.

        Returns
        -------
        bool
            True if data acquisition should start, False otherwise.
        """
        return self.start_event.is_set()

    def _should_stop_acquisition(self):
        """
        Check if data acquisition should stop.

        Returns
        -------
        bool
            True if data acquisition should stop, False otherwise.
        """
        return self.stop_event.is_set() or self._force_stop

    def _wait_to_start(self):
        """ Wait for the start event before beginning data acquisition.
        Listens for pause/exit requests as well. """
        while not self._should_start_acquisition() and not self._force_stop:
            self.start_event.wait(self.idle_timeout)
            if not self._should_start_acquisition():
                self._check_and_handle_pause_request()

        if not self._force_stop:
            self._log('Started.')

    def _check_and_handle_pause_request(self):
        """ Checks and handles pause/resume requests.
        Listens for exit requests as well."""
        was_paused = False
        while not self.resume_event.is_set() and not self._force_stop:
            if not was_paused:
                was_paused = True
                self._log('Pausing.')
            self.resume_event.wait(self.idle_timeout)

        if not self._force_stop:
            self._log('Resuming.')

    def _handle_entry(self):
        """ Handle the thread's entry behavior and waits for
        the start event before beginning data acquisition. """
        self._log('Entered.', logging.DEBUG)

        if self.pipeline_mode == 'stream':
            self._log('Data will be continuously streamed to pipeline.')
        else:
            self._log('Data will be put to pipeline at end of acquisition.')

        self._wait_to_start()

    def _handle_exit(self):
        """ Handle the thread's exit behavior and puts
        data to pipeline if in aggregate mode. """
        if self._force_stop:
            self._log('Force stopped.')
        else:
            self._log('Stopped.')

        if self.pipeline_mode == 'aggregate':
            self.pipeline.put(self._data)

        self._log('Exited.', logging.DEBUG)

    @final
    def _log(self, message, level: int = logging.INFO):
        """
        Log messages related to the acquisition thread.

        Parameters
        ----------
        message : str
            The message to log.
        level : int, optional
            The logging level (default is logging.INFO (==10)).
        """
        name = self.parent_identifier
        logger.log(level, message, extra={'title': name, 'subtitle': 'Acquisition thread'}, exc_info=True)


class TimeSeriesAcquisitionThread(AcquisitionThread):
    """
    A thread class that acquires time-series data from
    devices implemented using the `AcquisitionMixin` class.

    This class provides functionality for collecting data
    from a device using a specified acquisition method.
    Data can be collected in different pipeline modes,
    {'stream' or 'aggregate'}, and can be paused or stopped
    as needed.
    """

    def __init__(
            self,
            parent: 'AcquisitionMixin',
            start_event: threading.Event,
            stop_event: threading.Event,
            resume_event: threading.Event,
            pipeline_mode: str = 'aggregate',
    ):
        """
        Parameters
        ----------
        parent: AcquisitionMixin
            The parent object/device of the thread.
        start_event : threading.Event
            An event to trigger the start of data acquisition.
        stop_event : threading.Event
            An event to signal the end of data acquisition.
        resume_event : threading.Event
            An event to handle pause-resume requests of data acquisition.
        pipeline_mode : str, optional
            The mode for data pipeline handling ('aggregate' or 'stream'). Default is 'aggregate'.
        """
        super().__init__(
            ...
        )


class StreamingDataThread(threading.Thread):
    """
    A thread class that streams data from an acquisition
    thread to a device implemented using the `AcquisitionMixin`
    class.
    """

    def __init__(
            self,
            acquisition_thread: AcquisitionThread,
            pipeline: queue.Queue,
            idle_timeout: float,
            parent_identifier: str = 'Unknown'
    ):
        super().__init__()
        self.acquisition_thread = acquisition_thread
        self.pipeline = pipeline
        self.idle_timeout = idle_timeout
        self.parent_identifier = parent_identifier
        self._force_stop = False

    def stop(self):
        self._force_stop = True

    def run(self):
        self._log('Entered thread.', logging.DEBUG)

        while not self._should_stop_reading_stream():
            try:
                data = self.pipeline.get(timeout=self.idle_timeout)
                self.process_streamed_data(data)
                self.pipeline.task_done()
            except queue.Empty:
                self.handle_idle_timeout()

        self._log('Exited thread.', logging.DEBUG)

    def _should_stop_reading_stream(self):
        """
        Check if the thread should stop reading data from the
        pipeline.

        Returns:
            bool: True if the thread should stop reading data,
            False otherwise.
        """
        return self._force_stop or (not self.acquisition_thread.is_alive() and self.pipeline.qsize() == 0)

    def process_streamed_data(self, data):
        """
        Process streamed data.

        This method is called when new data is streamed from the pipeline.

        Parameters:
            data: The streamed data.
        """
        # Add your custom data processing logic here
        pass

    def handle_idle_timeout(self):
        """
        Handle the idle timeout.

        This method is called when no new data is received within the idle timeout.
        You can customize the behavior when the thread is idle.
        """
        pass

    @final
    def _log(self, message, level=logging.INFO):
        """
        Log messages related to the streaming thread.

        Parameters:
            message (str): The message to log.
            level (int, optional): The logging level (default is logging.INFO).
        """
        name = self.parent_identifier
        logger.log(level, message, extra={'title': name, 'subtitle': 'Streaming thread'}, exc_info=True)


class AcquisitionMixin(abc.ABC):
    """
    AcquisitionMixin is a mixin that provides the ability to acquire single and time-series data from a device.
    Must be used as a subclass. Must be the first in order of the Device definition,
    e.g., `class MyDevice(AcquisitionMixin, Device): ...`
    """

    def __init__(self):
        self._acquisition_thread: threading.Thread | None = None
        self._acquisition_thread_force_stop: bool = False

        self._acquisition_pipeline = queue.Queue()
        self._data_streaming_thread: threading.Thread | None = None

        self.time_series_data: AcquisitionMixin.TimeSeriesData | None = None

        self._acquisition_acquisition_interval = 0.1  # seconds
        self._acquisition_idle_timeout = 1  # seconds

    @abc.abstractmethod
    def setup_acquisition(
            self,
            acquisition_acquisition_interval: float = None,
            acquisition_idle_timeout: float = None
    ):
        if acquisition_acquisition_interval is not None:
            self._acquisition_acquisition_interval = acquisition_acquisition_interval
        if acquisition_idle_timeout is not None:
            self._acquisition_idle_timeout = acquisition_idle_timeout

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
    def start_time_series_acquisition(
            self,
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