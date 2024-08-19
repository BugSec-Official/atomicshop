from dataclasses import dataclass

from ..file_io import tomls


class CategoryNotFoundInConfigError(Exception):
    pass


@dataclass
class PropertyUpdate:
    """
    :param category: str, Category in the config file.
    :param category_property: str, Property in the category.
    :param value: str, Value to set to the property.
    """
    category: str
    category_property: str
    value: any


def update_properties(
        property_update_list: list[PropertyUpdate],
        config_file_path: str
) -> None:
    """
    Edit a property in the config file.

    :param property_update_list: list of PropertyUpdate objects.
    :param config_file_path: str, Path to the config file.

    -----------

    Config Example:
    [category]
    category_property = value
    """

    toml_config = tomls.read_toml_file(config_file_path)

    for property_update in property_update_list:
        if property_update.category not in toml_config:
            raise CategoryNotFoundInConfigError(f"Category '{property_update.category}' not found in the config file.")

    changes_dict: dict = dict()
    for property_update in property_update_list:
        if property_update.category in changes_dict:
            changes_dict[property_update.category].update({property_update.category_property: property_update.value})
        else:
            changes_dict[property_update.category] = {property_update.category_property: property_update.value}

    tomls.update_toml_file_with_new_config(
        main_config_file_path=config_file_path,
        changes_dict=changes_dict
    )
