import argparse
import subprocess
import sys


WHEEL = (
    "https://github.com/fireeye/pywintrace/releases/download/"
    "v0.3.0/pywintrace-0.3.0-py3-none-any.whl"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pywintrace",
        description="Utility wrapper for installing FireEye’s pywintrace wheel"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("install", help="Download and install pywintrace v0.3.0")
    args = parser.parse_args()

    if args.command == "install":
        subprocess.check_call([sys.executable, "-m", "pip", "install", WHEEL])
        print("pywintrace 0.3.0 installed")

if __name__ == "__main__":
    main()
