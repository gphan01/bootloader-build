import argparse
import sys
import re

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

    print(f"Device:     {args.device}")
    print(f"Version:    {args.version}")
    print(f"Skip build: {args.skip_build}")
    print(f"No cleanup: {args.no_cleanup}")

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







if __name__ == "__main__":
  main();