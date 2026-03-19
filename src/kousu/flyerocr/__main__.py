import os
from pathlib import Path
import argparse
import logging

from .ocr import ocr_flyer
from . import ics

log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s %(levelname)-6s %(name)+25s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


parser = argparse.ArgumentParser(
    description="Convert flyer images to iCal files"
)
parser.add_argument(
    "-o", "--output-dir",
    default=".",
    help="Output directory for .ics files (default: ./)",
)
parser.add_argument(
    '-v', '--verbose',
    action='count',
    default=0,
    help='Enable verbose logging'
)
parser.add_argument('flyers', nargs='+', type=Path)


def main():

    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    if not anthropic_key:
        parser.error('ANTHROPIC_API_KEY environment variable must be set')
        raise SystemExit(1)
    os.environ['ANTHROPIC_API_KEY'] = anthropic_key.strip()

    args = parser.parse_args()

    if args.verbose > 0:
        logging.getLogger().setLevel(logging.INFO)
    if args.verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)


    # ----------------------------

    for flyer in args.flyers:
      # flyer = os.path.relpath(flyer)
      try:
          output_ics  = ics.save(ocr_flyer(flyer), args.output_dir)
          print(f"{flyer} => {output_ics}")
      except ValueError as exc:
          print(f"Failed to parse {flyer}: {exc}")
          if args.verbose:
              import traceback
              traceback.print_exc()

if __name__ == '__main__':
    main()
