import os
import winreg


def get_installed_software() -> list[dict]:
    registry_path: str = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    data: list[dict] = []

    # Open the specified registry path
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as reg_key:
        i = 0
        while True:
            try:
                # Enumerate all sub-keys
                subkey_name = winreg.EnumKey(reg_key, i)
                subkey_path = os.path.join(registry_path, subkey_name)
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path) as subkey:
                    try:
                        # Fetch DisplayName and DisplayVersion if they exist
                        display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                    except FileNotFoundError:
                        display_name = "N/A"

                    try:
                        display_version, _ = winreg.QueryValueEx(subkey, "DisplayVersion")
                    except FileNotFoundError:
                        display_version = "N/A"

                    try:
                        install_date, _ = winreg.QueryValueEx(subkey, "InstallDate")
                    except FileNotFoundError:
                        install_date = "N/A"

                    try:
                        install_location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                    except FileNotFoundError:
                        install_location = "N/A"

                    try:
                        install_source, _ = winreg.QueryValueEx(subkey, "InstallSource")
                    except FileNotFoundError:
                        install_source = "N/A"

                    if display_name != "N/A":
                        data.append({
                            "DisplayName": display_name,
                            "DisplayVersion": display_version,
                            "InstallDate": install_date,
                            "SubkeyName": subkey_name,
                            "InstallLocation": install_location,
                            "InstallSource": install_source
                        })
            except OSError:
                break  # No more subkeys

            i += 1

    return data