import argparse
import sys
import re
import configparser
import os
import subprocess
import glob

DEVICE_EXTENSIONS = {'main'  : '.bin',
                     'tuner' : '.bin',
                     'io'    : '.hex',
                     'driver': '.hex'
                    }
          
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

    discover_eoc(device=args.device, paths=paths)

    signed_path = sign_firmware(config=config, paths=paths, device=args.device, version_str=args.version)
    if signed_path == None:
        print('Error: signing process failed', file=sys.stderr)
        sys.exit(1) 

    print(f'DEBUG: Signed firmare at {signed_path}\n')
    
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

"""
    Finds the EOC for the respective device.
    Note: EOC = Executable Object Code
"""
def discover_eoc(device : str, paths : dict) -> None:
     
    device_extension = DEVICE_EXTENSIONS[device]

    project_path = paths['project_path']
    debug_path = os.path.join(project_path, 'Debug')
    pattern = os.path.join(debug_path, f'*{device_extension}')

    matches = glob.glob(pattern)

    if len(matches) == 1:
        paths['eoc_path'] = matches[0]
    elif len(matches) == 0:
        print(f'Error: no {device_extension} file found at {debug_path}', file=sys.stderr)
        sys.exit(1)
    else:
        print(f'Error: multiple {device_extension} files found at {debug_path}', file=sys.stderr)
        sys.exit(1)

def sign_firmware(config: configparser.ConfigParser, paths: dict, device: str, version_str: str) -> str | None:
    """
    Signs .bin firmware with imgtool (signing + optional encryption).
    For .hex devices, skips signing and returns the original file path.
    Returns the output path on success, None on failure.
    """
    input_path = paths['eoc_path']
    # TODO 1: Determine device type (.bin vs .hex)
    #         - main/tuner -> .bin -> sign with imgtool
    #         - driver/io  -> .hex -> skip signing, return input path unchanged
    if DEVICE_EXTENSIONS.get(device) != '.bin':
        return input_path 

    # TODO 2: Pull bootloader config values
    header_size = config.get('BOOTLOADER', 'header-size')
    slot_size = config.get('BOOTLOADER', 'slot-size')
    align = config.get('BOOTLOADER', 'align')
    pad_header = config.getboolean('BOOTLOADER', 'pad-header')


    # TODO 3: Pull signing config values
    #         - encryption-enabled (bool, use config.getboolean)
    encryption_enabled = config.getboolean('SIGNING', 'encryption-enabled')


    # TODO 4: Build output path
    #         - Filename convention: {device}_fw{version_str}.tmp
    #         - Place it in paths['results_path']
    #         - Use os.path.join() to build the full path
    output_file_name = f'{device}_fw{version_str}.tmp'
    output_path = os.path.join(paths['results_path'], output_file_name)

    # TODO 5: Build the imgtool command as a list of strings
    #         - Start with required flags: imgtool path, 'sign', --key, --align, --header-size, --slot-size, --version
    #         - Required positional args at the end: input path, output path
    img_tool_path = paths['imgtool']
    cmd = [
                img_tool_path,
                'sign', 
                '--key', paths['sign_path'],
                '--align', align,
                '--header-size', header_size,
                '--slot-size', slot_size,
                '--version', version_str,
              ]
    
    # TODO 6: Conditionally append --pad-header if pad-header is True
    if pad_header:
        cmd.append('--pad-header')

        
    # TODO 7: Conditionally append --encrypt <enc_path> if encryption is enabled
    if encryption_enabled:
        enc_path = paths['enc_path']
        cmd.extend(['--encrypt', enc_path])
    
    cmd.append(input_path)
    cmd.append(output_path)

    # TODO 8: Run the command with subprocess.run()
    #         - Print the command for debugging: print(f'DEBUG: cmd = {cmd}')
    #         - Check result.returncode
    print(f'DEBUG: command - {cmd}')
    result = subprocess.run(cmd)

    if result.returncode != 0:
        return None
    
    # TODO 9: Return the output path on success, None on failure
    return output_path

if __name__ == "__main__":
  main() 
  


















