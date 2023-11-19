import subprocess


def is_enabled():
    try:
        # Command to get CPU virtualization extension availability
        command = "wmic cpu get VirtualizationFirmwareEnabled"
        result = subprocess.run(command, capture_output=True, text=True, shell=True)

        if "TRUE" in result.stdout:
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e.stderr}")
        return False
