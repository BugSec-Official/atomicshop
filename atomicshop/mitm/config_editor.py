import configparser


class CategoryNotFoundInConfigError(Exception):
    pass


def edit_property(category: str, category_property: str, value: str, config_file_path: str) -> None:
    """
    Edit a property in the config file.

    :param category: str, Category in the config file.
    :param category_property: str, Property in the category.
    :param value: str, Value to set to the property.
    :param config_file_path: str, Path to the config file.

    :return: None.

    -----------

    Config Example:
    [category]
    category_property = value
    """
    config = configparser.ConfigParser()
    config.read(config_file_path)

    if category not in config:
        raise CategoryNotFoundInConfigError(f"Category '{category}' not found in the config file.")

    # Change the value of the property if it is different from the current value.
    current_value = config[category][category_property]
    if current_value != value:
        config[category][category_property] = value

        with open(config_file_path, "w") as configfile:
            config.write(configfile)
