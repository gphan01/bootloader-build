"""
File:
    generate_pkg_rt1064.py

Description:
    - The script automates the process of generating the
      corresponding packages for the customer bootloader
      being used for the EkoHeat2 project.

    - Process is stricly for the rt1064 mcus

Expected File System:

    FwPkgUtility/
    ├── data/
    ├── keys/
    └── results/

    project_application/
    generate_pkg_rt1064.py

  Preconditions:
   - Script expects this file structure.

Author:
    Gabe Phan <pphan@ambrell.com>

Date:
    2026-04-13
"""

import argparse
import sys
import re
import configparser
import os
import subprocess
import glob

DEVICE_EXTENSIONS = {
    "main": ".bin",
    "tuner": ".bin",
}


def main():
    parser = argparse.ArgumentParser(
        description="Firmware build and packaging pipeline"
    )

    parser.add_argument(
        "-d", "--target", required=True, choices=["main", "tuner", "io", "driver"]
    )
    parser.add_argument("-v", "--version", required=True)
    parser.add_argument("-sb", "--skip-build", required=False, action="store_true")

    args = parser.parse_args()

    # Version tuple currently unused.
    # In the future may be useful
    version = parse_version(args.version)

    config = load_config()

    paths = discover_paths(config)

    if not prepare_dot_project(paths):
        sys.exit(1)

    if not prepare_project(paths):
        sys.exit(1)

    if not args.skip_build:
        if not run_build(config, paths):
            sys.exit(1)

    discover_eoc(target=args.target, paths=paths)

    signed_path = sign_firmware(
        config=config, paths=paths, target=args.target, version_str=args.version
    )
    if signed_path is None:
        print("Error: signing process failed", file=sys.stderr)
        sys.exit(1)

    # print(f'DEBUG (main) - Signed firmare at {signed_path}\n')

    pkg_path = package_firmware(paths=paths, target=args.target, input_path=signed_path)
    if pkg_path is None:
        print("ERROR - Package process failed.\n", file=sys.stderr)
        sys.exit(1)

    # print(f'DEBUG (main) - {paths}\n')


def parse_version(version_str: str) -> tuple:
    """
    Parses the version argument passed to the script.
    Returns a tuple on success, on failure returns a
    code 1 and exits.
    """
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)\+(\d+)$", version_str)

    if match is None:
        print(f"ERROR (parse_version) - version format is invalid: {version_str}")
        sys.exit(1)

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    rc = int(match.group(4))

    version_tuple = (major, minor, patch, rc)
    for value in version_tuple:
        if value < 0 or value > 255:
            print(
                f"ERROR (parse_version) - Version component out of range: {value}",
                file=sys.stderr,
            )
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
        print(
            f"ERROR (load_config) - Config path not found at {config_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    return config


# Helper function to determine if the path to a file is valid
def _is_file(path: str) -> None:
    if not os.path.isfile(path):
        print(f"Error: path not found at {path}", file=sys.stderr)
        sys.exit(1)


def discover_paths(config: configparser.ConfigParser) -> dict:
    """
    Discovers paths that are stored in a dictionary to be used throughout
    the script.
    Returns True on success, exits with code 1 on failure.
    """

    paths = {}

    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths["script_path"] = script_dir

    utility_dir = os.path.join(script_dir, "FwPkgUtility")

    entries = os.listdir(path=script_dir)
    for entry in entries:
        entry_path = os.path.join(script_dir, entry)
        if os.path.isdir(entry_path):
            cproject_path = os.path.join(entry_path, ".cproject")

            if os.path.isfile(cproject_path):
                # .cproject found in MCUXpresso project directory
                paths["project_path"] = entry_path
                paths["cproject_path"] = cproject_path

                dot_project_path = os.path.join(entry_path, ".project")
                if not os.path.isfile(dot_project_path):
                    print(
                        f"ERROR (discover_paths) - .project not found at {dot_project_path}",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                paths["dot_project_path"] = dot_project_path
                break

    if "project_path" not in paths:
        print("ERROR - No .cproject found", file=sys.stderr)
        sys.exit(1)

    imgtool_path = os.path.join(utility_dir, "data", "imgtool.exe")
    _is_file(imgtool_path)

    paths["imgtool"] = imgtool_path

    fwpkgbuilder_path = os.path.join(utility_dir, "data", "FwPkgBuilder.exe")
    _is_file(fwpkgbuilder_path)

    paths["fwpkgbuilder"] = fwpkgbuilder_path

    key_pair_name = config.get("SIGNING", "key-pair-name")
    sign_path = os.path.join(
        utility_dir, "keys", key_pair_name, f"sign_{key_pair_name}.pem"
    )
    _is_file(sign_path)

    paths["sign_path"] = sign_path

    enc_path = os.path.join(
        utility_dir, "keys", key_pair_name, f"enc_{key_pair_name}.pem"
    )
    _is_file(enc_path)

    paths["enc_path"] = enc_path

    results_path = os.path.join(utility_dir, "results")

    if not os.path.isdir(results_path):
        print(
            f"ERROR (discover_paths) - path not found at {results_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    paths["results_path"] = results_path

    return paths


def prepare_dot_project(paths: dict) -> bool:
    """
    Updates the <name> element in .project to match the project-name
    Returns True on success, False on failure.
    """
    project_name = os.path.basename(paths["project_path"])
    dot_project_path = paths["dot_project_path"]

    if not os.path.isfile(dot_project_path):
        print(f"ERROR - .project not found at {dot_project_path}", file=sys.stderr)
        return False

    with open(dot_project_path, "r", encoding="utf-8", newline="") as f:
        text = f.read()

    pattern = r"<name>[^<]*</name>"
    replacement = f"<name>{project_name}</name>"
    new_text, count = re.subn(pattern, replacement, text, count=1)

    if count == 0:
        print(
            "ERROR (prepare_dot_project) - <name> element not found in .project",
            file=sys.stderr,
        )
        return False

    with open(dot_project_path, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)

    return True


def prepare_project(paths: dict) -> bool:
    """
    Modifies .cproject via text surgery
      1. Add MFLASH_BASE_ADDR=0x380000 to Debug defined symbols
      2. Update PROGRAM_FLASH memoryInstance location and size
    Returns True on success, False on failure.
    """

    cproject_path = paths["cproject_path"]

    with open(cproject_path, "r", encoding="utf-8", newline="") as f:
        text = f.read()

    debug_cfg_anchor = 'id="com.crt.advproject.config.exe.debug'
    debug_cfg_idx = text.find(debug_cfg_anchor)

    if debug_cfg_idx == -1:
        print(
            "ERROR (prepare_project) - Debug cconfiguration not found", file=sys.stderr
        )
        return False

    symbols_anchor = 'superClass="gnu.c.compiler.option.preprocessor.def.symbols"'
    symbols_idx = text.find(symbols_anchor, debug_cfg_idx)
    if symbols_idx == -1:
        print(
            "ERROR (prepare_project) - Debug defined-symbols option not found",
            file=sys.stderr,
        )
        return False

    option_close_idx = text.find("</option>", symbols_idx)
    if option_close_idx == -1:
        print(
            "ERROR (prepare_project) - closing </option> after defined-symbols not found",
            file=sys.stderr,
        )
        return False

    option_block = text[symbols_idx:option_close_idx]
    if "MFLASH_FILE_BASEADDR" not in option_block:
        # Match the indentation of existing listOptionValue lines (tabs in this file)
        new_line = '\t\t\t\t\t\t\t\t\t<listOptionValue builtIn="false" value="MFLASH_FILE_BASEADDR=0x380000"/>\n'

        # Find the last \n before </option> and insert there
        insert_at = text.rfind("\n", symbols_idx, option_close_idx) + 1
        text = text[:insert_at] + new_line + text[insert_at:]

    # Regex: find id="PROGRAM_FLASH" and replace the location and size attrs
    # that follow it on the same element.
    pattern = r'(id="PROGRAM_FLASH"[^/]*?location=")[^"]*(".*?size=")[^"]*(")'
    replacement = r"\g<1>0x70040400\g<2>0x140000\g<3>"
    new_text, count = re.subn(pattern, replacement, text)

    if count == 0:
        print("ERROR - PROGRAM_FLASH memoryInstance not found", file=sys.stderr)
        return False

    if count > 1:
        print(
            f"ERROR - PROGRAM_FLASH matched {count} times, expected 1", file=sys.stderr
        )
        return False

    text = new_text

    # removed for the bootloader build. Main doesn't have it; deletion is a no-op.
    pattern_pf2 = (
        r'[ \t]*&lt;memoryInstance[^/]*?id="PROGRAM_FLASH2"[^/]*?/&gt;&#13;\n?'
    )
    new_text, pf2_count = re.subn(pattern_pf2, "", text)
    if pf2_count > 1:
        print(
            f"ERROR (prepare_project) - PROGRAM_FLASH2 matched {pf2_count} times, expected 0 or 1",
            file=sys.stderr,
        )
        return False

    text = new_text

    with open(cproject_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    return True


def run_build(config: configparser.ConfigParser, paths) -> bool:
    """
    Runs the MCUXpresso headless build to generate the respective binary.
    Returns True on successs, False on failure
    """
    ide_path = config.get("MCUXPRESSO", "ide-path")
    workspace_path = config.get("MCUXPRESSO", "workspace-path")
    project_name = os.path.basename(paths["project_path"])

    script_path = paths["script_path"]

    command = [
        ide_path,
        "-nosplash",
        "--launcher.suppressErrors",
        "-application",
        "org.eclipse.cdt.managedbuilder.core.headlessbuild",
        "-data",
        workspace_path,
        "-importAll",
        script_path,
        "-cleanBuild",
        f"{project_name}/Debug",
    ]

    result = subprocess.run(command)

    if result.returncode != 0:
        return False

    return True


def discover_eoc(target: str, paths: dict) -> None:
    """
    Discovers the Executable Object Code (EOC) path.
    Returns None on success, exits with code 1 on failure.
    """
    device_extension = DEVICE_EXTENSIONS[target]

    project_path = paths["project_path"]
    debug_path = os.path.join(project_path, "Debug")
    pattern = os.path.join(debug_path, f"*{device_extension}")

    matches = glob.glob(pattern)

    if len(matches) == 1:
        paths["eoc_path"] = matches[0]
    elif len(matches) == 0:
        print(
            f"ERROR (discover_eoc) - No {device_extension} file found at {debug_path}",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(
            f"ERROR (discover_eoc) - Multiple {device_extension} files found at {debug_path}",
            file=sys.stderr,
        )
        sys.exit(1)


def sign_firmware(
    config: configparser.ConfigParser, paths: dict, target: str, version_str: str
) -> str | None:
    """
    Signs .bin firmware with imgtool (signing + optional encryption).
    For .hex devices, skips signing and returns the original file path.
    Returns the output path on success, None on failure.
    """
    input_path = paths["eoc_path"]

    if DEVICE_EXTENSIONS.get(target) != ".bin":
        return input_path

    header_size = config.get("BOOTLOADER", "header-size")
    slot_size = config.get("BOOTLOADER", "slot-size")
    align = config.get("BOOTLOADER", "align")
    pad_header = config.getboolean("BOOTLOADER", "pad-header")

    encryption_enabled = config.getboolean("SIGNING", "encryption-enabled")

    output_file_name = f"{target}_fw{version_str}.tmp"
    output_path = os.path.join(paths["results_path"], output_file_name)

    img_tool_path = paths["imgtool"]
    cmd = [
        img_tool_path,
        "sign",
        "--key",
        paths["sign_path"],
        "--align",
        align,
        "--header-size",
        header_size,
        "--slot-size",
        slot_size,
        "--version",
        version_str,
    ]

    if pad_header:
        cmd.append("--pad-header")

    if encryption_enabled:
        enc_path = paths["enc_path"]
        cmd.extend(["--encrypt", enc_path])

    cmd.append(input_path)
    cmd.append(output_path)

    # print(f'DEBUG - command: {cmd}\n')
    result = subprocess.run(cmd)

    if result.returncode != 0:
        return None

    return output_path


def package_firmware(paths: dict, target: str, input_path: str) -> str | None:
    """
    Wraps signed firmware (.tmp) or hex (.hex) into a .pkg via FwPkgBuilder.
    Returns the .pkg path on success, None on failure.
    """

    fwpkgbuilder = paths["fwpkgbuilder"]
    cmd = [fwpkgbuilder, input_path]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        return None

    base, _ = os.path.splitext(input_path)
    pkg_path = base + ".pkg"

    if not os.path.isfile(pkg_path):
        print(
            f"ERROR (package_firmmware) - Generated package file missing at {pkg_path}\n"
        )
        return None

    return pkg_path


if __name__ == "__main__":
    main()
