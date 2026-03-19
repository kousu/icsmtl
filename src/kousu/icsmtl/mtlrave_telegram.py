import argparse
import glob
import hashlib
import os
import re
import traceback
import json
import unicodedata
import subprocess
from urllib.parse import urljoin
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from xdg.BaseDirectory import xdg_cache_home

from kousu.flyerocr.ocr import make_ics
from kousu.flyerocr.util import sanitize_title

SEARCH_URL = "https://t.me/s/mtlrave"
CACHE_DIR = os.path.join(xdg_cache_home, "icsmtl", "mtlrave_telegram")
POSTS_DIR = os.path.join(CACHE_DIR, "posts")
FLYERS_DIR = os.path.join(CACHE_DIR, "flyers")
DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), "events")
USER_AGENT = "icsmtl/0.1"


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
        ),  # only accept external links; links back to Telegram are noise
    )
    return urljoin(SEARCH_URL, a_tag["href"]) if a_tag else None


def extract_image_url(style):
    """Pull URL from a background-image:url('...') CSS declaration."""
    m = re.search(r"background-image:\s*url\('([^']+)'\)", style or "")
    return m.group(1) if m else None


def fetch_day(session, d, output_dir):
    """Fetch and cache Telegram posts for a given date."""
    tag = date_tag(d)
    url = f"{SEARCH_URL}?q=%23{tag}"
    print(f"[{d}] Fetching {url}")

    date_str = d.strftime("%Y-%m-%d")

    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    posts = soup.select("div.tgme_widget_message")

    if not posts:
        print(f"[{d}] No posts found")
        return

    print(f"[{d}] Found {len(posts)} post(s)")

    for post in posts:
        post_attr = post.get("data-post", "")
        if "/" not in post_attr:
            continue
        post_id = post_attr.split("/")[-1]

        # Try photo wrap first, then video thumbnail
        img_url = None
        photo_el = post.select_one("a.tgme_widget_message_photo_wrap")
        if photo_el:
            img_url = extract_image_url(photo_el.get("style"))
        if not img_url:
            video_el = post.select_one("i.tgme_widget_message_video_thumb")
            if video_el:
                img_url = extract_image_url(video_el.get("style"))

        if not img_url:
            print(f"  Post {SEARCH_URL}/{post_id}: no image, skipping")
            continue

        # Determine file extension from URL
        ext = os.path.splitext(img_url.split("?")[0])[-1] or ".jpg"

        post_dir = os.path.join(POSTS_DIR, post_id)
        flyer_path = os.path.join(post_dir, f"flyer{ext}")

        # Phase 1: Download flyer if not cached
        if not os.path.exists(flyer_path):
            print(f"gotta scrape for {flyer_path}")
            caption_el = post.select_one("div.tgme_widget_message_text")
            caption_url = extract_caption_url(caption_el)
            caption = caption_el.get_text() if caption_el else ""

            os.makedirs(post_dir, exist_ok=True)
            if caption_url:
                with open(
                    os.path.join(post_dir, "url.txt"), "w", encoding="utf-8"
                ) as f:
                    f.write(caption_url)
            print(f"  Post {SEARCH_URL}/{post_id} : downloading flyer{ext}")
            img_resp = session.get(img_url, timeout=30)
            img_resp.raise_for_status()
            img_data = img_resp.content
            flyer_hash = hashlib.sha256(img_data).hexdigest()
            canonical_flyer = os.path.join(FLYERS_DIR, f"{flyer_hash}{ext}")
            if not os.path.exists(canonical_flyer):
                with open(canonical_flyer, "wb") as f:
                    f.write(img_data)

            if os.path.lexists(flyer_path):  # ln -s --force
                os.remove(flyer_path)
            os.symlink(os.path.relpath(canonical_flyer, post_dir), flyer_path)
            with open(
                os.path.join(post_dir, "caption.txt"), "w", encoding="utf-8"
            ) as f:
                f.write(caption)

        # Phase 2: Extract .ics from flyer
        # Find actual flyer file (handles any extension)
        flyer_files = glob.glob(os.path.join(post_dir, "flyer.*"))
        if not flyer_files:
            print(f"  Post {SEARCH_URL}/{post_id}: no flyer file found, skipping")
            continue
        flyer_path = flyer_files[0]

        with open(flyer_path, "rb") as f:
            flyer_hash = hashlib.sha256(f.read()).hexdigest()

        event = ocr_flyer(flyer_path)

        # Tweak the event to read nicer:

        # Determine event URL
        # use the url in the caption if there was one
        # but fill in the link to the Telegram post if not
        url_path = os.path.join(post_dir, "url.txt")

        if os.path.exists(url_path):
            with open(url_path, "r", encoding="utf-8") as f:
                event["url"] = f.read().strip()

        if not event.get("url"):
            event["url"] = f"https://t.me/s/mtlrave/{post_id}"

        # clip the description for sanity
        if event["description"] is not None:
            event["description"] = event["description"][:500]

        # print(event)
        #
        # we know the date and timezone of these events, so impose that

        tz = ZoneInfo("America/Montreal")

        if event.get("date") and event.get("end_date"):
            delta = event["end_date"] - event["date"]
            event["end_date"] = d + delta
        event["date"] = d

        for field in ["date", "end_date"]:
            if event.get(field):
                event[field] = event[field].replace(tzinfo=tz)

        # Build ICS
        ics_content = make_ics(event)

        filename = f"{date_str}-{sanitize_title(event['title'])}.ics"
        output_path = os.path.join(output_dir, filename)
        print(f"  Post {SEARCH_URL}/{post_id} => {filename}")
        with open(output_path, "w", encoding="utf-8") as f:
            # print(ics_content)
            f.write(ics_content)


def main():
    parser = argparse.ArgumentParser(
        description="Download flyer images and captions from the @mtlrave Telegram channel"
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
    args = parser.parse_args()
    args.output_dir = os.path.join(args.output_dir, "mtlrave_telegram")
    if args.end is None:
        args.end = args.start + timedelta(days=90)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(FLYERS_DIR, exist_ok=True)

    d = args.start
    while d <= args.end:
        fetch_day(session, d, args.output_dir)
        d += timedelta(days=1)

    with open(args.output_dir + ".ics", "w") as merged_calendar:
        subprocess.run(
            ["catics"] + glob.glob(os.path.join(args.output_dir, "*.ics")),
            stdout=merged_calendar,
            check=True,
        )
        print("Output to", os.path.relpath(merged_calendar.name, "."))


if __name__ == "__main__":
    main()
