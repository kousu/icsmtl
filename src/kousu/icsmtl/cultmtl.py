import argparse
import os
import glob
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

import requests
from bs4 import BeautifulSoup

from kousu.flyerocr.ics import save as save_ics
from kousu.flyerocr.catics import cat as cat_ics

log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s %(levelname)-6s %(name)+25s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

FEED_URL = "https://cultmtl.com?feed=event_feed"
DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), "events", "cultmtl")

parser = argparse.ArgumentParser(
    description="Scrape events from the Cult MTL RSS feed into .ics files"
)
parser.add_argument(
    "-v", "--verbose", action="count", default=0, help="Enable verbose logging"
)
parser.add_argument(
    "-o",
    "--output-dir",
    default=DEFAULT_OUTPUT_DIR,
    help=f"Output directory for .ics files (default: {DEFAULT_OUTPUT_DIR})",
)


def scrape_item(item):

    title = item.find("title")
    link = item.find("link")
    content = item.find("content:encoded") or item.find("encoded")
    dtstart = item.find("event_listing:start_date") or item.find("start_date")
    dtend = item.find("event_listing:end_date") or item.find("end_date")
    location = item.find("event_listing:location") or item.find("location")
    ticket_price = item.find("event_listing:ticket_price") or item.find("ticket_price")

    if not title or not dtstart or not dtend:
        return

    title = title.get_text(strip=True)
    dtstart = datetime.strptime(dtstart.get_text(strip=True), "%Y-%m-%d %H:%M:%S")
    dtend = datetime.strptime(dtend.get_text(strip=True), "%Y-%m-%d %H:%M:%S")

    # We know the timezone
    tz = ZoneInfo("America/Montreal")
    dtstart = dtstart.replace(tzinfo=tz)
    dtend = dtend.replace(tzinfo=tz)

    # Get description
    description = []
    if content:
        plain = BeautifulSoup(content.get_text(), "html.parser").get_text()
        description.append(plain.strip())
    description = "\n\n".join(description)

    return {
        "title": title,
        "dtstart": dtstart,
        "dtend": dtend,
        "description": description or None,
        "location": location or None,
        "price": ticket_price.get_text(strip=True),
        "url": link.get_text(strip=True) if link else None,
    }


def scrape(args):
    resp = requests.get(FEED_URL, timeout=30, headers={"User-Agent": "icsmtl/0.1"})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "lxml-xml")
    items = soup.find_all("item")

    if not items:
        print("No events found in feed.")
        return

    for item in items:
        event = scrape_item(item)
        if event:
            filename = save_ics(event, args.output_dir)
            print(f"\t{event['url']} => {filename}")


def main():
    args = parser.parse_args()
    if args.verbose > 0:
        logging.getLogger().setLevel(logging.INFO)
    if args.verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)

    scrape(args)

    merged_calendar = cat_ics(glob.glob(os.path.join(args.output_dir, "*.ics")))
    with open(args.output_dir + ".ics", "wb") as fd:
        fd.write(merged_calendar.to_ical())
        print("Output to", os.path.relpath(fd.name, "."))


if __name__ == "__main__":
    main()
