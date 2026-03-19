import argparse
import os

import requests
from bs4 import BeautifulSoup

from icsmtl.util import make_ics, make_filename

FEED_URL = "https://cultmtl.com?feed=event_feed"
DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), "events")
PRODID = "-//icsmtl//cultmtl//EN"


def main():
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
    args.output_dir = os.path.join(args.output_dir, "cultmtl")

    resp = requests.get(FEED_URL, timeout=30, headers={"User-Agent": "icsmtl/0.1"})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "lxml-xml")
    items = soup.find_all("item")

    if not items:
        print("No events found in feed.")
        return

    os.makedirs(args.output_dir, exist_ok=True)

    count = 0
    for item in items:
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
            continue

        title_text = title.get_text(strip=True)
        link_text = link.get_text(strip=True) if link else ""
        dtstart = start_date.get_text(strip=True)
        dtend = end_date.get_text(strip=True)

        # Build description: HTML-stripped content + ticket price
        desc_parts = []
        if content:
            plain = BeautifulSoup(content.get_text(), "html.parser").get_text()
            desc_parts.append(plain.strip())
        if ticket_price:
            desc_parts.append(ticket_price.get_text(strip=True))

        description = "\n\n".join(desc_parts)

        ics_text = make_ics(
            title_text,
            description,
            dtstart,
            dtend,
            prodid=PRODID,
            location=location,
            tzid="America/Montreal",
            url=link_text or None,
        )
        filename = make_filename(dtstart, title_text)
        filepath = os.path.join(args.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(ics_text)

        count += 1

    print(f"Wrote {count} .ics files to {args.output_dir}")


if __name__ == "__main__":
    main()
