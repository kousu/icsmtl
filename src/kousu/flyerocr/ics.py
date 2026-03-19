import os
import uuid
import base64
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Tuple

from . import util

# TODO:
# import icalendar
# - run black

log = logging.getLogger("kousu.flyerocr.__main__")

PRODID = "-//flyerocr//EN"


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


def datetime2ics(T):
    if isinstance(T, datetime):
        # note: datetimes are also dates; so this case has to be first
        return T.strftime("%Y%m%dT%H%M%S")
    elif isinstance(T, date):
        return T.strftime("%Y%m%d")


def _interpret_date(
    start_date, end_date, start_time, end_time
) -> Tuple[date | datetime, date | datetime]:
    """
    mangle the date info into dtstart/dtend, doing our best to guess missing information if it wasn't on the flyer or parsed badly
    """
    # -> this should go into ics.py

    if not start_date:
        raise ValueError("date is required")
        return None, None

    # Ignore end_time if there's no start_time to anchor it
    if end_time and not start_time:
        end_time = None

    if not end_date:
        # default to single day events
        end_date = start_date

    if not start_time:
        # --- All-day cases ---
        dtstart = start_date
        dtend = end_date if end_date else dtstart + timedelta(days=1)
    else:
        # --- Timed cases ---
        if not end_time:
            # default to 3 hour events; easy to see notice and correct if needed, without overflowing the screen
            end_time = start_time + timedelta(hours=3)

        dtstart = datetime.combine(start_date, start_time)
        dtend = datetime.combine(end_date, end_time)

    if dtend <= dtstart:
        # End might be past midnight (e.g. party starts 22:00, ends 03:00)
        dtend += timedelta(days=1)

    return dtstart, dtend


def make(event, length_limit=None):
    """Build a single-event VCALENDAR string."""
    summary = event.get("title")
    description = event.get("description")
    location = event.get("location")
    image = None  # TODO: embed image as a URL or base64
    price = event.get("price")
    url = event.get("url")
    id = event.get("id") or str(uuid.uuid6())

    dtstart, dtend = _interpret_date(
        event.get("date"),
        event.get("end_date"),
        event.get("start_time"),
        event.get("end_time"),
    )
    if not dtstart:
        raise ValueError("Unknown date")

    now = datetime2ics(datetime.today())
    dtstart = datetime2ics(dtstart)
    dtend = datetime2ics(dtend)

    tzid = "America/Montreal"
    if tzid:
        dt_prefix = f";TZID={tzid}"
    else:
        dt_prefix = ""

    description = description or ""
    # clip the description for sanity
    # # this should go into make_ics
    if length_limit is not None:
        description = description[:length_limit]
    if price:
        description += f"\n\nPrice: {price}"
    if url and url not in description:
        description += f"\n\n{url}"
    description = description.strip()

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "BEGIN:VEVENT",
        fold_line(f"DTSTAMP{dt_prefix}:{format_datetime(now)}"),
        fold_line(f"DTSTART{dt_prefix}:{format_datetime(dtstart)}"),
        fold_line(f"DTEND{dt_prefix}:{format_datetime(dtend)}"),
        fold_line(f"SUMMARY:{escape_ics_text(summary)}"),
        fold_line(f"DESCRIPTION:{escape_ics_text(description)}"),
    ]
    if image:
        if image.startswith("https://"):
            lines.append(fold_line(f"IMAGE;VALUE=URI:{image}"))
        elif os.path.exists(image):
            lines.append(
                fold_line(
                    f"IMAGE;VALUE=BINARY;ENCODING=BASE64;FMTTYPE={mimetypes.guess_type(image)}:{base64.b64encode(open(image,'rb').read())}"
                )
            )
        else:
            raise TypeError("Unable to interpret image={image}")
    if url:
        lines.append(fold_line(f"URL:{url}"))
    if location:
        lines.append(fold_line(f"LOCATION:{escape_ics_text(location)}"))
    lines += [
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def save(event, output_path: str | Path):
    filename = util.filename(event)

    ics = make(event)

    os.makedirs(output_path, exist_ok=True)
    output_path = os.path.join(output_path, filename)

    with open(output_path, "w", encoding="utf-8") as fd:
        log.debug(ics)
        fd.write(ics)

    return output_path


if __name__ == "__main__":
    import doctest

    doctest.testmod()
