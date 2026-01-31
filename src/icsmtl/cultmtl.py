import os
import unicodedata

import requests
from bs4 import BeautifulSoup


FEED_URL = "https://cultmtl.com?feed=event_feed"
OUTPUT_DIR = os.path.join(os.getcwd(), "events", "cultmtl")
PRODID = "-//icsmtl//cultmtl//EN"


def fold_line(line):
    """Fold a content line per RFC 5545: at 75 octets, continuation lines start with a space."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    chunks = []
    while len(encoded) > 75:
        # first chunk is 75 octets, subsequent are 74 (leading space takes 1)
        limit = 75 if not chunks else 74
        cut = limit
        # don't split in the middle of a multi-byte UTF-8 character
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        chunks.append(encoded[:cut])
        encoded = encoded[cut:]
    if encoded:
        chunks.append(encoded)
    return (b"\r\n ".join(chunks)).decode("utf-8")


def escape_ics_text(text):
    """Escape special characters for ICS text values."""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    return text


def format_datetime(dt_str):
    """Convert '2026-03-08 18:30:00' to '20260308T183000'."""
    return dt_str.replace("-", "").replace(" ", "T").replace(":", "")


def make_filename(title):
    """NFKD-normalize, drop non-ASCII, replace spaces and / with _, append .ics."""
    name = unicodedata.normalize("NFKD", title)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.replace(" ", "_").replace("/", "_")
    return name + ".ics"


def make_ics(summary, description, url, dtstart, dtend):
    """Build a single-event VCALENDAR string."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "BEGIN:VEVENT",
        fold_line(f"DTSTART;TZID=America/Montreal:{format_datetime(dtstart)}"),
        fold_line(f"DTEND;TZID=America/Montreal:{format_datetime(dtend)}"),
        fold_line(f"SUMMARY:{escape_ics_text(summary)}"),
        fold_line(f"DESCRIPTION:{escape_ics_text(description)}"),
        fold_line(f"URL:{url}"),
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def main():
    resp = requests.get(FEED_URL, timeout=30, headers={"User-Agent": "icsmtl/0.1"})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "lxml-xml")
    items = soup.find_all("item")

    if not items:
        print("No events found in feed.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    count = 0
    for item in items:
        title = item.find("title")
        link = item.find("link")
        content = item.find("content:encoded") or item.find("encoded")
        start_date = item.find("event_listing:start_date") or item.find("start_date")
        end_date = item.find("event_listing:end_date") or item.find("end_date")
        ticket_price = item.find("event_listing:ticket_price") or item.find("ticket_price")

        if not title or not start_date or not end_date:
            continue

        title_text = title.get_text(strip=True)
        link_text = link.get_text(strip=True) if link else ""
        dtstart = start_date.get_text(strip=True)
        dtend = end_date.get_text(strip=True)

        # Build description: HTML-stripped content + link + ticket price
        desc_parts = []
        if content:
            plain = BeautifulSoup(content.get_text(), "html.parser").get_text()
            desc_parts.append(plain.strip())
        if link_text:
            desc_parts.append(link_text)
        if ticket_price:
            desc_parts.append(ticket_price.get_text(strip=True))

        description = "\n\n".join(desc_parts)

        ics_text = make_ics(title_text, description, link_text, dtstart, dtend)
        filename = make_filename(title_text)
        filepath = os.path.join(OUTPUT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(ics_text)

        count += 1

    print(f"Wrote {count} .ics files to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
