import argparse
import sys

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
  print(f"Device:     {args.device}")
  print(f"Version:    {args.version}")
  print(f"Skip build: {args.skip_build}")
  print(f"No cleanup: {args.no_cleanup}")

if __name__ == "__main__":
  main();