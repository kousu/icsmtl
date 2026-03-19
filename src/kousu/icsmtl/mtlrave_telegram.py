import argparse
import glob
import hashlib
import os
import re
import subprocess
import logging
from urllib.parse import urljoin
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from xdg.BaseDirectory import xdg_cache_home

from kousu.flyerocr.ocr import ocr_flyer
from kousu.flyerocr.ics import save as save_ics

CHANNEL_URL = "https://t.me/s/mtlrave"
CACHE_DIR = os.path.join(xdg_cache_home, "icsmtl", "mtlrave_telegram")
POSTS_DIR = os.path.join(CACHE_DIR, "posts")
FLYERS_DIR = os.path.join(CACHE_DIR, "flyers")
DEFAULT_OUTPUT_DIR = "./events/"
USER_AGENT = "icsmtl/0.1"

log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s %(levelname)-6s %(name)+25s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def date_tag(d):
    """Format a date as DDmonYY, e.g. 07feb26."""
    return f"{d.day:02d}{d.strftime('%b').lower()}{d.strftime('%y')}"


def extract_caption_url(caption_el):
    """Extract the first URL in the caption that's not a link back to Telegram."""
    if not caption_el:
        return None
    a_tag = caption_el.find(
        "a",
        href=lambda h: h.startswith(
            "http"
        ),  # onlyaccept external links; links back to Telegram are noise
    )
    return urljoin(CHANNEL_URL, a_tag["href"]) if a_tag else None


def extract_image_url(style):
    """Pull URL from a background-image:url('...') CSS declaration."""
    m = re.search(r"background-image:\s*url\('([^']+)'\)", style or "")
    return m.group(1) if m else None


def fetch_telegram_posts(session, url): # -> seq[Tuple[post_url, image_url, caption]]:
    """

    """
    assert url.startswith("https://t.me/s/")

    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    posts = soup.select("div.tgme_widget_message")

    if not posts:
        print("No posts found")
        return

    print(f"{len(posts)} post(s) found")

    for post in posts:
        post_attr = post.get("data-post", "")
        if "/" not in post_attr:
            continue
        post_id = post_attr.split("/")[-1]

        # Try photo wrap first, then video thumbnail
        img_url = None
        photo = post.select_one("a.tgme_widget_message_photo_wrap")
        if photo:
            img_url = extract_image_url(photo.get("style"))
            post_url = photo['href']
        if not img_url:
            video = post.select_one("i.tgme_widget_message_video_thumb")
            if video:
                img_url = extract_image_url(video.get("style"))
                post_url = video.find_parent('a')['href']

        if not img_url:
            print(f"  Post {post_id}: no image, skipping")
            continue

        caption_el = post.select_one("div.tgme_widget_message_text")
        caption_url = extract_caption_url(caption_el)
        caption = caption_el.get_text() if caption_el else ""

        yield post_id, post_url, img_url, caption, caption_url



def fetch_day(session, d, output_dir):
    """Fetch and cache Telegram posts for a given date."""
    tag = date_tag(d)
    url = f"{CHANNEL_URL}?q=%23{tag}"
    print(f"[{d}] Fetching {url}")

    for post_id, post_url, img_url, caption, caption_url in fetch_telegram_posts(session, url):

        # Determine file extension from URL
        ext = os.path.splitext(img_url.split("?")[0])[-1] or ".jpg"

        post_dir = os.path.join(POSTS_DIR, post_id)
        flyer_path = os.path.join(post_dir, f"flyer{ext}")

        # Phase 1: Download flyer if not cached
        img_data = None
        if not os.path.exists(flyer_path):
            log.info(f"Downloading flyer {CHANNEL_URL}/{post_id}")

            img_resp = session.get(img_url, timeout=30)
            img_resp.raise_for_status()
            img_data = img_resp.content

            flyer_hash = hashlib.sha256(img_data).hexdigest()

            os.makedirs(FLYERS_DIR, exist_ok=True)
            canonical_flyer = os.path.join(FLYERS_DIR, f"{flyer_hash}{ext}")
            if not os.path.exists(canonical_flyer):
                with open(canonical_flyer, "wb") as f:
                    f.write(img_data)

            if os.path.lexists(flyer_path):  # ln -s --force
                os.remove(flyer_path)
            log.debug(f"{flyer_path=}, {canonical_flyer=}, {post_dir=}")
            os.symlink(os.path.relpath(canonical_flyer, post_dir), flyer_path)
            with open(
                os.path.join(post_dir, "caption.txt"), "w", encoding="utf-8"
            ) as f:
                f.write(caption)

        # Phase 2: Extract .ics from flyer
        if img_data is None:
            flyer_files = glob.glob(os.path.join(post_dir, "flyer.*"))
            if not flyer_files:
                print(f"  Post {CHANNEL_URL}/{post_id}: no flyer file found, skipping")
                continue
            flyer_path = flyer_files[0]

            with open(flyer_path, "rb") as fd:
                img_data = fd.read()

        ## Do The OCR
        #
        event = ocr_flyer(img_data)

        # Tweak the event to read better
        #

        # We are sure anout the date, so impose it

        if event.get("date") and event.get("end_date"):
            delta = event["end_date"] - event["date"]
            event["end_date"] = d + delta
        event["date"] = d

        # We also know the timezone
        tz = ZoneInfo("America/Montreal")
        for field in ["start_time", "end_time"]:
            if event.get(field):
                event[field] = event[field].replace(tzinfo=tz)

        # clip the description for sanity
        if event["description"] is not None:
            event["description"] = event["description"][:500]

        # event url; use the organizer's link if given, else just link to the Telegram page
        event["url"] = caption_url if caption_url else f"{CHANNEL_URL}/{post_id}"

        # add (plaintext) caption
        if event['description'] is not None and caption.strip():
            if caption.strip():
                event['description'] += f"\n\n{caption}"

        # Save our results
        #

        filename = save_ics(event, output_dir)
        print(f"\t{CHANNEL_URL}/{post_id} => {filename}")


parser = argparse.ArgumentParser(
    description="Download flyer images and captions from the @mtlrave Telegram channel"
)
parser.add_argument(
    "-v", "--verbose", action="count", default=0, help="Enable verbose logging"
)
parser.add_argument(
    "-s",
    "--start",
    type=lambda s: date.fromisoformat(s),
    default=date.today(),
    help="Start date (YYYY-MM-DD, default: today)",
)
parser.add_argument(
    "-e",
    "--end",
    type=lambda s: date.fromisoformat(s),
    default=None,
    help="End date (YYYY-MM-DD, default: start + 3 months)",
)
parser.add_argument(
    "-o",
    "--output-dir",
    default=DEFAULT_OUTPUT_DIR,
    help=f"Output directory for .ics files (default: {DEFAULT_OUTPUT_DIR})",
)

def main():
    args = parser.parse_args()
    args.output_dir = os.path.join(args.output_dir, "mtlrave_telegram")
    if args.end is None:
        args.end = args.start + timedelta(days=90)

    if args.verbose > 0:
        logging.getLogger().setLevel(logging.INFO)
    if args.verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT


    d = args.start
    while d <= args.end:
        fetch_day(session, d, args.output_dir)
        d += timedelta(days=1)

    with open(args.output_dir + ".ics", "w") as merged_calendar:
        subprocess.run(
            ["ics-cat"] + glob.glob(os.path.join(args.output_dir, "*.ics")),
            stdout=merged_calendar,
            check=True,
        )
        print("Output to", os.path.relpath(merged_calendar.name, "."))


if __name__ == "__main__":
    main()
