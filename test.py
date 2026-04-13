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
    # Copy from RT1064 script — identical logic.
    pass


def load_config() -> configparser.ConfigParser:
    # Copy from RT1064 script — identical logic.
    pass


def _is_file(path: str) -> None:
    # Copy from RT1064 script — identical logic.
    pass


def discover_paths(config: configparser.ConfigParser, device: str) -> dict:
    """
    Finds the attiny project directory for the given device, plus FwPkgUtility paths.
    Returns a dict with keys: script_path, project_path, fwpkgbuilder, results_path.
    """
    # TODO 1: get script_dir, store in paths['script_path']

    # TODO 2: loop through siblings of script_dir looking for the project.
    #         Filter chain (each continue rejects the candidate):
    #           - not a directory → skip
    #           - device string not in entry.lower() → skip
    #           - no Makefile in entry → skip
    #           - no nbproject/ dir in entry → skip
    #         If all checks pass: record project_path and break.

    # TODO 3: if project_path was never set, error out

    # TODO 4: build FwPkgUtility paths
    #           - fwpkgbuilder at FwPkgUtility/data/FwPkgBuilder.exe (use _is_file)
    #           - results dir at FwPkgUtility/results (check isdir)

    # TODO 5: return paths dict
    pass


def run_build(config: configparser.ConfigParser, paths: dict) -> bool:
    """
    Runs `make CONF=offset` in the attiny project directory.
    Uses the make path from config.ini [ATTINY] make-path since make is not
    on PATH on the Windows work machines.
    Returns True on success, False on failure.
    """
    # TODO 1: get make-path from config, verify with _is_file

    # TODO 2: build command list: [make_path, 'CONF=offset']

    # TODO 3: subprocess.run with cwd=project_path

    # TODO 4: return True if returncode == 0, else False
    pass


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
