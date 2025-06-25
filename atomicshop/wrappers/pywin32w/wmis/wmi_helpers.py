import os
from typing import Union

import win32com.client
from win32com.client import CDispatch


class WmiMethodExecutionError(Exception):
    pass


class WmiMethodParameterError(Exception):
    pass


class EmptyValue:
    pass
_EMPTY_VALUE = EmptyValue()


class WMINetworkAdapterNotFoundError(Exception):
    pass


LOCAL_SERVER: str = '.'


def get_wmi_instance(
        server: str = LOCAL_SERVER,
        namespace: str = 'root\\cimv2',
        wmi_instance: CDispatch = None,
        locator: CDispatch = None
) -> tuple[CDispatch, CDispatch]:
    """
    Get the WMI instance.

    :param server: str, The server you want to connect to. Default is '.' (local machine).
    :param namespace: str, WMI namespace. Default is 'root\\cimv2'.
        Other examples:
            'root\\StandardCimv2'
    :param wmi_instance: WMI connected instance.
    :param locator: WMI locator instance. If not provided, a new one will be created.
    :return: WMI instance.

    ===================

    If you want to connect directly to a WMI namespace, you can use the following code:
    return win32com.client.GetObject(f"winmgmts:\\\\{location}\\{namespace}")
    """

    if not locator:
        # This is a better way to get the WMI instance, since you have more control over the WMI object.
        locator: CDispatch = win32com.client.Dispatch('WbemScripting.SWbemLocator')

    if wmi_instance:
        server_from_instance, namespace_from_instance = get_connection_details(wmi_instance)

        # If current server name of the wmi connection is not the same as was passed to the function,
        # then create a new connection to the server.
        if server_from_instance.lower() != server.lower():
            if not (server_from_instance.lower() == os.environ["COMPUTERNAME"].lower() and server.lower() == LOCAL_SERVER):
                wmi_instance = locator.ConnectServer(server, namespace)
        # If the namespace is not the same as was passed to the function.
        if namespace_from_instance != namespace:
            wmi_instance = locator.ConnectServer(server, namespace)

    else:
        wmi_instance: CDispatch = locator.ConnectServer(server, namespace)

    return wmi_instance, locator


def get_connection_details(wmi_instance: CDispatch) -> tuple[str, str]:
    """
    Get the connection details: connected server and namespace.

    :param wmi_instance: WMI instance.
    :return: tuple of server and namespace.
    """

    # Get the current connection details.
    # Get the security object for the WMI instance.
    security_object: CDispatch = wmi_instance.Get("__SystemSecurity=@")
    # Get the Paths.
    path: CDispatch = security_object.Path_

    server_from_instance: str = path.Server
    namespace_from_instance: str = path.Namespace

    return server_from_instance, namespace_from_instance


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
        value: Union[
            Union[tuple, dict],
            Union[bool, str, list]] = _EMPTY_VALUE
):
    """
    Call the WMI method.

    :param wmi_object: WMI object.
    :param method_name: str, name of the method.
    :param value: tuple, value to pass to the method.
        tuple: If ou pass a tuple, it will be unpacked and passed as positional arguments.
            Dor example if a method requires 2 parameters, you can pass a tuple with 2 values.
        dict: If you pass a dictionary, it will be unpacked and passed as keyword arguments.

        If you pass a single value, which is not a dict or tuple, it will be passed as a single parameter.

        Methods can receive a None value if they don't require any parameters.
        If the method doesn't require any parameters, leave it as 'EmptyValue' class.
    :return: WMI method object.
    """

    # Assign the single value to a tuple if it is not already a tuple or dict and not an EmptyValue.
    if not isinstance(value, (EmptyValue, tuple, dict)):
        value = (value,)

    # Get the method instance out of the WMI object.
    method = get_method(wmi_object, method_name)

    # ── discover the method’s IN parameters up-front ─────────────────────────────
    if method.InParameters:
        input_properties: list = [(in_property.Name, in_property.IsArray) for in_property in method.InParameters.Properties_]
    else:
        input_properties: list = []  # no inputs expected

    expected = len(input_properties)  # how many inputs the method wants

    got_tuple = isinstance(value, tuple)
    got_dict = isinstance(value, dict)
    got_empty = isinstance(value, EmptyValue)

    # ── validate the caller’s intent ─────────────────────────────────────────────
    if expected == 0 and not got_empty:
        raise WmiMethodParameterError(
            f"Method '{method_name}' takes no parameters, got: {value!r}"
        )
    if expected > 0 and got_empty:
        raise WmiMethodParameterError(
            f"Method '{method_name}' expects {expected} parameter(s); none given."
        )
    if got_tuple and len(value) != expected:
        raise WmiMethodParameterError(
            f"Method '{method_name}' expects {expected} parameter(s); "
            f"{len(value)} positional value(s) given."
        )

    # ── prepare the parameter object if needed ──────────────────────────────────
    if expected == 0:  # simple – no inputs
        result = wmi_object.ExecMethod_(method_name)

    else:
        param_obj = get_method_parameter_instance(method)

        if got_tuple:  # positional list / tuple
            for (name, is_array), val in zip(input_properties, value):
                setattr(param_obj, name, val)

        elif got_dict:  # mapping by name
            for name, _ in input_properties:
                if name in value:
                    setattr(param_obj, name, value[name])

        else:  # single scalar for one-input method
            name, is_array = input_properties[0]
            if is_array and not (isinstance(value, list) or value is None):
                raise WmiMethodParameterError(
                    f"Parameter '{name}' must be a list.\nValue: {value!r}"
                )
            setattr(param_obj, name, value)

        result = wmi_object.ExecMethod_(method_name, param_obj)

    # ── collect OUT parameters & check return code ──────────────────────────────
    out_vals = []
    if method.OutParameters:
        for parameter in method.OutParameters.Properties_:
            out_vals.append(result.Properties_(parameter.Name).Value)

    # return-code conventions: 0 = OK, 1 = OK-needs-reboot
    if out_vals and out_vals[0] not in (0, 1):
        result_code: int = out_vals[0]
        if result_code == 91:
            raise PermissionError(
                f"Method '{method_name}' failed (code {result_code}) – try with admin rights."
            )
        if result_code == 68:
            raise WmiMethodExecutionError(
                f"Method '{method_name}' failed (code {result_code}) – Invalid input parameter"
            )
        raise WmiMethodExecutionError(
            f"Method '{method_name}' failed with error code {result_code}"
        )

    return out_vals or None


"""
# Setting SeDebugPrivilege
import win32security, ntsecuritycon, win32con, win32api
privs = ((win32security.LookupPrivilegeValue('',ntsecuritycon.SE_DEBUG_NAME), win32con.SE_PRIVILEGE_ENABLED),)
hToken = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_ALL_ACCESS)
win32security.AdjustTokenPrivileges(hToken, False, privs)
win32api.CloseHandle(hToken)
"""