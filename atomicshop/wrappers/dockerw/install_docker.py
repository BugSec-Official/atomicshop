import sys
import os
import subprocess
import getpass
import tempfile
import textwrap
from pathlib import Path

from ... import process, filesystem
from ...permissions import permissions, ubuntu_permissions
from ...print_api import print_api
from .. import ubuntu_terminal


PREPARATION_OUTPUT_DIR: str = str(Path(__file__).parent / "offline-bundle")
PREPARATION_OUTPUT_ZIP: str = f"{PREPARATION_OUTPUT_DIR}.zip"
GET_DOCKER_URL: str = "https://get.docker.com"


def is_docker_installed():
    """
    The function will check if docker is installed.
    :return: bool.
    """

    try:
        # Run the command 'docker --version'
        result = subprocess.run(['docker', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Check if the command was successful
        if result.returncode == 0:
            message = f"Docker is installed. Version: {result.stdout.strip()}"
            print_api(message, color='green')
            return True
        else:
            print_api("Docker is not installed.")
            return False
    except FileNotFoundError:
        print_api("Docker command not found. Docker is not installed.")
        return False


def add_current_user_to_docker_group(print_kwargs: dict = None):
    """
    The function will add the current user to the docker group.

    :param print_kwargs: dict, the print arguments.
    :return:
    """
    # Check if current user that executed the script is a sudo user. If not, use the current user.
    sudo_executer_username: str = ubuntu_permissions.get_sudo_executer_username()
    if sudo_executer_username:
        current_user = sudo_executer_username
    else:
        current_user = getpass.getuser()

    # Add the current user to the docker group.
    # subprocess.check_call(['sudo', 'usermod', '-aG', 'docker', current_user])
    command = f"sudo usermod -aG docker {current_user}"
    # Execute the command
    subprocess.run(command, shell=True, capture_output=True, text=True)

    # Check if the user was added to the docker group.
    result = subprocess.run(['groups', current_user], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if 'docker' in result.stdout:
        print_api(f"User {current_user} was added to the docker group.", color='green', **(print_kwargs or {}))
        return True
    else:
        print_api(f"User {current_user} was not added to the docker group. Try executing with sudo", color='red',
                  **(print_kwargs or {}))
        return False


def install_docker_ubuntu(
        use_docker_installer: bool = True,
        rootless: bool = False,
        add_current_user_to_docker_group_bool: bool = False
) -> int:
    """
    The function will install docker on ubuntu.
    Note: If you want to install docker in rootless mode, you need to run the script without sudo.

    :param rootless: bool, if True, the rootless installation will be performed.
        Meaning, you will be able to run the 'docker' command without sudo and you will not need to add the
        current user to the docker group.
    :param use_docker_installer: bool, if True, the docker installer will be used.
        If False, the docker will be installed using the apt package manager, custom repo and keyring.
    :param add_current_user_to_docker_group_bool: bool, if True, the current user will be added to the docker group.
        So the user will be able to run the 'docker' command without sudo. If you install docker in rootless mode
        this is not needed.

    Usage in main.py (run with sudo):
        import sys
        from atomicshop.wrappers.dockerw import install_docker


        def main():
            execution_result: int = install_docker.install_docker_ubuntu()
            return execution_result


        if __name__ == '__main__':
            sys.exit(main())
    """

    if rootless and permissions.is_admin():
        print_api('Rootless installation requires running the script without sudo.', color='red')
        sys.exit()

    if use_docker_installer:
        if not ubuntu_terminal.is_executable_exists('curl'):
            print_api('curl is not installed, installing...', color='yellow')
            ubuntu_terminal.update_system_packages()
            ubuntu_terminal.install_packages(['curl'])

        # Use the docker installer script.
        # The script will install docker and add the current user to the docker group.
        # The script will also install docker-compose and docker-buildx.
        # process.execute_script('curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh', shell=True)
        process.execute_script('curl -fsSL https://get.docker.com | sh', shell=True)
        # subprocess.run("curl -fsSL https://get.docker.com | sh", shell=True, check=True)
        # process.execute_script('curl -fsSL https://get.docker.com -o get-docker.sh', shell=True)
        # process.execute_script('sh get-docker.sh', shell=True)
        # filesystem.remove_file('get-docker.sh')
    else:
        # Remove the existing keyrings, so we will not be asked to overwrite it if it exists.
        docker_keyring_file_path: str = "/etc/apt/keyrings/docker.gpg"
        filesystem.remove_file(docker_keyring_file_path)

        script = f"""
        # Step 1: Set up Docker's apt repository
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        
        # Add the repository to Apt sources
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update
        
        # Step 2: Install the Docker packages
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras
        
        # Step 3: Verify the installation
        # sudo docker run hello-world
        
        # Add Privileges to run docker without sudo. Add current user to Docker superuser group.
        # sudo usermod -aG docker $USER
        """

        process.execute_script(script, shell=True)

    if rootless:
        # Install uidmap package.
        if not ubuntu_terminal.is_package_installed('uidmap'):
            print_api('uidmap is not installed, installing...', color='yellow')
            ubuntu_terminal.update_system_packages()
            ubuntu_terminal.install_packages(['uidmap'])

        with ubuntu_permissions.temporary_regular_permissions():
            # After 'get-docker.sh' execution, we will install docker in rootless mode.
            # process.execute_script('dockerd-rootless-setuptool.sh install', shell=True, as_regular_user=True)
            process.execute_script(
                '/usr/bin/dockerd-rootless-setuptool.sh install',
                as_regular_user=True,
                shell=True,
                executable=None)

        # Start and enable the docker service in user mode.
        docker_start_command = ubuntu_terminal.get_command_execution_as_sudo_executer(
            'systemctl --user start docker.service')
        docker_enable_command = ubuntu_terminal.get_command_execution_as_sudo_executer(
            'systemctl --user enable docker.service')
        print_api('Starting and enabling the docker service in user mode...')
        process.execute_script(docker_start_command, shell=True, executable=None)
        process.execute_script(docker_enable_command, shell=True, executable=None)

        print_api('Executing "loginctl enable-linger" to enable Docker to run when the user is not logged in...')
        non_sudo_executer = ubuntu_permissions.get_sudo_executer_username()
        # Enable lingering so Docker runs when the user is not logged in
        process.execute_script(f'sudo loginctl enable-linger {non_sudo_executer}', shell=True)

        print_api('Adding $HOME/bin to your PATH...')
        # Add $HOME/bin to your PATH if it's not already there.
        with ubuntu_permissions.temporary_regular_permissions():
            ubuntu_terminal.add_path_to_bashrc(as_regular_user=True)

        # Add appropriate permissions to the docker socket, so the user can run docker commands without sudo in python.
        # with open('/etc/profile.d/docker_vars.sh', 'w') as file:
        #     file.write('export DOCKER_HOST=unix:///run/user/1000/docker.sock')

        # Since we are installing the rootless mode, this script runs without sudo, so to add the DOCKER_HOST variable
        # to the environment, we need to add it to the /etc/profile.d/docker_vars.sh file with sudo.
        command = "echo 'export DOCKER_HOST=unix:///run/user/1000/docker.sock' | sudo tee /etc/profile.d/docker_vars.sh"
        subprocess.run(command, shell=True, check=True)

        # ubuntu_terminal.add_line_to_bashrc(
        #     'export DOCKER_HOST=unix:///run/user/1000/docker.sock', as_regular_user=True)
        # process.execute_script('export DOCKER_HOST=unix:///run/user/1000/docker.sock', shell=True)
        # Restart shell.
        # process.execute_script('source ~/.bashrc', shell=True)

    if add_current_user_to_docker_group_bool:
        # Check if current user that executed the script is a sudo user. If not, use the current user.
        # Add the current user to the docker group.
        add_current_user_to_docker_group()

        # Verify the installation.
        result: list = process.execute_with_live_output('sudo docker run hello-world')
    else:
        result: list = process.execute_with_live_output('docker run hello-world')

    print_api('\n'.join(result))

    if 'Hello from Docker!' in '\n'.join(result):
        print_api('Docker installed successfully.', color='green')
        return 0
    else:
        print_api('Docker installation failed.', color='red')
        print_api('Please check the logs above for more information.', color='red')
        return 1


def prepare_offline_installation_bundle():
    # The Bash script in a single triple-quoted string - this is to easier copy-paste it if needed to run directly.
    bash_script = textwrap.dedent(r"""#!/usr/bin/env bash
#
# Build an offline-install bundle for Docker Engine on Ubuntu 24.04 LTS.
# The package list is auto-discovered from `get.docker.com --dry-run`.
#
#   sudo ./prepare_docker_offline.sh  [/path/to/output_dir]
#
set -Eeuo pipefail

################################################################################
# CLI PARAMETERS
#   $1  → OUTDIR           (already supported: where to build the bundle)
#   $2  → GET_DOCKER_URL   (defaults to https://get.docker.com)
#   $3  → OUTPUT_ZIP       (defaults to "$OUTDIR.zip")
################################################################################
OUTDIR="${1:-"$PWD/offline-bundle"}"
GET_DOCKER_URL="${2:-https://get.docker.com}"
OUTPUT_ZIP="${3:-$OUTDIR.zip}"

die()       { echo "ERROR: $*" >&2; exit 1; }
need_root() { [[ $EUID -eq 0 ]] || die "Run as root (use sudo)"; }
need_cmd() {
  local cmd=$1
  local pkg=${2:-$1}               # default package == command
  if ! command -v "$cmd" &>/dev/null; then
    echo "[*] $cmd not found – installing $pkg ..."
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive \
      apt-get install -y --no-install-recommends "$pkg" || \
      die "Unable to install required package: $pkg"
  fi
}

need_root
need_cmd curl

echo "[*] Discovering package list via get.docker.com --dry-run ..."
DRY_LOG=$(curl -fsSL "$GET_DOCKER_URL" | bash -s -- --dry-run)

echo "[*] Determining package list via --dry-run ..."
PKGS=$(printf '%s\n' "$DRY_LOG" | sed -n 's/.* install \(.*\) >\/dev\/null.*/\1/p')

if ! grep -q '\S' <<< "$PKGS"; then
  echo "No packages detected in dry-run output – aborting." >&2
  exit 1
fi

echo "[*] Install Docker before preparing the offline bundle."
curl -fsSL "$GET_DOCKER_URL" | sh

mkdir -p "$OUTDIR"/packages
echo "[*] Output directory: $OUTDIR"

echo "Packages to install:"
echo "$PKGS"

echo "[*] Downloading packages and all dependencies …"
apt-get update -qq
apt-get clean
mkdir -p /var/cache/apt/archives/partial
apt-get -y --download-only --reinstall install $PKGS
cp -v /var/cache/apt/archives/*.deb "$OUTDIR/packages/"
echo "[*] $(ls "$OUTDIR/packages" | wc -l) .deb files written to packages/"

echo "[*] Building local Packages.gz index …"
pushd "$OUTDIR/packages" >/dev/null
for deb in *.deb; do
  dpkg-deb -f "$deb" Package
done | awk '{printf "%s\tmisc\toptional\n",$1}' > override
apt-ftparchive packages . override | tee Packages | gzip -9c > Packages.gz
popd >/dev/null


echo ">> Checking for Docker ..."
command -v docker >/dev/null 2>&1 || { echo "Docker not found."; exit 1; }

# Pack final bundle
echo "[*] Creating a zip archive ..."
parent_dir=$(dirname  "$OUTDIR")
base_name=$(basename "$OUTDIR")

# Create new shell, cd into the directory, and zip the contents. So that the zip file will not contain the full path.
(
  cd "$parent_dir"
  zip -rq "$OUTPUT_ZIP" "$base_name"
)

rm -rf "$OUTDIR"
echo "Docker offline bundle created at $OUTPUT_ZIP"
echo
echo "Copy the zip file and the offline installation python script to the target machine and execute."
    """)

    # Write it to a secure temporary file.
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.sh') as f:
        f.write(bash_script)
        temp_path = f.name
    os.chmod(temp_path, 0o755)  # make it executable

    cmd = [
        "sudo", "bash", temp_path,
        PREPARATION_OUTPUT_DIR,
        GET_DOCKER_URL,
        PREPARATION_OUTPUT_ZIP,
    ]

    # Run it and stream output live.
    try:
        subprocess.run(cmd, check=True)
    finally:
        # 5. Clean up the temp file unless you want to inspect it.
        os.remove(temp_path)


def install_offline_installation_bundle():
    bash_script = textwrap.dedent(r"""#!/usr/bin/env bash
# Offline installer for the Docker bundle produced by prepare_docker_offline.sh
set -euo pipefail

die()       { echo "ERROR: $*" >&2; exit 1; }
need_root() { [[ $EUID -eq 0 ]] || die "Run as root (use sudo)"; }

need_root

# ------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------
BUNDLE_ZIP="${1:-"$PWD/offline-bundle.zip"}"

BUNDLE_DIR="${BUNDLE_ZIP%.zip}"  # remove .zip suffix
REPO_DIR="$BUNDLE_DIR/packages"                        # contains *.deb + Packages
OFFLINE_LIST="/etc/apt/sources.list.d/docker-offline.list"

# Extract zip archive if it exists
if [[ -f "$BUNDLE_ZIP" ]]; then
  echo "[*] Extracting offline bundle from $BUNDLE_ZIP ..."
  mkdir -p "$BUNDLE_DIR"
  unzip -q "$BUNDLE_ZIP" -d "."
else
  die "Bundle zip file '$BUNDLE_ZIP' not found. Provide a valid path."
fi

TEMP_PARTS="$(mktemp -d)"                              # empty dir ⇒ no extra lists

# ------------------------------------------------------------------------------
# Helper to clean up even if the script aborts
# ------------------------------------------------------------------------------
cleanup() {
  sudo rm -f "$OFFLINE_LIST"
  sudo rm -rf "$TEMP_PARTS"
}
trap cleanup EXIT

# ------------------------------------------------------------------------------
# 1. Add the local repository (trusted) as the *only* source we will use
# ------------------------------------------------------------------------------
echo "[*] Adding temporary APT source for the offline bundle …"
echo "deb [trusted=yes] file:$REPO_DIR ./" | sudo tee "$OFFLINE_LIST" >/dev/null

# Ensure plain index exists (APT always understands the un-compressed form)
if [[ ! -f "$REPO_DIR/Packages" && -f "$REPO_DIR/Packages.gz" ]]; then
    gunzip -c "$REPO_DIR/Packages.gz" > "$REPO_DIR/Packages"
fi

# ------------------------------------------------------------------------------
# 2. Update metadata – but ONLY from our offline list
# ------------------------------------------------------------------------------
echo "[*] Updating APT metadata – offline only …"
sudo apt-get -o Dir::Etc::sourcelist="$OFFLINE_LIST" \
             -o Dir::Etc::sourceparts="$TEMP_PARTS" \
             -o APT::Get::List-Cleanup="0" \
             update -qq

# ------------------------------------------------------------------------------
# 3. Figure out which packages are inside the bundle
# ------------------------------------------------------------------------------
PKGS=$(awk '/^Package: /{print $2}' "$REPO_DIR/Packages")

echo "[*] Installing:"
printf '    • %s\n' $PKGS

# ------------------------------------------------------------------------------
# 4. Install them, again restricting APT to the offline repo only
# ------------------------------------------------------------------------------
sudo apt-get -y \
     -o Dir::Etc::sourcelist="$OFFLINE_LIST" \
     -o Dir::Etc::sourceparts="$TEMP_PARTS" \
     install $PKGS

echo "[✓] Docker installed completely offline!"

usage() {
  echo "Usage: $0 <image-archive.tar.gz>"
  exit 1
}

echo ">> Checking for Docker ..."
command -v docker >/dev/null 2>&1 || {
  echo "Docker is not installed; install Docker and try again."
  exit 1
}

echo "Removing extracted files..."
rm -rf "$BUNDLE_DIR"
    """)

    # Write it to a secure temporary file.
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.sh') as f:
        f.write(bash_script)
        temp_path = f.name
    os.chmod(temp_path, 0o755)  # make it executable

    cmd = [
        "sudo", "bash", temp_path,
        PREPARATION_OUTPUT_ZIP,  # $1  BUNDLE_ZIP
    ]

    # 4. Run it and stream output live.
    try:
        subprocess.run(cmd, check=True)
    finally:
        # 5. Clean up the temp file unless you want to inspect it.
        os.remove(temp_path)