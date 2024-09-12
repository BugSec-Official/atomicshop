import subprocess


def install_playwright():
    subprocess.run(["playwright", "install"])
