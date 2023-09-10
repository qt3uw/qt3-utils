import abc
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from functools import singledispatchmethod
from typing import final, Callable, Any, Protocol, Type

from src.qt3utils.logger import get_configured_logger, LoggableMixin

logger = get_configured_logger(__name__)


class Appendable(Protocol):
    """
    Protocol for classes that define an `append` method.
    Used for type-hinting appendable objects (e.g., list).
    """
    def append(self, item):
        pass


def acquisition_sleep(acquisition_interval: float, start_time: float = None):
    """
    Sleep for a given amount of time, accounting
    for the time it took to acquire data.

    Parameters
    ----------
    acquisition_interval: float
        Time to sleep.
    start_time: float, optional
        Time at which the acquisition started.
        If None, sleep for full duration.

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
    This class does not enforce any specific data type,
    only the size of the tuple when passing a single datum.

    The size of a single measurement list is also not enforced.
    This increases the flexibility of the class, but can be
    dangerous when not used correctly.

    MAKE SURE YOU ALWAYS ACCESS THE DATA WITH THE LOCK!
    Not doing so may result in data-related attributes
    of different lengths, which is probably going to
    cause problems in your code.

    SAFEST WAY TO TRANSEFER THE DATA TO ANOTHER VARIABLE:
    Acquire the lock, transfer all data to new variables
    within the same lock acquisition and create deep copies.

    Example
    -------
    >>> import copy
    >>>
    >>> ts1 = TimeSeriesData()
    >>> ts1.append_separately(0.0, 1.0, [1, 2, 3])
    >>> ts1.append((1.0, 2.0, [4, 5, 6]))
    >>> ts2 = TimeSeriesData()
    >>> ts2.append_separately(2.0, 3.0, [7, 8, 9])
    >>> ts1.append(ts2)
    >>>
    >>> with ts1.lock:
    >>>     start_times = copy.deepcopy(ts1.start_times)
    >>>     end_times = copy.deepcopy(ts1.end_times)
    >>>     measurements = copy.deepcopy(ts1.measurements)
    >>> print(start_times)
    [0.0, 1.0, 2.0]
    >>> print(end_times)
    [1.0, 2.0, 3.0]
    >>> print(measurements)
    [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    """
    start_times: list[float] = field(default_factory=list, init=False)
    end_times: list[float] = field(default_factory=list, init=False)
    measurements: list[list[Any]] = field(default_factory=list, init=False)
    lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    @singledispatchmethod
    def append(self, data):
        if not isinstance(data, TimeSeriesData):
            raise ValueError(f"Unsupported data type: {type(data)}")

        with self.lock:
            self.start_times.extend(data.start_times)
            self.end_times.extend(data.end_times)
            self.measurements.extend(data.measurements)

    @append.register(tuple)
    def _append_tuple(self, data: tuple[float, float, list]):
        if len(data) != 3:
            raise ValueError('Data must be a tuple of length 3.')
        self.append_separately(*data)

    def append_separately(self, start_time: float, end_time: float, measurement: list):
        with self.lock:
            self.start_times.append(start_time)
            self.end_times.append(end_time)
            self.measurements.append(measurement)


class AcquisitionThread(threading.Thread, LoggableMixin):
    """
    A threaded data acquisition class for time-series data
    collection.

    This class provides functionality for collecting data
    from a device using a specified acquisition method.
    Data can be collected in different pipeline modes,
    {'stream' or 'aggregate'}, and can be paused or stopped
    as needed.

    The aggregation mode is suited best for data accumulation
    where little to no temporal overhead is critical.
    Alternatively, the stream mode is suited for accumulation
    of data that need to be processed in real-time
    (e.g., displayed on a GUI graph).
    """

    PIPELINE_MODES = ['stream', 'aggregate']  # TODO: assert

    def __init__(
            self,
            acquisition_interval: float,
            idle_timeout: float,
            acquisition_method: Callable[[], Any],
            pipeline: queue.Queue,
            start_event: threading.Event,
            stop_event: threading.Event,
            resume_event: threading.Event,
            pipeline_mode: str = 'aggregate',
            collection_data_type: Type[Appendable] = list,
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

        super(threading.Thread).__init__()
        super(LoggableMixin).__init__(logger, parent_identifier, 'Acquisition Thread')

        if pipeline_mode not in self.PIPELINE_MODES:
            raise ValueError(f'Invalid pipeline mode: {pipeline_mode}')
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
        """ Force-stops the data acquisition thread,
        ignoring the `stop_event`. """
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
        and handles entry, pause, and exit conditions.
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
            self.log('Started data acquisition.')

    def _check_and_handle_pause_request(self):
        """ Checks and handles pause/resume requests.
        Listens for exit requests as well."""
        was_paused = False
        while not self.resume_event.is_set() and not self._force_stop:
            if not was_paused:
                was_paused = True
                self.log('Pausing data acquisition.')
            self.resume_event.wait(self.idle_timeout)

        if not self._force_stop:
            self.log('Resuming data acquisition.')

    def _handle_entry(self):
        """ Handle the thread's entry behavior and waits for
        the start event before beginning data acquisition. """
        self.log('Entered.', logging.DEBUG)

        if self.pipeline_mode == 'stream':
            self.log('Data will be continuously streamed to pipeline.')
        else:
            self.log('Data will be put to pipeline at end of acquisition.')

        self._wait_to_start()

    def _handle_exit(self):
        """ Handle the thread's exit behavior and puts
        data to pipeline if in aggregate mode. """
        if self._force_stop:
            self.log('Force stopped data acquisition.')
        else:
            self.log('Stopped data acquisition.')

        if self.pipeline_mode == 'aggregate':
            self.pipeline.put(self._data)

        self.log('Exited.', logging.DEBUG)

    @final
    def log(self, message, level: int = logging.INFO):
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

    The aggregation mode is suited best for data accumulation
    where little to no temporal overhead is critical.
    Alternatively, the stream mode is suited for accumulation
    of data that need to be processed in real-time
    (e.g., displayed on a GUI graph).
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
            parent.ts_acquisition_interval,
            parent.ts_idle_timeout,
            parent.timed_single_acquisition,
            parent.ts_pipeline,
            start_event,
            stop_event,
            resume_event,
            pipeline_mode,
            TimeSeriesData,
            getattr(parent, 'DEVICE_PY_ALIAS', parent.__class__.__name__),
        )


class StreamingThread(threading.Thread, LoggableMixin):
    """
    A thread class that collects streamed data from an
    AcquisitionThread.
    """

    def __init__(
            self,
            acquisition_thread: AcquisitionThread,
            pipeline: queue.Queue,
            idle_timeout: float,
            data_collection_object: Appendable,
            data_collection_object_lock: threading.RLock,
            parent_identifier: str = 'Unknown',
    ):
        """
        Parameters
        ----------
        acquisition_thread : AcquisitionThread
            The acquisition thread to collect data from.
        pipeline : queue.Queue
            The pipeline to put data into.
        idle_timeout : float
            The timeout for the thread when it is idle.
        data_collection_object : Appendable
            The object to append data to.
        data_collection_object_lock : threading.RLock, optional
            A thread-safe reentrant lock for the data
            collection object.
        parent_identifier : str, optional
            The identifier of the parent object.
            Default is 'Unknown'.
        """
        super(threading.Thread).__init__()
        super(LoggableMixin).__init__(logger, parent_identifier, 'Streaming Thread')
        self.acquisition_thread = acquisition_thread
        self.pipeline = pipeline
        self.idle_timeout = idle_timeout
        self.parent_identifier = parent_identifier

        self.data = data_collection_object
        self._data_lock = data_collection_object_lock

        self._force_stop = False

    def stop(self):
        self._force_stop = True

    def stop_and_join(self):
        self.stop()
        self.join()

    def run(self):
        self.log('Entered.', logging.DEBUG)

        while not self._should_stop_collecting_streamed_data():
            try:
                datum = self.pipeline.get(timeout=self.idle_timeout)
                self.process_streamed_data(datum)
                self.pipeline.task_done()
            except queue.Empty:
                self.handle_idle_timeout()

        self.log('Exited.', logging.DEBUG)

    def _should_stop_collecting_streamed_data(self):
        """
        Check if the thread should stop reading data from the
        pipeline.

        Returns:
            bool: True if the thread should stop reading data,
            False otherwise.
        """
        return self._force_stop or (not self.acquisition_thread.is_alive() and self.pipeline.qsize() == 0)

    def process_streamed_data(self, datum):
        """
        Process streamed datum.

        This method is called when new data is streamed
        from the pipeline.

        Parameters:
            datum: The streamed datum.
        """
        with self._data_lock:
            self.data.append(datum)

    def handle_idle_timeout(self):
        """
        Handle the idle timeout.

        This method is called when no new data
        is received within the idle timeout.
        """
        pass


class TimeSeriesStreamingThread(StreamingThread):
    """
    A thread class that collects time-series data for
    devices implemented using the `AcquisitionMixin` class.
    """

    def __init__(
            self,
            parent: 'AcquisitionMixin',
    ):
        self.parent = parent
        super().__init__(
            parent.ts_acquisition_thread,
            parent.ts_pipeline,
            parent.ts_idle_timeout,
            parent.ts_data,
            parent.ts_data.lock,
            getattr(parent, 'DEVICE_PY_ALIAS', parent.__class__.__name__),
        )


class AcquisitionMixin(abc.ABC, LoggableMixin):
    """
    AcquisitionMixin provides the ability to acquire single
    and time-series data from a device.
    """

    DEFAULT_ACQ_INTERVAL = 0.01  # seconds
    DEFAULT_IDLE_TIMEOUT = 0.1  # seconds

    def __init__(self):
        super(LoggableMixin).__init__(logger, getattr(self, 'DEVICE_PY_ALIAS', self.__class__.__name__))
        self._ts_acquisition_thread: TimeSeriesAcquisitionThread | None = None
        self._ts_streaming_thread: TimeSeriesStreamingThread | None = None

        self._ts_pipeline = queue.Queue()
        self._ts_data = TimeSeriesData()

        self._ts_acquisition_interval = self.DEFAULT_ACQ_INTERVAL  # seconds
        self._ts_idle_timeout = self.DEFAULT_IDLE_TIMEOUT  # seconds

    @property
    def ts_acquisition_thread(self) -> TimeSeriesAcquisitionThread | None:
        """ Returns the time-series acquisition thread. """
        return self._ts_acquisition_thread

    @property
    def ts_streaming_thread(self) -> TimeSeriesStreamingThread | None:
        """ Returns the time-series streaming thread. """
        return self._ts_streaming_thread

    @property
    def ts_pipeline(self) -> queue.Queue:
        """ Returns the time-series pipeline. """
        return self._ts_pipeline

    @property
    def ts_data(self) -> TimeSeriesData:
        """ Returns the time-series data. """
        return self._ts_data

    @property
    def ts_acquisition_interval(self) -> float:
        """ Returns the time-series acquisition interval. """
        return self._ts_acquisition_interval

    @ts_acquisition_interval.setter
    def ts_acquisition_interval(self, value: float | None):
        """ Sets the time-series acquisition interval. """
        if value is not None:
            self._ts_acquisition_interval = value

    @property
    def ts_idle_timeout(self) -> float:
        """ Returns the time-series idle timeout. """
        return self._ts_idle_timeout

    @ts_idle_timeout.setter
    def ts_idle_timeout(self, value: float | None):
        """ Sets the time-series idle timeout. """
        if value is not None:
            self._ts_idle_timeout = value

    @abc.abstractmethod
    def setup_acquisition(
            self,
            ts_acquisition_interval: float = None,
            ts_idle_timeout: float = None
    ):
        """
        Sets up acquisition-related parameters.

        When passing None values, the object attribute
        values will not be updated.

        Override method in subclass to set up other device
        parameters critical to the acquisition process.

        Parameters
        ----------
        ts_acquisition_interval: float, optional
            The time-series acquisition interval.
        ts_idle_timeout: float, optional:
            The time-series idle timeout.
        """
        self.ts_acquisition_interval = ts_acquisition_interval
        self.ts_idle_timeout = ts_idle_timeout

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
            resume_event: threading.Event,
            pipeline_mode: str = 'aggregate',
            clear_data: bool = True,
    ):
        """
        Initializes all threads and starts the time-series acquisition.

        Parameters
        ----------
        start_event : threading.Event
            An event to trigger the start of data acquisition.
        stop_event : threading.Event
            An event to signal the end of data acquisition.
        resume_event : threading.Event
            An event to handle pause-resume requests of data acquisition.
        pipeline_mode : str, optional
            The mode for data pipeline handling ('aggregate' or 'stream').
            Default is 'aggregate'.
        clear_data: bool, optional
            Whether to clear old data.
            If False, the new data will be appended to the old data.

        Raises
        ------
        RuntimeError
            If the acquisition or streaming threads are already running.

        Notes
        -----
        """

        # TODO: assert pipeline_mode in ['at_end', 'stream']

        if self.ts_acquisition_thread is not None:
            self.ts_acquisition_thread.log('Attempted to start when it was already running.', level=logging.ERROR)
            raise RuntimeError('Attempted to start acquisition thread when it was already running.')  # TODO: change

        if self.ts_streaming_thread is not None:
            self.ts_streaming_thread.log('Attempted to start when it was already running.', level=logging.ERROR)
            raise RuntimeError('Attempted to start streaming thread when it was already running.')  # TODO: change

        if clear_data:
            self._ts_data = TimeSeriesData()

        self._ts_acquisition_thread = TimeSeriesAcquisitionThread(
                self, start_event, stop_event, resume_event, pipeline_mode)

        if pipeline_mode == 'stream':
            self._ts_streaming_thread = TimeSeriesStreamingThread(self)

        self._ts_acquisition_thread.start()
        if pipeline_mode == 'stream':
            self.ts_streaming_thread.start()

    @final
    def stop_time_series_acquisition(self, force_stop=False):
        """
        Stops the time-series acquisition.

        Parameters
        ----------
        force_stop: bool, optional
            Whether to forcefully stop the acquisition and streaming threads.
            Default to False.
        """
        if self._ts_acquisition_thread is not None:
            self._stop_and_join_thread('_ts_acquisition_thread', force_stop)

        if self.ts_streaming_thread is not None:
            self._stop_and_join_thread('_ts_streaming_thread', force_stop)
        else:
            self._collect_aggregated_data_from_pipeline()

    @final
    def save_time_series_data(self, file_path: str):
        # TODO: Decide how to save time series to file.
        pass

    def _stop_and_join_thread(self, thread_attribute_name: str, force_stop=False):
        """
        Stops and joins the acquisition or streaming thread.

        This method is used by the stop_time_series_acquisition method.
        It is not intended to be called directly.

        Parameters
        ----------
        thread_attribute_name: str
            The thread attribute name to stop and join.
        force_stop: bool, optional
            Whether to forcefully stop the acquisition and streaming threads.
            Default to False.
        """
        thread = getattr(self, thread_attribute_name)
        if force_stop:
            thread.stop()
        thread.join()
        del thread
        setattr(self, thread_attribute_name, None)
        thread_name = 'Acquisition thread' if thread_attribute_name == '_ts_acquisition_thread' else 'Streaming thread'
        self.log(f'Cleared {thread_name}.')

    def _collect_aggregated_data_from_pipeline(self):
        """
        Collects the data from the pipeline.
        Used when the streaming thread is not running.
        """
        try:
            data = self.ts_pipeline.get()
            self.ts_data.append(data)
            self.ts_pipeline.task_done()
            self.log('Retrieved data.')
        except queue.Empty:
            self.log('Already stopped streaming data. No new data retrieved.')
