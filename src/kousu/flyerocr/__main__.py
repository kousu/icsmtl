import os
import copy
from pathlib import Path
import argparse
import json
import hashlib
import logging
import pickle # lol

from xdg.BaseDirectory import xdg_cache_home

from .ocr import ocr_flyer
from kousu.icsmtl.mtlrave_telegram import build_ics, sanitize_title

log = logging.getLogger("kousu.flyerocr")

PRODID = "-//icsmtl//flyers//EN"
CACHE_DIR = os.path.join(xdg_cache_home, "kousu", "flyersocr")

def extract(flyer_path: str | Path, output_path: str | Path):
    flyer_path = str(flyer_path)

    with open(flyer_path,"rb") as img:
      img_data = img.read()

    # hashing the flyer lets us cache it so we don't burn lots of OCR cost
    # TODO move this into ocr_flyer() directly?
    flyer_hash = hashlib.sha256(img_data).hexdigest()
    os.makedirs(CACHE_DIR, exist_ok=True)
    json_path = os.path.join(CACHE_DIR, f"{flyer_hash}.json")
    exc_path = os.path.join(CACHE_DIR, f"{flyer_hash}.exc")

    if os.path.exists(exc_path):
        log.warn("Flyer has a cached exception %s", exc_path)
        with open(exc_path,'rb') as exc:
            raise pickle.load(exc) # LOL?

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as fd:
            log.info("Loading OCR for '%s' from '%s'", flyer_path, json_path)
            event = json.loads(fd.read())
    else:
        try:
            log.info("Running OCR on %s", flyer_path)
            event = ocr_flyer(flyer_path)
        except Exception as exc:
            with open(exc_path, "w", encoding="utf-8") as fd:
                exc = copy.copy(exc)
                exc.__traceback__ = None # detach
                pickle.dump(exc, fd)
            raise

        with open(json_path, "w", encoding="utf-8") as fd:
            fd.write(json.dumps(event))

    # ----

    if not event.get('is_event', False) or not event.get('date'):
        desc = event.get('description', '')
        raise ValueError('Not an event' + (f": {desc}" if desc else ""))

    # clip the description for sanity
    if event['description'] is not None:
        event['description'] = event['description'][:500]

    # print(event)  # DEBUG

    # Build ICS
    ics_content = build_ics(event, id=flyer_hash, PRODID=PRODID)

    date_str = event['date']

    if date_str:
        filename = f"{date_str}-{sanitize_title(event['title'])}.ics"
    else:
        filename = f"{sanitize_title(event['title'])}.ics"

    os.makedirs(output_path, exist_ok=True)
    output_path = os.path.join(output_path, filename)
    with open(output_path, "w", encoding="utf-8") as fd:
        # print(ics_content)  # DEBUG
        fd.write(ics_content)
    return output_path



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
    action='store_true',
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

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    # ----------------------------

    for flyer in args.flyers:
      # flyer = os.path.relpath(flyer)
      try:
          filename = extract(flyer, args.output_dir)
          print(f"  {flyer} => {filename}")
      except ValueError as exc:
          print(f"Failed to parse {flyer}: {exc}")

if __name__ == '__main__':
    main()
