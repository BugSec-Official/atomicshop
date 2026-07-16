"""Set the current process's Windows priority class and opt out of Win11 EcoQoS
power throttling, so the process isn't starved of CPU / parked on E-cores under load.

All failures are logged and swallowed — a scheduling tweak must never crash the server.
Windows does not inherit above_normal/high priority to child processes, so each
process calls this for itself.
"""
import ctypes
import multiprocessing
import os
import sys
from ctypes import wintypes

import psutil

from ...print_api import print_api


# Config string -> psutil priority class. 'normal' is intentionally absent (no change).
# psutil priority constants exist only on Windows, so build the map guarded.
if sys.platform == 'win32':
    _PRIORITY_CLASSES = {
        'above_normal': psutil.ABOVE_NORMAL_PRIORITY_CLASS,
        'high': psutil.HIGH_PRIORITY_CLASS,
    }
else:
    _PRIORITY_CLASSES = {}

_VALID_PRIORITIES = frozenset({'normal', 'above_normal', 'high'})

# SetProcessInformation(ProcessPowerThrottling): opt out of EcoQoS execution-speed
# throttling. ControlMask picks the knob, StateMask=0 turns it off (full speed).
_PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
_PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
_PROCESS_INFORMATION_CLASS_POWER_THROTTLING = 4


class _ProcessPowerThrottlingState(ctypes.Structure):
    """ctypes mirror of the Win32 PROCESS_POWER_THROTTLING_STATE struct passed to
    SetProcessInformation. Version is the struct version; ControlMask selects which
    throttling policies to manage; StateMask holds their on/off bits."""
    _fields_ = [
        ('Version', wintypes.ULONG),
        ('ControlMask', wintypes.ULONG),
        ('StateMask', wintypes.ULONG),
    ]


def _disable_power_throttling() -> bool:
    """Turn off Win11 EcoQoS execution-speed throttling for the current process.

    Calls kernel32 SetProcessInformation with a PROCESS_POWER_THROTTLING_STATE that
    manages EXECUTION_SPEED with its state bit cleared (0 = throttling disabled = full
    clock). Windows-only; the caller guards both platform and exceptions.

    :return: True if SetProcessInformation reported success, False otherwise.
    """
    state = _ProcessPowerThrottlingState(
        Version=_PROCESS_POWER_THROTTLING_CURRENT_VERSION,
        ControlMask=_PROCESS_POWER_THROTTLING_EXECUTION_SPEED,
        StateMask=0,
    )
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    # argtypes so the process handle isn't truncated on 64-bit.
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.SetProcessInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.SetProcessInformation.restype = wintypes.BOOL
    ok = kernel32.SetProcessInformation(
        kernel32.GetCurrentProcess(),
        _PROCESS_INFORMATION_CLASS_POWER_THROTTLING,
        ctypes.byref(state),
        ctypes.sizeof(state),
    )
    return bool(ok)


def boost_process_priority(
        priority: str = 'normal',
        disable_power_throttling: bool = False,
        logger=None,
) -> dict:
    """Raise the current process's Windows scheduling priority and, on Windows, opt it
    out of Win11 EcoQoS power throttling, so it is not starved of CPU or parked on
    efficiency cores under load. Best-effort: every failure is logged and swallowed,
    never raised. No-op off Windows and for priority='normal'.

    :param priority: target priority class — 'normal' (leave priority unchanged),
        'above_normal', or 'high'. An unrecognized value is left unchanged and logged as
        a warning; 'realtime' is intentionally not selectable.
    :param disable_power_throttling: when True and on Windows, disable EcoQoS
        execution-speed throttling for this process. Ignored off Windows.
    :param logger: optional logging.Logger for the warning/info messages; when None they
        go to stdout via print_api.
    :return: dict of what was applied — 'priority_applied' is the priority string set, or
        None if left unchanged/failed; 'power_throttling_disabled' is True if throttling
        was turned off, else False.
    """
    result = {'priority_applied': None, 'power_throttling_disabled': False}

    priority = (priority or 'normal').lower()
    if priority not in _VALID_PRIORITIES:
        print_api(f"Unrecognized process_priority {priority!r}; leaving priority unchanged. "
                  f"Valid: {', '.join(sorted(_VALID_PRIORITIES))}.",
                  logger=logger, logger_method='warning')
    elif priority in _PRIORITY_CLASSES:
        try:
            psutil.Process().nice(_PRIORITY_CLASSES[priority])
            result['priority_applied'] = priority
        except (psutil.Error, OSError) as exc:
            print_api(f"Could not set process priority to {priority!r}: {exc}",
                      logger=logger, logger_method='warning')

    if disable_power_throttling and sys.platform == 'win32':
        try:
            result['power_throttling_disabled'] = _disable_power_throttling()
        except Exception as exc:   # best-effort tuning: never propagate
            print_api(f"Could not disable power throttling: {exc}",
                      logger=logger, logger_method='warning')

    proc_name = multiprocessing.current_process().name
    print_api(f"Process tuning [{proc_name} pid={os.getpid()}]: "
              f"priority={result['priority_applied'] or 'unchanged'}, "
              f"power_throttling_disabled={result['power_throttling_disabled']}",
              logger=logger, logger_method='info')
    return result
