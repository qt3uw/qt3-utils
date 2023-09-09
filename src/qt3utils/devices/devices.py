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
from src.qt3utils.logger import get_configured_logger, LoggableMixin

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


class Device(abc.ABC, LoggableMixin):
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
        super(LoggableMixin).__init__(logger=get_configured_logger(self.DEVICE_PY_ALIAS))
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
