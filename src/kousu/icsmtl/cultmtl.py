import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from kousu.flyerocr.ics import save as save_ics

FEED_URL = "https://cultmtl.com?feed=event_feed"
DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), "events", "cultmtl")

parser = argparse.ArgumentParser(
    description="Scrape events from the Cult MTL RSS feed into .ics files"
)
parser.add_argument(
    "-o",
    "--output-dir",
    default=DEFAULT_OUTPUT_DIR,
    help=f"Output directory for .ics files (default: {DEFAULT_OUTPUT_DIR})",
)
args = parser.parse_args()

def scrape_item(item):

    title = item.find("title")
    link = item.find("link")
    content = item.find("content:encoded") or item.find("encoded")
    location = item.find("event_listing:location") or item.find("location")
    start_date = item.find("event_listing:start_date") or item.find("start_date")
    end_date = item.find("event_listing:end_date") or item.find("end_date")
    ticket_price = item.find("event_listing:ticket_price") or item.find(
        "ticket_price"
    )

    if not title or not start_date or not end_date:
        return

    title_text = title.get_text(strip=True)
    dtstart = datetime.strptime(start_date.get_text(strip=True), "%Y-%m-%d %H:%M:%S")
    dtend = datetime.strptime(end_date.get_text(strip=True), "%Y-%m-%d %H:%M:%S")

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
        'title': title_text,

        # this is kind of janky because it just roundtrips
        # text -> datetime -> date+time -> datetime -> textto round-trip these like this but okay
        'date': dtstart.date(),
        'start_time': dtstart.time(),
        'end_date': dtend.date(),
        'end_time': dtend.time(),

        # the test of the details
        'description': description,
        'location': location,
        'price': ticket_price.get_text(strip=True),
        'url': link.get_text(strip=True) if link else None,
    }


def main():

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


if __name__ == "__main__":
    main()
