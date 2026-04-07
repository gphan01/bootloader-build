import argparse
import sys
import re
import configparser
import os
import subprocess
import glob

def main():
    parser = argparse.ArgumentParser(description="Firmware build and packaging pipeline")

    parser.add_argument('-d', '--device', required = True, choices=['main', 'tuner', 'io', 'driver'])
    parser.add_argument('-v', '--version', required = True)
    parser.add_argument('-sb', '--skip-build', required = False, action='store_true')
    parser.add_argument('-nc', '--no-cleanup', required = False, action='store_true')
 
    args = parser.parse_args()

    version = parse_version(args.version)

    print(f'DEBUG: Version Type: {type(version)} Version: v{version[0]}.{version[1]}.{version[2]}+{version[3]}\n')

    config = load_config()

    paths = discover_paths(config)

    if not args.skip_build:
        if not run_build(config, paths):
            sys.exit(1)

    discover_firmware(config=config, device=args.device, paths=paths)
    print(f'DEBUG: {paths}\n')


# TODO parse_version(version) 0.20.1+1
def parse_version(version_str: str) -> tuple:
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)\+(\d+)$', version_str)

    # The version format is invalid.
    if match is None:
        print(f'Version format is invalid: {version_str}')
        sys.exit(1)
    
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    rc    = int(match.group(4))

    version_tuple = (major, minor, patch, rc)
    for value in version_tuple:
        if value < 0 or value > 255:
            print(f'Error: version component out of range: {value}', file=sys.stderr)
            sys.exit(1)

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

# Helper function to determine if the path to a file is valid
def _is_file(path : str) -> None:
    if not os.path.isfile(path):
        print(f'Error: path not found at {path}', file=sys.stderr)
        sys.exit(1)

def discover_paths(config : configparser.ConfigParser) -> dict:
    paths = {}
    # 1. Script discovery
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths["script_path"] = script_dir

    # FwPkgUtility Directory
    utility_dir = os.path.join(script_dir, 'FwPkgUtility')

    # 2. Firmware project directory - find script_dir for subdirectories containing a .cproject file (os.listdir() and os.path.isfile())
    entries = os.listdir(path=script_dir)
    for entry in entries:
        entry_path = os.path.join(script_dir, entry);
        if os.path.isdir(entry_path):
            cproject_path = os.path.join(entry_path, '.cproject')

            if os.path.isfile(cproject_path):
                # .cproject found in MCUXpresso project directory
                paths['project_path'] = entry_path
                paths['cproject_path'] = cproject_path              
                break

    if 'project_path' not in paths:
        print(f'Error: no .cproject found', file=sys.stderr)
        sys.exit(1)
    
    # 3. Tool paths = imgtool.exe and FwPkgBuidler.exe under FwPkgUtility/data/
    imgtool_path = os.path.join(utility_dir, 'data', 'imgtool.exe')
    _is_file(imgtool_path)

    paths['imgtool'] = imgtool_path

    fwpkgbuilder_path = os.path.join(utility_dir, 'data', 'FwPkgBuilder.exe')
    _is_file(fwpkgbuilder_path)

    paths['fwpkgbuilder'] = fwpkgbuilder_path

    # 4. Key paths - sign_v2.pem and enc_v2.pem under FwPkgUtility/keys/v2
    key_pair_name = config.get('SIGNING', 'key-pair-name')
    sign_path = os.path.join(utility_dir, 'keys', key_pair_name, f'sign_{key_pair_name}.pem')
    _is_file(sign_path)


    paths['sign_path'] = sign_path

    enc_path = os.path.join(utility_dir, 'keys', key_pair_name, f'enc_{key_pair_name}.pem')
    _is_file(enc_path)

    paths['enc_path'] = enc_path

    # 5. Results directory - FwPkgUtility/results
    results_path = os.path.join(utility_dir, 'results')
    print(results_path)
    if not os.path.isdir(results_path):
        print(f'Error: path not found at {results_path}', file=sys.stderr)
        sys.exit(1)

    paths['results_path'] = results_path

    return paths

def run_build(config : configparser.ConfigParser, paths) -> bool:
    # 2, MCUXpresso Section 
    ide_path = config.get('MCUXPRESSO', 'ide-path')
    workspace_path = config.get('MCUXPRESSO', 'workspace-path')
    project_name = config.get('MCUXPRESSO', 'project-name')

    script_path = paths['script_path']
    
    # 3. Run arguments
    command = [ide_path, '-nosplash', '--launcher.suppressErrors', '-application', 
                 'org.eclipse.cdt.managedbuilder.core.headlessbuild', 
                 '-data', workspace_path, '-importAll', script_path,'-cleanBuild', f'{project_name}/Debug' ]
    
    # 4. run command with with subprocess.run
    result = subprocess.run(command)
    print(f'DEBUG: {result.returncode}')

    if result.returncode != 0:
        return False
    
    return True

# Write a discover_firmware() function that:
	#1.	Takes device (string) and paths (dict) as parameters
def discover_firmware(config : configparser.ConfigParser, device : str, paths : dict) -> None:
      
	#2.	Determines the expected extension based on device: 	main or tuner -> .bin
	# driver, io, or sense -> .hex
    extensions = {'main'  : '.bin',
           'tuner' : '.bin',
           'io'    : '.hex',
           'driver': '.hex'
            }
    
    device_extension = f'{extensions[device]}'
    project_name = config.get('MCUXPRESSO', 'project-name')

    project_path = paths['project_path']
    #3.	Looks in paths['project_path']/Debug/ for files matching that extension 
    debug_path = os.path.join(project_path, 'Debug')
    eoc_path = os.path.join(debug_path, f'{project_name}{device_extension}')

    eoc = glob.glob(eoc_path)

    if len(eoc) == 1:
          paths['bin_path'] = eoc_path
    else:
        print(f'Error: multiple EOCs or none found')
        sys.exit(1)

if __name__ == "__main__":
  main();