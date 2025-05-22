import ctypes
from ctypes import wintypes
import uuid


# Constants and functions for creating root-enumerated device nodes
# ---------------------------------------------------------------------------
#  Compatibility shim: wintypes.ULONG_PTR is missing on some builds
# ---------------------------------------------------------------------------
if not hasattr(wintypes, "ULONG_PTR"):
    if ctypes.sizeof(ctypes.c_void_p) == 8:          # 64-bit Python
        wintypes.ULONG_PTR = ctypes.c_uint64
    else:                                           # 32-bit Python
        wintypes.ULONG_PTR = ctypes.c_uint32

# ------------------------------------------------------------------
# SetupDi* “device‑registry property” indices (SPDRP_…)
# From Microsoft’s setupapi.h – keep them as ints.
# ------------------------------------------------------------------
SPDRP_DEVICEDESC      = 0   # REG_SZ   – Device description (friendly name)
SPDRP_HARDWAREID      = 1   # REG_MULTI_SZ – Hardware‑ID list
SPDRP_COMPATIBLEIDS   = 2   # REG_MULTI_SZ – Compatible‑ID list
SPDRP_SERVICE         = 4   # REG_SZ   – Service/miniport to load
SPDRP_CLASS           = 7   # REG_SZ   – Class name (e.g. "Net")
SPDRP_CLASSGUID       = 8   # REG_SZ   – Class GUID in string form

# newdev.h  (Windows SDK) / SetupAPI
DIF_REGISTERDEVICE   = 0x00000019
DIF_REMOVE           = 0x00000005
DICD_GENERATE_ID     = 0x00000001
INSTALLFLAG_FORCE            = 0x00000001  # install even if “better” driver exists
INSTALLFLAG_READONLY         = 0x00000002  # don’t write driver to driver store
INSTALLFLAG_NONINTERACTIVE   = 0x00000004  # never display UI (silent mode)

DIGCF_PRESENT        = 0x00000002
ERROR_NO_MORE_ITEMS  = 259

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
newdev   = ctypes.WinDLL("newdev",   use_last_error=True)

# ---------------------------------------------------------------------------
#  Structures & prototypes
# ---------------------------------------------------------------------------
class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize",   wintypes.DWORD),
        ("ClassGuid", ctypes.c_byte * 16),
        ("DevInst", wintypes.DWORD),
        ("Reserved", wintypes.ULONG_PTR),
    ]

# --- creation helpers ------------------------------------------------------
SetupDiCreateDeviceInfoList = setupapi.SetupDiCreateDeviceInfoList
SetupDiCreateDeviceInfoList.argtypes = [ctypes.POINTER(ctypes.c_byte * 16), wintypes.HWND]
SetupDiCreateDeviceInfoList.restype  = wintypes.HANDLE

SetupDiCreateDeviceInfoW = setupapi.SetupDiCreateDeviceInfoW
SetupDiCreateDeviceInfoW.argtypes = [
    wintypes.HANDLE, wintypes.LPCWSTR,
    ctypes.POINTER(ctypes.c_byte * 16),
    wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD,
    ctypes.POINTER(SP_DEVINFO_DATA)
]
SetupDiCreateDeviceInfoW.restype = wintypes.BOOL

SetupDiSetDeviceRegistryPropertyW = setupapi.SetupDiSetDeviceRegistryPropertyW
SetupDiSetDeviceRegistryPropertyW.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.DWORD,
    wintypes.LPBYTE, wintypes.DWORD
]
SetupDiSetDeviceRegistryPropertyW.restype = wintypes.BOOL

SetupDiCallClassInstaller = setupapi.SetupDiCallClassInstaller
SetupDiCallClassInstaller.argtypes = [
    wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA)
]
SetupDiCallClassInstaller.restype = wintypes.BOOL

# --- enumeration / removal -------------------------------------------------
SetupDiGetClassDevsW = setupapi.SetupDiGetClassDevsW
SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(ctypes.c_byte * 16),
                                 wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
SetupDiGetClassDevsW.restype  = wintypes.HANDLE

SetupDiEnumDeviceInfo = setupapi.SetupDiEnumDeviceInfo
SetupDiEnumDeviceInfo.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                  ctypes.POINTER(SP_DEVINFO_DATA)]
SetupDiEnumDeviceInfo.restype = wintypes.BOOL

SetupDiGetDeviceRegistryPropertyW = setupapi.SetupDiGetDeviceRegistryPropertyW
SetupDiGetDeviceRegistryPropertyW.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.PBYTE, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD)
]
SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL

SetupDiDestroyDeviceInfoList = setupapi.SetupDiDestroyDeviceInfoList
SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
SetupDiDestroyDeviceInfoList.restype  = wintypes.BOOL

UpdateDriverForPlugAndPlayDevicesW = newdev.UpdateDriverForPlugAndPlayDevicesW
UpdateDriverForPlugAndPlayDevicesW.argtypes = [
    wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
    wintypes.DWORD, ctypes.POINTER(wintypes.BOOL)
]
UpdateDriverForPlugAndPlayDevicesW.restype = wintypes.BOOL


# ---------------------------------------------------------------------------
# 1. Create a root-enumerated devnode (idempotent)
# ---------------------------------------------------------------------------
def create_root_enumerated_devnode(
    class_guid: str,
    friendly_name: str,            # what shows in Device Manager
    hardware_ids: "list[str] | str",
    compatible_ids: "list[str] | str | None" = None,
    devdesc_override: str | None = None,
    create_flags: int = DICD_GENERATE_ID,
    existing_ok: bool = True,
) -> None:
    """
    Programmatically create a *root‑enumerated* device node, set its
    Hardware‑ID (and optional Compatible‑ID) list, then ask Plug and Play
    to register/ install whatever driver matches those IDs.

    Parameters
    ----------
    class_guid : string representation of a GUID.
        Device‑class GUID (e.g. GUID_DEVCLASS_NET, GUID_DEVCLASS_MEDIA …).
        Example:
            class_guid="{4d36e972-e325-11ce-bfc1-08002be10318}"
            This is the GUID for network adapters.

    friendly_name : str
        Initial instance name placed in the registry (DeviceDesc).
        Also, will be shown in Device Manager.

    hardware_ids : str | list[str]
        One or more hardware IDs (MULTI_SZ).  The *first* one is the key
        identifier PnP uses when selecting an INF.

    compatible_ids : str | list[str] | None
        Optional Compatible‑ID list (another MULTI_SZ, lower priority).

    devdesc_override : str | None
        If supplied, written to SPDRP_DEVICEDESC (rarely necessary because
        the INF’s own DeviceDesc usually replaces it).

    create_flags : int
        Flags for SetupDiCreateDeviceInfoW.  Default is DICD_GENERATE_ID.

    existing_ok : bool
        If True, silently succeed when the devnode already exists.
    """

    class_guid_bytes = uuid.UUID(class_guid).bytes_le
    class_guid_object = (ctypes.c_byte * 16).from_buffer_copy(class_guid_bytes)

    # --- 1. Create a temporary empty device‑info set -------------------
    hdi = SetupDiCreateDeviceInfoList(class_guid_object, None)  # Open a new, empty set
    if hdi == wintypes.HANDLE(-1).value:  # INVALID_HANDLE_VALUE?
        raise ctypes.WinError(ctypes.get_last_error())  # Bail out on failure

    # Prepare the SP_DEVINFO_DATA structure -----------------------------
    devinfo = SP_DEVINFO_DATA()  # Zero‑initialised struct
    devinfo.cbSize = ctypes.sizeof(devinfo)  # Must set cbSize field

    # --- 2. Create (or open) the devnode itself ------------------------
    if not SetupDiCreateDeviceInfoW(
            hdi,  # Info‑set handle
            friendly_name,  # Instance name
            class_guid_object,  # Class GUID
            None, None,  # (Description, parent window)
            create_flags,  # e.g. DICD_GENERATE_ID
            ctypes.byref(devinfo)  # Receives devinfo data
    ):
        err = ctypes.get_last_error()  # Capture error now
        SetupDiDestroyDeviceInfoList(hdi)  # Clean up handle
        if not (existing_ok and err == 0xE0000217):  # ERROR_DEVINST_ALREADY_EXISTS
            raise ctypes.WinError(err)  # Re‑raise unless allowed

    # --- 3. Build MULTI_SZ buffers and write registry properties -------
    def _multisz(lst_or_str):  # Helper → MULTI_SZ buffer
        buf = lst_or_str if isinstance(lst_or_str, str) else "\0".join(lst_or_str)
        return ctypes.create_unicode_buffer(buf + "\0")  # Extra trailing NUL

    # Hardware‑ID list (required) ---------------------------
    hwid = _multisz(hardware_ids)  # Build MULTI_SZ buffer
    if not SetupDiSetDeviceRegistryPropertyW(
            hdi, ctypes.byref(devinfo), SPDRP_HARDWAREID,  # Property to set
            ctypes.cast(hwid, wintypes.LPBYTE),  # Cast to LPBYTE
            (len(hwid) + 1) * ctypes.sizeof(ctypes.c_wchar)  # Size in bytes
    ):
        SetupDiDestroyDeviceInfoList(hdi)
        raise ctypes.WinError(ctypes.get_last_error())

    # Compatible‑ID list (optional) -------------------------
    if compatible_ids:
        cid = _multisz(compatible_ids)  # Build MULTI_SZ buffer
        if not SetupDiSetDeviceRegistryPropertyW(
                hdi, ctypes.byref(devinfo), SPDRP_COMPATIBLEIDS,
                ctypes.cast(cid, wintypes.LPBYTE),
                (len(cid) + 1) * ctypes.sizeof(ctypes.c_wchar)
        ):
            SetupDiDestroyDeviceInfoList(hdi)
            raise ctypes.WinError(ctypes.get_last_error())

    # DeviceDesc override (optional) -----------------------
    if devdesc_override:
        desc = ctypes.create_unicode_buffer(devdesc_override + "\0")
        if not SetupDiSetDeviceRegistryPropertyW(
                hdi, ctypes.byref(devinfo), SPDRP_DEVICEDESC,
                ctypes.cast(desc, wintypes.LPBYTE),
                (len(desc) + 1) * ctypes.sizeof(ctypes.c_wchar)
        ):
            SetupDiDestroyDeviceInfoList(hdi)
            raise ctypes.WinError(ctypes.get_last_error())

    # --- 4. Hand the devnode to the class installer --------------------
    if not SetupDiCallClassInstaller(
            DIF_REGISTERDEVICE,  # “Install this device”
            hdi, ctypes.byref(devinfo)
    ):
        err = ctypes.get_last_error()
        # ERROR_DI_DO_DEFAULT means “already registered / nothing to do”
        if not (existing_ok and err == 0xE000020E):
            SetupDiDestroyDeviceInfoList(hdi)
            raise ctypes.WinError(err)

    # --- 5. Final cleanup ----------------------------------------------
    SetupDiDestroyDeviceInfoList(hdi)  # Always release handle


# ---------------------------------------------------------------------------
# 2. Bind driver from netloop.inf (idempotent)
# ---------------------------------------------------------------------------
def update_driver_for_hwids(
    hardware_ids: "str | list[str]",
    inf_path: str,
    force_install: bool = False,
    quiet: bool = True,
    existing_ok: bool = True,
) -> bool:
    """
    Install / update the driver in *inf_path* for every present device whose first
    Hardware‑ID matches *hardware_ids*.

    Parameters
    ----------
    hardware_ids : str | list[str]
        Single Hardware‑ID string or a list of IDs.  Each is passed separately to
        UpdateDriverForPlugAndPlayDevicesW.

    inf_path : str
        Full path to the target driver’s .INF file (must already be accessible or
        pre‑staged).

    force_install : bool, default False
        If True the function sets INSTALLFLAG_FORCE so the specified INF will be
        applied even when Windows thinks a “better” driver is already installed.

    quiet : bool, default True
        If True the installation runs without UI (parent window = NULL).  Set
        False if you want progress dialogs.

    existing_ok : bool, default True
        When *False*, a return code of ERROR_NO_MORE_ITEMS (no devices found) or
        ERROR_DI_DO_DEFAULT (“already using this driver”) is treated as an error.

    Returns
    -------
    bool
        True  → Windows signalled that a reboot is required.
        False → No reboot required.

    =====================================================================

    Examples
    --------
    1. Force‑install the Microsoft KM‑Test Loopback driver that ships with
       Windows (the same scenario as the original hard‑coded function)::

         reboot_needed = update_driver_for_hwids(
             hardware_ids="*ROOT\\NET\\0000",
             inf_path=r"C:\\Windows\\INF\\netloop.inf",
             force_install=True
         )

    2. Install an Intel i219‑V NIC driver only if Windows agrees it is the best
       match (no force flag) for either of two possible PCI IDs::

         reboot_needed = update_driver_for_hwids(
             hardware_ids=[
                 "PCI\\VEN_8086&DEV_15B8",
                 "PCI\\VEN_8086&DEV_15BB"
             ],
             inf_path=r"D:\\Drivers\\PRO1000\\e1r.inf"
         )
    """
    # Normalise to a Python list for uniform processing
    ids: list[str] = [hardware_ids] if isinstance(hardware_ids, str) else list(hardware_ids)

    # Build the flag word sent to UpdateDriverForPlugAndPlayDevicesW
    flags = INSTALLFLAG_FORCE if force_install else 0
    if quiet:
        flags |= INSTALLFLAG_NONINTERACTIVE

    any_reboot = False                     # track whether *any* call needs reboot
    for hid in ids:
        reboot = wintypes.BOOL(False)
        ok = UpdateDriverForPlugAndPlayDevicesW(
            None,                          # hwndParent → silent (we add INSTALLFLAG_NONINTERACTIVE)
            hid,                           # first Hardware‑ID to match
            inf_path,                      # target driver INF
            flags,                         # INSTALLFLAG_* bitmask
            ctypes.byref(reboot)           # tells us if reboot required
        )
        if not ok:
            err = ctypes.get_last_error()
            # ERROR_NO_MORE_ITEMS (0xE000020B): no matching devices present
            # ERROR_DI_DO_DEFAULT  (0xE000020E): already using this driver
            benign = {0xE000020B, 0xE000020E}
            if not (existing_ok and err in benign):
                raise ctypes.WinError(err)
        any_reboot |= bool(reboot.value)

    return any_reboot


def add_device(
        class_guid: str,
        friendly_name: str,
        hardware_ids: "list[str] | str",
        inf_path: str,
        compatible_ids: "list[str] | str | None" = None,
        devdesc_override: str | None = None,
        create_flags: int = DICD_GENERATE_ID,
        existing_ok: bool = True,
        force_install: bool = False,
        quiet: bool = True
) -> None:
    """
    Create a root-enumerated device node and bind a driver to it.
    This is a wrapper around the two functions create_root_enumerated_devnode() and
    update_driver_for_hwids().

    This adds the device to the system and binds the driver to it.

    :param class_guid: string representation of a GUID.
        Device class GUID (e.g. GUID_DEVCLASS_NET, GUID_DEVCLASS_MEDIA …).
        Example:
            class_guid="{4d36e972-e325-11ce-bfc1-08002be10318}"
            This is the GUID for network adapters.
    :param friendly_name: str
        Initial instance name placed in the registry (DeviceDesc).
        Also, will be shown in Device Manager.
    :param hardware_ids: str | list[str]
        One or more hardware IDs (MULTI_SZ).  The *first* one is the key
        identifier PnP uses when selecting an INF.
    :param inf_path: str
        Full path to the target driver’s .INF file (must already be accessible or
        pre-staged).
    :param compatible_ids: str | list[str] | None
        Optional Compatible-ID list (another MULTI_SZ, lower priority).
    :param devdesc_override: str | None
        If supplied, written to SPDRP_DEVICEDESC (rarely necessary because
        the INF’s own DeviceDesc usually replaces it).
    :param create_flags: int
        Flags for SetupDiCreateDeviceInfoW.  Default is DICD_GENERATE_ID.
    :param existing_ok: bool
        If True, silently succeed when the devnode already exists.
    :param force_install: bool, default False
        If True the function sets INSTALLFLAG_FORCE so the specified INF will be
        applied even when Windows thinks a “better” driver is already installed.
    :param quiet: bool, default True
        If True the installation runs without UI (parent window = NULL).  Set
        False if you want progress dialogs.
    :return: None

    =====================================================================
    Examples
    --------



    """
    create_root_enumerated_devnode(
        class_guid=class_guid,
        friendly_name=friendly_name,
        hardware_ids=hardware_ids,
        compatible_ids=compatible_ids,
        devdesc_override=devdesc_override,
        create_flags=create_flags,
        existing_ok=existing_ok
    )

    update_driver_for_hwids(
        hardware_ids=hardware_ids,
        inf_path=inf_path,
        force_install=force_install,
        quiet=quiet,
        existing_ok=existing_ok
    )


def remove_device(
        pnp_device_id: str,
        class_guid: str
) -> bool:
    """
    Delete the single device whose PNPDeviceID
    equals the string you pass in (case-insensitive).  Returns True on
    success, False if no matching devnode was found.

    :param pnp_device_id: PNPDeviceID of the device to remove.
        If you're using the Win32_NetworkAdapter class, you can
        get the PNPDeviceID from the object itself: network_config.PNPDeviceID
    :param class_guid: string representation of the device class GUID.
        Example: '{4d36e972-e325-11ce-bfc1-08002be10318}' for network adapters.
    """

    class_guid_bytes = uuid.UUID(class_guid).bytes_le
    class_guid_object = (ctypes.c_byte * 16).from_buffer_copy(class_guid_bytes)

    # Get only PRESENT devices in the Network class
    hdi = SetupDiGetClassDevsW(class_guid_object, None, None, DIGCF_PRESENT)
    if hdi == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())

    devinfo   = SP_DEVINFO_DATA()
    devinfo.cbSize = ctypes.sizeof(devinfo)
    index     = 0
    removed   = False

    # Helper to fetch the instance-ID of the current element
    instance_buf_len = 512
    GetInstanceId = setupapi.SetupDiGetDeviceInstanceIdW
    GetInstanceId.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA),
        wintypes.LPWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
    ]
    GetInstanceId.restype = wintypes.BOOL
    inst_buf = ctypes.create_unicode_buffer(instance_buf_len)

    while SetupDiEnumDeviceInfo(hdi, index, ctypes.byref(devinfo)):
        index += 1

        if not GetInstanceId(hdi, ctypes.byref(devinfo),
                             inst_buf, instance_buf_len, None):
            continue

        if inst_buf.value.lower() != pnp_device_id.lower():
            continue  # not the target

        # Found it → remove
        if not SetupDiCallClassInstaller(DIF_REMOVE, hdi, ctypes.byref(devinfo)):
            err = ctypes.get_last_error()
            SetupDiDestroyDeviceInfoList(hdi)
            raise ctypes.WinError(err)

        removed = True
        break

    SetupDiDestroyDeviceInfoList(hdi)
    return removed