import os.path
import sys
import argparse

from atomicshop.file_io import tomls


def parse_args():
    parser = argparse.ArgumentParser(
        description='Update the config.toml file.\n'
                    'This script will update the current config.toml file with the keys from the target config.toml file.\n'
                    'If the key is not present in the current config.toml file, it will be added.\n'
                    'If the key is present in the current config.toml file, its value will be left unchanged.\n')
    parser.add_argument('current_config_file', type=str, help="Path to the current config.toml file that will be updated.")
    parser.add_argument('target_config_file', type=str, help="Path to the target config.toml file that we'll get the updates from.")
    parser.add_argument('-n', '--new_file_path', type=str, help="(OPTIONAL) Path to the new config.toml file that will be created with the updates.", default=None)
    return parser.parse_args()


def main():
    args = parse_args()

    if os.path.isfile(args.current_config_file) is False:
        print(f"Error: The current config file '{args.current_config_file}' does not exist.")
        return 1
    if os.path.isfile(args.target_config_file) is False:
        print(f"Error: The target config file '{args.target_config_file}' does not exist.")
        return 1

    tomls.update_toml_file_with_new_config(
        main_config_file_path=args.current_config_file,
        changes_config_file_path=args.target_config_file,
        new_config_file_path=args.new_file_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())