import argparse
import sys
import re
import configparser
import os
import subprocess
import glob

DEVICES = ["io", "driver"]


def main():
    parser = argparse.ArgumentParser(description='Firmware build and packaging pipeline for ATtiny MCUs')
    parser.add_argument('-t', '--target', required=True, choices=DEVICES)
    parser.add_argument('-v', '--version', required=True)
    parser.add_argument('-sb', '--skip-build', action='store_true')

    args = parser.parse_args()

    parse_version(args.version)
    config = load_config()
    paths = discover_paths(config, target=args.target)

    if not args.skip_build:
        if not run_build(config, paths):
            sys.exit(1)

    discover_hex(paths)

    pkg_path = package_firmware(
        paths=paths,
        config=config,
        target=args.target,
        version=args.version,
        input_path=paths['hex_path'],
    )

    if pkg_path is None:
        print('ERROR (main) - Package process failed', file=sys.stderr)
        sys.exit(1)


def parse_version(version_str: str) -> tuple:
    """
    Parses MAJOR.MINOR.PATCH+RC. Each component must fit in a byte.
    Exits on invalid input.
    """
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)\+(\d+)$", version_str)
    if match is None:
        print(f"ERROR (parse_version) - version format is invalid: {version_str}", file=sys.stderr)
        sys.exit(1)

    version_tuple = tuple(int(match.group(i)) for i in range(1, 5))
    for value in version_tuple:
        if value < 0 or value > 255:
            print(f"ERROR (parse_version) - Version component out of range: {value}", file=sys.stderr)
            sys.exit(1)

    return version_tuple


def load_config() -> configparser.ConfigParser:
    """
    Loads config.ini from the script's directory (not cwd), so the script can
    be invoked from anywhere.
    """
    script_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_path, "config.ini")

    if not os.path.exists(config_path):
        print(f"ERROR (load_config) - Config not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def _is_file(path: str) -> None:
    if not os.path.isfile(path):
        print(f"ERROR - Path not found at {path}", file=sys.stderr)
        sys.exit(1)


def _is_dir(path: str) -> None:
    if not os.path.isdir(path):
        print(f"ERROR - Directory not found at {path}", file=sys.stderr)
        sys.exit(1)


def discover_paths(config: configparser.ConfigParser, target: str) -> dict:
    """
    Locates the attiny project directory for this target, plus FwPkgUtility
    paths. Project must be a sibling of the script with Makefile + nbproject/.
    """
    paths = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths["script_path"] = script_dir

    project_path = None
    for entry in os.listdir(script_dir):
        entry_path = os.path.join(script_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        if target not in entry.lower():
            continue
        if not os.path.isfile(os.path.join(entry_path, "Makefile")):
            continue
        if not os.path.isdir(os.path.join(entry_path, "nbproject")):
            continue
        project_path = entry_path
        break

    if project_path is None:
        print(f"ERROR - No attiny project directory found for target: {target}", file=sys.stderr)
        sys.exit(1)
    paths["project_path"] = project_path

    utility_dir = os.path.join(script_dir, "FwPkgUtility")
    _is_dir(utility_dir)

    builder_path = os.path.join(utility_dir, "data", "FwPkgBuilder.exe")
    _is_file(builder_path)
    paths["builder_path"] = builder_path

    results_path = os.path.join(utility_dir, "results")
    _is_dir(results_path)
    paths["results"] = results_path

    return paths


def run_build(config: configparser.ConfigParser, paths: dict) -> bool:
    """
    Runs `make CONF=offset` in the project directory.
    Prefers MAKE_PATH env var (set by batch launcher), falls back to config.ini.
    """
    project_path = paths["project_path"]

    make_path = os.environ.get("MAKE_PATH")
    if not make_path:
        make_path = config.get("ATTINY", "make-path")
    _is_file(make_path)

    cmd = [make_path, "CONF=offset"]
    print(f'DEBUG - Running: {cmd} in {project_path}')
    result = subprocess.run(cmd, cwd=project_path)
    return result.returncode == 0


def discover_hex(paths: dict) -> None:
    """
    Locates the .production.hex from the offset build. Expects exactly one match.
    """
    project_path = paths["project_path"]
    pattern = os.path.join(project_path, "dist", "offset", "production", "*.production.hex")
    matches = glob.glob(pattern)

    if len(matches) == 1:
        paths["hex_path"] = matches[0]
    elif len(matches) == 0:
        print(f"ERROR (discover_hex) - No .production.hex found at {pattern}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"ERROR (discover_hex) - Multiple .production.hex files at {pattern}", file=sys.stderr)
        sys.exit(1)


def hex_to_bin(hex_path: str, allowed_start: int, allowed_size: int, placeholder: int = 0xFF, page_size: int = 128) -> bytes:
    """
    Converts an Intel HEX file to raw firmware bytes.

    Reads the hex line by line. Data records inside the allowed window are
    kept; records outside are silently dropped (this filters FUSE records at
    0x00820000). Gaps in the allowed window are filled with placeholder bytes.
    Final output is padded to a page boundary.

    Intel HEX format: each line is :LLAAAATT[DD...]CC where LL=length,
    AAAA=16-bit address, TT=record type, DD=data, CC=checksum.
    Record types handled: 00 (data), 01 (EOF), 04 (extended linear address).
    """
    allowed_end = allowed_start + allowed_size
    base_addr = 0  # upper 16 bits, set by EXT_ADDR_LIN records
    data_by_addr = {}  # full_address -> byte value

    with open(hex_path, 'rt') as f:
        for line_num, line in enumerate(f, start=1):
            line = line.rstrip()
            if not line:
                continue
            if line[0] != ':':
                print(f'ERROR (hex_to_bin) - Line {line_num}: missing start code', file=sys.stderr)
                sys.exit(1)

            try:
                record = bytes.fromhex(line[1:])
            except ValueError:
                print(f'ERROR (hex_to_bin) - Line {line_num}: invalid hex characters', file=sys.stderr)
                sys.exit(1)

            if len(record) < 5:
                print(f'ERROR (hex_to_bin) - Line {line_num}: record too short', file=sys.stderr)
                sys.exit(1)

            length = record[0]
            address_low = (record[1] << 8) | record[2]
            rec_type = record[3]
            payload = record[4:4 + length]

            # Sum of all bytes (incl checksum) must be 0 mod 256
            if (sum(record) & 0xFF) != 0:
                print(f'ERROR (hex_to_bin) - Line {line_num}: bad checksum', file=sys.stderr)
                sys.exit(1)

            if rec_type == 0x00:  # DATA
                full_addr = base_addr + address_low
                # Drop the whole record if any byte falls outside allowed window
                if full_addr < allowed_start or full_addr + length > allowed_end:
                    continue
                for i, byte in enumerate(payload):
                    data_by_addr[full_addr + i] = byte

            elif rec_type == 0x01:  # EOF
                break

            elif rec_type == 0x04:  # EXT_ADDR_LIN — upper 16 bits of address
                if length != 2:
                    print(f'ERROR (hex_to_bin) - Line {line_num}: bad EXT_ADDR_LIN length', file=sys.stderr)
                    sys.exit(1)
                base_addr = ((payload[0] << 8) | payload[1]) << 16

            # Other types (02, 03, 05) ignored — not used in AVR builds

    if not data_by_addr:
        return b''

    # Build contiguous binary from allowed_start up to highest written address
    max_addr = max(data_by_addr.keys())
    size = max_addr - allowed_start + 1

    bin_data = bytearray([placeholder] * size)
    for addr, byte in data_by_addr.items():
        bin_data[addr - allowed_start] = byte

    # Pad to page boundary
    remainder = len(bin_data) % page_size
    if remainder > 0:
        bin_data += bytes([placeholder] * (page_size - remainder))

    return bytes(bin_data)


def package_firmware(paths: dict, config: configparser.ConfigParser, target: str, version: str, input_path: str) -> str | None:
    """
    Converts the .hex to a binary (filtering out FUSE records), names it
    according to FwPkgBuilder's required convention (<target>_fw<version>.bin),
    then invokes FwPkgBuilder to wrap it in the package format.
    """
    fwpkgbuilder = paths["builder_path"]
    results_dir = paths["results"]

    # ATtiny3227 application section: starts at 0x1000 (after 4KB bootloader),
    # size 28544 bytes (32KB total - 4KB bootloader - 128B app descriptor).
    # If you add ATtiny1627 or other variants later, parameterize per device.
    bin_data = hex_to_bin(
        hex_path=input_path,
        allowed_start=0x1000,
        allowed_size=28544,
        placeholder=0xFF,
        page_size=128,
    )

    staged_name = f"{target}_fw{version}.bin"
    staged_path = os.path.join(results_dir, staged_name)
    with open(staged_path, 'wb') as f:
        f.write(bin_data)
    print(f'DEBUG - Staged binary: {staged_path} ({len(bin_data)} bytes)')

    cmd = [fwpkgbuilder, staged_path]
    print(f'DEBUG - Package firmware: {cmd}')
    result = subprocess.run(cmd)
    if result.returncode != 0:
        return None

    base, _ = os.path.splitext(staged_path)
    pkg_path = base + '.pkg'

    if not os.path.isfile(pkg_path):
        print(f'ERROR (package_firmware) - Package not produced at {pkg_path}', file=sys.stderr)
        return None

    return pkg_path


if __name__ == "__main__":
    main()