import argparse
import os
import re
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup
from xdg.BaseDirectory import xdg_cache_home

SEARCH_URL = "https://t.me/s/mtlrave"
CACHE_DIR = os.path.join(xdg_cache_home, "icsmtl", "mtlrave_telegram")
USER_AGENT = "icsmtl/0.1"


def date_tag(d):
    """Format a date as DDmonYY, e.g. 07feb26."""
    return f"{d.day:02d}{d.strftime('%b').lower()}{d.strftime('%y')}"


def extract_image_url(style):
    """Pull URL from a background-image:url('...') CSS declaration."""
    m = re.search(r"background-image:\s*url\('([^']+)'\)", style or "")
    return m.group(1) if m else None


def fetch_day(session, d):
    """Fetch and cache Telegram posts for a given date."""
    tag = date_tag(d)
    url = f"{SEARCH_URL}?q=%23{tag}"
    print(f"[{d}] Fetching {url}")

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
            print(f"  Post {post_id}: no image, skipping")
            continue

        # Determine file extension from URL
        ext = os.path.splitext(img_url.split("?")[0])[-1] or ".jpg"

        post_dir = os.path.join(CACHE_DIR, post_id)
        flyer_path = os.path.join(post_dir, f"flyer{ext}")

        if os.path.exists(flyer_path):
            print(f"  Post {post_id}: cached, skipping")
            continue

        # Extract caption
        caption_el = post.select_one("div.tgme_widget_message_text")
        caption = caption_el.get_text() if caption_el else ""

        # Download image and write caption
        os.makedirs(post_dir, exist_ok=True)
        print(f"  Post {post_id}: downloading flyer{ext}")
        img_resp = session.get(img_url, timeout=30)
        img_resp.raise_for_status()
        with open(flyer_path, "wb") as f:
            f.write(img_resp.content)
        with open(os.path.join(post_dir, "caption.txt"), "w", encoding="utf-8") as f:
            f.write(caption)


def main():
    parser = argparse.ArgumentParser(
        description="Download flyer images and captions from the @mtlrave Telegram channel"
    )
    parser.add_argument(
        "-s", "--start",
        type=lambda s: date.fromisoformat(s),
        default=date.today(),
        help="Start date (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "-e", "--end",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="End date (YYYY-MM-DD, default: start + 3 months)",
    )
    args = parser.parse_args()
    if args.end is None:
        args.end = args.start + timedelta(days=90)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    d = args.start
    while d <= args.end:
        fetch_day(session, d)
        d += timedelta(days=1)

    print(f"\nCache directory: {CACHE_DIR}")


if __name__ == "__main__":
    main()
