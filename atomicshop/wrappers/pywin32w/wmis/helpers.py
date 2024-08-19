import win32com.client


class WmiMethodExecutionError(Exception):
    pass


class WmiMethodParameterError(Exception):
    pass


class EmptyValue:
    pass


def get_method(
        wmi_object: win32com.client.CDispatch,
        method_name: str
):
    """
    Get the WMI method.

    :param wmi_object: WMI object.
    :param method_name: str, name of the method.
    :return: WMI method object.
    """

    return wmi_object.Methods_(method_name)


def get_method_parameter_instance(
        method: win32com.client.CDispatch
):
    """
    Get the WMI method parameter.

    :param method: WMI method object.
    :return: WMI method parameter object.
    """

    return method.inParameters.SpawnInstance_()


def call_method(
        wmi_object: win32com.client.CDispatch,
        method_name: str,
        value: any = EmptyValue
):
    """
    Call the WMI method.

    :param wmi_object: WMI object.
    :param method_name: str, name of the method.
    :param value: any, value to pass to the method.
        Methods can receive a None value if they don't require any parameters.
        If the method doesn't require any parameters, leave it as 'EmptyValue' class.
    :return: WMI method object.
    """

    # Get the method instance out of the WMI object.
    method = get_method(wmi_object, method_name)

    # Check if the method requires any parameters.
    if not method.InParameters and not isinstance(value, EmptyValue):
        raise WmiMethodParameterError(f"Method '{method_name}' doesn't require any parameters.\nValue: {value}")
    elif method.InParameters and isinstance(value, EmptyValue):
        raise WmiMethodParameterError(f"Method '{method_name}' requires parameters.\nValue: {value}")

    # If value was passed for the method to set.
    if not isinstance(value, EmptyValue):
        # Get the input parameters names that a method requires.
        # The names are stored in a list of tuples where the first element is the name of the parameter and the second
        # element is a boolean that indicates if the parameter is an array.
        input_parameters_names = [
            (input_parameter.Name, input_parameter.IsArray) for input_parameter in method.InParameters.Properties_]

        # Check if the value and the input parameter is a list.
        if not (isinstance(value, list) or value is None) and input_parameters_names[0][1]:
            raise WmiMethodParameterError(f"Parameter '{input_parameters_names[0][0]}' must be a list.\nValue: {value}")
        elif (isinstance(value, list) or value is None) and not input_parameters_names[0][1]:
            raise WmiMethodParameterError(f"Parameter '{input_parameters_names[0][0]}' "
                                          f"must be a single value.\nValue: {value}")

        # Get generic parameter instance.
        parameter_instance = get_method_parameter_instance(method)
        # Set the attribute of the parameter name instance that we retrieved from above to the value.
        # At this point only been using one parameter for a method, so maybe need to refactor this part if needed
        # in the future for more than one parameter.
        setattr(parameter_instance, input_parameters_names[0][0], value)

        # Execute the method with the parameter instance.
        result = wmi_object.ExecMethod_(method_name, parameter_instance)
    else:
        # Execute the method without any parameters.
        result = wmi_object.ExecMethod_(method_name)

    # Getting Result.
    # Get the output parameters names that a method returns.
    if method.OutParameters:
        out_properties_names = [
            (out_property.Name, out_property.IsArray) for out_property in method.OutParameters.Properties_]
    else:
        out_properties_names = []

    # Get the results for each parameter the method returns.
    results = []
    for name, is_array in out_properties_names:
        value = result.Properties_(name).Value
        if is_array:
            results.append(list(value or []))
        else:
            results.append(value)

    # Check if the method executed successfully.
    for result in results:
        if result != 0:
            raise WmiMethodExecutionError(f"Failed to execute method '{method_name}' with error code: {result}")


"""
# Setting SeDebugPrivilege
import win32security, ntsecuritycon, win32con, win32api
privs = ((win32security.LookupPrivilegeValue('',ntsecuritycon.SE_DEBUG_NAME), win32con.SE_PRIVILEGE_ENABLED),)
hToken = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_ALL_ACCESS)
win32security.AdjustTokenPrivileges(hToken, False, privs)
win32api.CloseHandle(hToken)
"""