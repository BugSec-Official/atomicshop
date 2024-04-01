import sys

from ...print_api import print_api
from ... import process, permissions
from .. import ubuntu_terminal
from . import config_basic, infrastructure


def install_elastic_kibana_ubuntu(install_elastic: bool = True, install_kibana: bool = True):
    """
    The function will install docker on ubuntu.

    :param install_elastic: bool, if True, install Elasticsearch.
    :param install_kibana: bool, if True, install Kibana.

    Usage in main.py (run with sudo):
        from atomicshop.wrappers.elasticw import install_elastic


        def main():
            install_elastic.install_elastic_ubuntu()


        if __name__ == '__main__':
            main()
    """

    # This is pure bash script.
    """
    #!/bin/bash

    # Color text in red.
    echo_red() {
        local color="\e[31m"  # Red color
        local reset="\e[0m"   # Reset formatting
        echo -e "${color}$1${reset}"
    }
    
    # Function to check if a service is running
    check_service_running() {
        local service_name=$1
        local status=$(systemctl is-active "$service_name")
    
        if [ "$status" == "active" ]; then
            echo "$service_name service is active and running."
            return 0
        else
            echo_red "$service_name service is not running or has failed. Status: $service_status, Failed: $service_failed"
            return 1
        fi
    }
    
    # Update and upgrade system packages
    sudo apt-get update && sudo apt-get upgrade -y
    
    # Install necessary dependencies
    sudo apt-get install apt-transport-https openjdk-11-jdk wget -y
    
    # Download and install the GPG signing key
    wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | gpg --dearmor | sudo tee /usr/share/keyrings/elasticsearch-keyring.gpg > /dev/null
    
    # Add the Elastic repository to the system
    echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" | sudo tee /etc/apt/sources.list.d/elastic-8.x.list
    
    # Update package index
    sudo apt-get update
    
    # Install Elasticsearch
    sudo apt-get install elasticsearch -y
    
    # Path to the Elasticsearch configuration file
    CONFIG_FILE="/etc/elasticsearch/elasticsearch.yml"
    
    # Check if the configuration file exists
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Configuration file does not exist at $CONFIG_FILE."
        exit 1
    fi
    
    # Function to check the setting in the configuration file
    check_setting() {
        if grep -q "^xpack.security.enabled: false" "$CONFIG_FILE"; then
            echo "The setting is confirmed to be 'xpack.security.enabled: false'."
        else
            echo "Failed to set 'xpack.security.enabled: false'."
            exit 1
        fi
    }
    
    # Check if 'xpack.security.enabled' is set to 'false'
    if grep -q "^xpack.security.enabled: false" "$CONFIG_FILE"; then
        echo "The setting is already set to false."
    elif grep -q "^xpack.security.enabled: true" "$CONFIG_FILE"; then
        # If the setting is true, change it to false
        sudo sed -i 's/^xpack.security.enabled: true/xpack.security.enabled: false/' "$CONFIG_FILE"
        echo "Changed xpack.security.enabled to false."
        check_setting
    else
        # If the setting doesn't exist, add it
        echo "xpack.security.enabled: false" | sudo tee -a "$CONFIG_FILE" > /dev/null
        echo "Added xpack.security.enabled: false to the configuration."
        check_setting
    fi
    
    # Start and enable Elasticsearch service
    sudo systemctl start elasticsearch
    sudo systemctl enable elasticsearch
    
    echo "Waiting 30 seconds for program to start before availability check..."
    sleep 30
    
    # Check if Elasticsearch service is running
    if ! check_service_running "elasticsearch"; then
        echo "Elasticsearch service failed to start. Exiting."
        exit 1
    fi
    
    # Function to check if Elasticsearch is up and running
    check_elasticsearch() {
        max_attempts=5
        wait_seconds=10
    
        for ((i=1; i<=max_attempts; i++)); do
            echo "Checking if Elasticsearch is running (Attempt $i/$max_attempts)..."
    
            # Using curl to get the HTTP status code
            status=$(curl --write-out %{http_code} --silent --output /dev/null http://localhost:9200)
    
            if [ "$status" -eq 200 ]; then
                echo "Elasticsearch is up and running."
                return 0
            else
                echo "Elasticsearch is not running. Status code: $status"
            fi
    
            echo "Waiting for Elasticsearch to start..."
            sleep $wait_seconds
        done
    
        echo "Elasticsearch did not start within the expected time."
        return 1
    }
    
    # Check if Elasticsearch is running
    if ! check_elasticsearch; then
        echo "Elasticsearch failed to start. Exiting."
        exit 1
    fi
    
    # Install Kibana
    sudo apt-get install kibana -y
    
    # Start and enable Kibana service
    sudo systemctl start kibana
    sudo systemctl enable kibana
    
    echo "Waiting 30 seconds for program to start before availability check..."
    sleep 30
    
    # Check if Kibana service is running
    if ! check_service_running "kibana"; then
        echo "Kibana service failed to start. Exiting."
        exit 1
    fi
    
    # Print status
    echo "Elasticsearch and Kibana installation completed."
    echo "Elasticsearch is running on http://localhost:9200"
    echo "Kibana is running on http://localhost:5601"
    """

    if not install_elastic and not install_kibana:
        raise ValueError("At least one of the services (Elasticsearch or Kibana) must be installed.")

    # Update and upgrade system packages.
    ubuntu_terminal.upgrade_system_packages()
    ubuntu_terminal.update_system_packages()

    # Install necessary dependencies.
    ubuntu_terminal.install_packages(config_basic.UBUNTU_DEPENDENCY_PACKAGES)

    # Install the GPG key and add elastic repository.
    script = f"""
    # Download and install the GPG signing key
    wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | gpg --dearmor | sudo tee /usr/share/keyrings/elasticsearch-keyring.gpg > /dev/null
    
    # Add the Elastic repository to the system
    echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" | sudo tee /etc/apt/sources.list.d/elastic-8.x.list
    """
    process.execute_script(script, shell=True)

    # Update system with elastic search packages.
    ubuntu_terminal.update_system_packages()

    if install_elastic:
        # Install Elasticsearch.
        ubuntu_terminal.install_packages([config_basic.UBUNTU_ELASTIC_PACKAGE_NAME])

        if not permissions.is_admin():
            print_api("This script requires root privileges...", color='red')
            sys.exit(1)

        # Check if the configuration file exists.
        infrastructure.is_elastic_config_file_exists(exit_on_error=True, output_message=True)

        # Check if the specific setting exists or not and set it to false.
        infrastructure.modify_xpack_security_setting(setting=False, output_message=True)

        # Check if the setting was really set to false.
        if infrastructure.check_xpack_security_setting() is False:
            print_api(f"The setting is confirmed to be [{config_basic.XPACK_SECURITY_SETTING_NAME}: false].")
        else:
            print_api(f"Failed to set [{config_basic.XPACK_SECURITY_SETTING_NAME}: false].")
            sys.exit(1)

        infrastructure.start_elastic_and_check_service_availability()

    if install_kibana:
        # Install Kibana.
        ubuntu_terminal.install_packages([config_basic.UBUNTU_KIBANA_PACKAGE_NAME])

        # Start and enable Kibana service.
        infrastructure.start_kibana_and_check_service_availability()

    print_api("Installation completed.", color='green')
    if install_elastic:
        print_api(f"Default Elasticsearch on {config_basic.DEFAULT_ELASTIC_URL}")
    if install_kibana:
        print_api(f"Default Kibana on {config_basic.DEFAULT_KIBANA_URL}")
