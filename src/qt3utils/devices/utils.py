from typing import TypeVar, Any, List, Type

from pyvisa import ResourceManager, VisaIOError
from pyvisa.attributes import Attribute
from pyvisa.resources import Resource, SerialInstrument, USBInstrument, GPIBInstrument, MessageBasedResource

ResourceType = TypeVar('ResourceType', Resource, SerialInstrument, USBInstrument, GPIBInstrument, MessageBasedResource)
ResourceQueryType = TypeVar('ResourceQueryType', SerialInstrument, USBInstrument, GPIBInstrument, MessageBasedResource)


# A_ = TypeVar('A_', bound=Attribute)


# def get_pyvisa_resource_attr_values(resource: Resource):
#     attr_values = {}
#     for attr in resource.visa_attributes_classes:
#         try:
#             value = resource.get_visa_attribute(attr.attribute_id)
#             attr_values[attr] = value
#         except VisaIOError as e:
#             attr_values[attr] = None


def find_available_resources_by_visa_attribute(rm: ResourceManager, visa_attribute: Type[Attribute],
                                               desired_attr_value: str, is_partial=False) -> List[ResourceType]:
    """
    For example, for a given USB resource, you want all resources with attribute AttrVI_ATTR_MODEL_NAME == 'Matisse TS',
    or 'Matisse TS' in AttrVI_ATTR_MODEL_NAME.
    """
    connected_resources_names = rm.list_resources()
    matching_attr_resource_list: list[ResourceType] = []

    for resource_name in connected_resources_names:
        try:
            resource = rm.open_resource(resource_name)
            resource.clear()
            resource_attr_value = resource.get_visa_attribute(visa_attribute.attribute_id)

            match_condition = (desired_attr_value in resource_attr_value) \
                if is_partial else (resource_attr_value == desired_attr_value)
            if match_condition:
                matching_attr_resource_list.append(resource)
            resource.close()
        except VisaIOError as e:
            pass  # resource is probably used by another application, so we ignore it.

    return matching_attr_resource_list


def find_available_resources_by_idn(rm: ResourceManager, desired_idn: str, is_partial=False) -> list[ResourceQueryType]:
    """
    For example, you want all resources with IDN == 'Matisse TS' or 'Matisse TS' in IDN.
    """
    connected_resources_names = rm.list_resources()
    matching_idn_resource_list: list[ResourceQueryType] = []

    for resource_name in connected_resources_names:
        try:
            resource = rm.open_resource(resource_name)
            if isinstance(resource, MessageBasedResource):
                resource.clear()
                idn = resource.query('*IDN?')

                match_condition = (desired_idn in idn) if is_partial else (idn == desired_idn)
                if match_condition:
                    matching_idn_resource_list.append(resource)
            resource.close()
        except VisaIOError as e:
            pass  # resource is probably used by another application, so we ignore it.

    return matching_idn_resource_list
