import argparse
import sys
import re
import configparser
import os

def main():
    parser = argparse.ArgumentParser(description="Firmware build and packaging pipeline")

    # TODO add --device
    parser.add_argument('-d', '--device')
    # TODO add --version
    parser.add_argument('-v', '--version');
    # TODO add --skip-build (optional)'
    parser.add_argument('-sb', '--skip-build', action='store_true')
    # TODO add --no-cleanup (optional)
    parser.add_argument('-nc', '--no-cleanup', action='store_true')

  
    args = parser.parse_args()

    parse_version(args.version)

    load_config();

    # print(f"Device:     {args.device}")
    # print(f"Version:    {args.version}")
    # print(f"Skip build: {args.skip_build}")
    # print(f"No cleanup: {args.no_cleanup}")

# TODO parse_version(version) 0.20.1+1
def parse_version(version_str: str) -> tuple:
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)\+(\d+)$', version_str)

    # The version format is invalid.
    if match is None:
        print(f'Version format is invalid: {version_str}')
        sys.exit(1);
    
    major = match.group(1)
    minor = match.group(2)
    patch = match.group(3)
    rc    = match.group(4)

    version_tuple = (major, minor, patch, rc)

    print(f'Tuple: {version_tuple}')
    return version_tuple

# TODO read and load the configuration file 
"""
Sections:
    [BOOTLODER]
        header-size = 0x0000
        slot-size = 0x0000
        pad-header = true
        align = 4

    [ENCRYPTION]
        encryption-enabled = true
        key-pair-name = "

    [MCUXPRESSO]
        headless-path = ""
        workspace-path = ""

"""
def load_config() -> configparser.ConfigParser:
    # Read the path of the script
    script_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_path, "config.ini")

    if os.path.exists(config_path) is False:
        print('Config path not found.')
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    return config

def discover_paths() -> dict:
    path_dict = {}
    # 1. Script discovery
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path_dict["script_path"] = script_dir

    # 2. Firmware project directory - find script_dir for subdirectories containing a .cproject file (os.listdir() and os.path.isfile())
    entries = os.listdir(path=script_dir)
    for entry in entries:
        entry_path = os.path.join(script_dir, entry);
        if os.path.isdir(entry_path):
            cproject_path = os.path.join(script_dir, '.cproject')

            if os.path.isfile(cproject_path):
                # .cproject found in MCUXpresso project directory
                path_dict["project_path"] = cproject_path              
                break;
    
    # 3 Tool paths = imgtool.exe and FwPkgBuidler.exe under FwPkgUtility/data/

    # 4 Key paths - sign_v2_pem and enc_v2.pem udner FwPkgUtility/keys/v2

    # Results directory - FwPkgUtility/results

    return path_dict

if __name__ == "__main__":
  main();