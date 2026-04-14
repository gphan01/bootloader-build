import argparse
import sys
import re
import configparser
import os
import subprocess
import glob

DEVICES = ['io', 'driver']


def main():
    # TODO 1: argparse setup
    #   - required: -d/--device (choices from DEVICES)
    #   - required: -v/--version
    #   - optional: -sb/--skip-build (action='store_true')

    # TODO 2: parse args

    # TODO 3: validate version (call parse_version, ignore return value)

    # TODO 4: load config

    # TODO 5: discover paths (pass config and args.device)

    # TODO 6: if not skip_build, call run_build and sys.exit(1) on failure

    # TODO 7: call discover_hex to populate paths['hex_path']

    # TODO 8: call package_firmware, sys.exit(1) if it returns None
    pass


def parse_version(version_str: str) -> tuple:
    """
    Parses the version argument passed to the script.
    Returns a tuple on success, on failure returns a 
    code 1 and exits. 
    """
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)\+(\d+)$', version_str)

    if match is None:
        print(f'ERROR (parse_version) - version format is invalid: {version_str}')
        sys.exit(1)
    
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    rc    = int(match.group(4))

    version_tuple = (major, minor, patch, rc)
    for value in version_tuple:
        if value < 0 or value > 255:
            print(f'ERROR (parse_version) - Version component out of range: {value}', file=sys.stderr)
            sys.exit(1)

    return version_tuple

def load_config() -> configparser.ConfigParser:
    """
    Loads the config file to be parsed and utilized
    throughout the script
    Returns the config object on success, else exits with code 1
    if config path is not found.
    """
    script_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_path, "config.ini")

    if os.path.exists(config_path) is False:
        print(f'ERROR (load_config) - Config path not found at {config_path}', file=sys.stderr)
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    return config



# Helper function to determine if the path to a file is valid
def _is_file(path : str) -> None:
    if not os.path.isfile(path):
        print(f'ERROR -  Path not found at {path}', file=sys.stderr)
        sys.exit(1)

def _is_dir(path : str) -> None:
    if not os.path.isdir(path):
        print(f'ERROR - Directory not found at {path}', file=sys.stderr)
        sys.exit(1)



def discover_paths(config: configparser.ConfigParser, device: str) -> dict:
    """
    Finds the attiny project directory for the given device, plus FwPkgUtility paths.
    Returns a dict with keys: script_path, project_path, fwpkgbuilder, results_path.
    """
    # TODO 1: get script_dir, store in paths['script_path']
    paths = {}

    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths['script_path'] = script_dir

    # TODO 2: loop through siblings of script_dir looking for the project.
    project_path = None

    entries = os.listdir(path=script_dir)
    for entry in entries:   
        entry_path = os.path.join(script_dir, entry)

        if not os.path.isdir(entry_path):
            continue
        if device not in entry.lower():
            continue
        if not os.path.isfile(os.path.join(entry_path, 'Makefile')):    
            continue 
        if not os.path.isdir(os.path.join(entry_path, 'nbproject')):   
            continue
        
        # All checks passed
        project_path = entry_path
        break

    paths['project_path'] = project_path   

    # TODO 3: if project_path was never set, error out
    if project_path is None:
        print(f'ERROR - No attiny project directory found for target: {device}', file=sys.stderr)
        sys.exit(1)
     
    # TODO 4: build FwPkgUtility paths
    #           - fwpkgbuilder at FwPkgUtility/data/FwPkgBuilder.exe (use _is_file)
    #           - results dir at FwPkgUtility/results (check isdir)
    
    utility_dir = os.path.join(script_dir, 'FwPkgUtility') 
    _is_dir(utility_dir)
    
    builder_path = os.path.join(utility_dir, 'data', 'FwPkgBuilder.exe')
    _is_file(builder_path)
    paths['builder_path']
    
    results_path = os.path.join(utility_dir, 'results')
    _is_dir(results_path)
    paths['results'] = results_path

    # TODO 5: return paths dict
    return paths


def run_build(config: configparser.ConfigParser, paths: dict) -> bool:
    """
    Runs `make CONF=offset` in the attiny project directory.
    Uses the make path from config.ini [ATTINY] make-path since make is not
    on PATH on the Windows work machines.
    Returns True on success, False on failure.
    """
    project_path = paths['project_path']

    make_path = config.get('ATTINY', 'make-path')

    _is_file(make_path)

    cmd = [
            make_path,
            'CONF=offset'
          ]

    result = subprocess.run(cmd, cwd=project_path)

    if result.returncode != 0:
        return False

    return True


def discover_hex(paths: dict) -> None:
    """
    Locates the .production.hex output from the offset build.
    Path pattern: <project>/dist/offset/production/*.production.hex
    Stores the match in paths['hex_path']. Expects exactly one match.
    """
    # TODO 1: build glob pattern

    # TODO 2: glob.glob it

    # TODO 3: branch on len(matches)
    #           - 1: store in paths['hex_path']
    #           - 0: error, exit
    #           - >1: error, exit (shouldn't happen with a clean build)
    pass


def package_firmware(paths: dict, device: str, input_path: str) -> str | None:
    """
    Hands the .hex to FwPkgBuilder. Verifies the .pkg exists on disk afterward
    (FwPkgBuilder has been observed to exit 0 without producing output).
    Returns the .pkg path on success, None on failure.
    """
    # TODO 1: build command: [fwpkgbuilder, input_path]

    # TODO 2: subprocess.run, return None on nonzero returncode

    # TODO 3: compute expected pkg path (splitext the input, append '.pkg')

    # TODO 4: verify pkg exists on disk, return None if not

    # TODO 5: return pkg_path
    pass


if __name__ == '__main__':
    main()