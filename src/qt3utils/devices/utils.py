import threading
from typing import TypeVar, List, Type

import pyvisa
import pyvisa.constants
from pyvisa import ResourceManager, VisaIOError
from pyvisa.attributes import Attribute
from pyvisa.resources import Resource, SerialInstrument, USBInstrument, GPIBInstrument, MessageBasedResource

# TODO: This types doesn't work great with type hinting. Find solution.
ResourceType = TypeVar('ResourceType', Resource, MessageBasedResource, SerialInstrument, USBInstrument, GPIBInstrument)
MessageBasedResourceType = TypeVar(
    'MessageBasedResourceType', MessageBasedResource, SerialInstrument, USBInstrument, GPIBInstrument)


# A_ = TypeVar('A_', bound=Attribute)


# def get_pyvisa_resource_attr_values(resource: Resource):
#     attr_values = {}
#     for attr in resource.visa_attributes_classes:
#         try:
#             value = resource.get_visa_attribute(attr.attribute_id)
#             attr_values[attr] = value
#         except VisaIOError as e:
#             attr_values[attr] = None


def find_available_resources_by_visa_attribute(
        rm: ResourceManager,
        visa_attribute: Type[Attribute],
        desired_attr_value: str,
        is_partial=False,
        **rm_kwargs,
) -> List[ResourceType]:
    """
    For example, for a given USB resource, you want all resources with attribute AttrVI_ATTR_MODEL_NAME == 'Matisse TS',
    or 'Matisse TS' in AttrVI_ATTR_MODEL_NAME.
    """
    connected_resources_names = rm.list_resources()
    matching_attr_resource_list: list[ResourceType] = []

    for resource_name in connected_resources_names:
        try:
            resource = rm.open_resource(resource_name, **rm_kwargs)
            try:
                resource.clear()
            except VisaIOError as e:  # the device does not properly implement clear
                pass

            resource_attr_value = resource.get_visa_attribute(visa_attribute.attribute_id)

            match_condition = (desired_attr_value in resource_attr_value) \
                if is_partial else (resource_attr_value == desired_attr_value)
            if match_condition:
                matching_attr_resource_list.append(resource)
            resource.close()
        except VisaIOError as e:
            pass  # resource is probably used by another application, so we ignore it.

    return matching_attr_resource_list


def find_available_resources_by_idn(
        rm: ResourceManager,
        desired_idn: str,
        is_partial=False,
        write_termination: str = r'\n',
        read_termination: str = None,
        **rm_kwargs,
) -> list[MessageBasedResourceType]:
    """
    For example, you want all resources with IDN == 'Matisse TS' or 'Matisse TS' in IDN.
    """
    connected_resources_names = rm.list_resources()
    matching_idn_resource_list: list[MessageBasedResourceType] = []

    for resource_name in connected_resources_names:
        try:
            resource = rm.open_resource(
                resource_name,
                write_termination=write_termination,
                read_termination=read_termination, **rm_kwargs
            )
            if isinstance(resource, MessageBasedResource):
                try:
                    resource.clear()
                except VisaIOError as e:  # the device does not properly implement clear
                    force_clear_message_based_resource(resource)

                idn = resource.query(r'*IDN?')

                read_termination, idn = auto_detect_read_termination(resource, idn)
                resource.read_termination = read_termination

                resource.close()

                match_condition = (desired_idn in idn) if is_partial else (idn == desired_idn)
                if match_condition:
                    matching_idn_resource_list.append(resource)
        except VisaIOError as e:
            pass  # resource is probably used by another application, so we ignore it.

    return matching_idn_resource_list


def force_clear_message_based_resource(
        resource: MessageBasedResourceType,
        quick_read_timeout: float = 10,
        lock: threading.Lock = None
):
    if lock is not None:
        lock.acquire()

    resource.flush(pyvisa.constants.BufferOperation.discard_write_buffer)
    resource.flush(pyvisa.constants.BufferOperation.discard_read_buffer)

    cleared = False
    original_timeout = resource.timeout
    resource.timeout = quick_read_timeout  # ms
    while not cleared:
        try:
            resource.read()
        except pyvisa.errors.VisaIOError:
            cleared = True
    resource.timeout = original_timeout

    if lock is not None:
        lock.release()


def auto_detect_read_termination(resource: MessageBasedResourceType, read_value: str = None) -> str | tuple[str, str]:
    """
    This function is used to detect the read termination character of a resource.
    """
    return_read_value = False
    if read_value is None:
        read_value = resource.query(r'*IDN?')
        return_read_value = True

    read_termination = resource.read_termination
    if read_value.endswith(r'\n'):
        read_value = read_value[:-1]
        read_termination = r'\n' if read_termination is None else r'\n' + read_termination
    if read_value.endswith(r'\r'):
        read_value = read_value[:-1]
        read_termination = r'\r' if read_termination is None else r'\r' + read_termination

    if return_read_value:
        return read_termination, read_value
    else:
        return read_termination
