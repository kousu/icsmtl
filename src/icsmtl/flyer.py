import sys, os
from pathlib import Path
import argparse
import traceback
import json
import hashlib

from xdg.BaseDirectory import xdg_cache_home

from icsmtl.ocr import ocr_flyer
from icsmtl.util import escape_ics_text, fold_line, make_ics, parse_ics, redate_ics
from icsmtl.mtlrave_telegram import build_ics, sanitize_title

# TODO: should mtlrave-telegram and this share a flyer OCR cache?
CACHE_DIR = os.path.join(xdg_cache_home, "icsmtl", "flyers")
FLYERS_DIR = os.path.join(CACHE_DIR, "flyers")
OCR_DIR = os.path.join(CACHE_DIR, "ocr")
DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), "events")
USER_AGENT = "icsmtl/0.1"
PRODID = "-//icsmtl//flyers//EN"


def read_flyer(flyer_path, output_dir):

    flyer_path = str(flyer_path)

    with open(flyer_path,"rb") as img:
      img_data = img.read()

    # Determine file extension from URL
    ext = os.path.splitext(flyer_path.split("?")[0])[-1] or ".jpg"

    flyer_hash = hashlib.sha256(img_data).hexdigest()
    canonical_flyer = os.path.join(FLYERS_DIR, f"{flyer_hash}{ext}")
    if not os.path.exists(canonical_flyer):
        with open(canonical_flyer, "wb") as f:
            f.write(img_data)


    # hashing the flyer lets us cache it so we don't burn lots of OCR cost

    ocr_json_path = os.path.join(OCR_DIR, f"{flyer_hash}.json")
    ocr_exc_path = os.path.join(OCR_DIR, f"{flyer_hash}.exc")

    if not os.path.exists(ocr_json_path):
        try:
            print(f"Running OCR on {flyer_path}")
            event = ocr_flyer(flyer_path)
        except Exception:
            with open(ocr_exc_path, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            print(f"  Post {flyer_path}: extraction failed, see {ocr_exc_path}")
            return
        with open(ocr_json_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(event))

    with open(ocr_json_path, "r", encoding="utf-8") as f:
        event = json.loads(f.read())

    # clip the description for sanity
    if event['description'] is not None:
        event['description'] = event['description'][:500]

    # print(event)

    # Build ICS
    ics_content = build_ics(event, id=flyer_hash, PRODID=PRODID)

    date_str = event['date']

    filename = f"{date_str}-{sanitize_title(event['title'])}.ics"
    output_path = os.path.join(output_dir, filename)
    print(f"  {flyer_path} => {filename}")
    with open(output_path, "w", encoding="utf-8") as f:
        # print(ics_content)
        f.write(ics_content)

def main():
    parser = argparse.ArgumentParser(
        description="Download flyer images and captions from the @mtlrave Telegram channel"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for .ics files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument('flyers', nargs='+', type=Path)
    args = parser.parse_args()
    args.output_dir = os.path.join(args.output_dir, "flyers")

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(FLYERS_DIR, exist_ok=True)
    os.makedirs(OCR_DIR, exist_ok=True)

    for flyer in args.flyers:
      read_flyer(flyer, args.output_dir)
