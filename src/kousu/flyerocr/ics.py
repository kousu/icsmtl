import os
import uuid
import base64
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Tuple

import filetype

from . import util

# TODO:
import icalendar

log = logging.getLogger("kousu.flyerocr.__main__")

PRODID = "-//flyerocr//EN"


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
        raise ValueError("Event has no date.")

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

    cal = icalendar.Calendar()
    cal["prodid"] = PRODID

    event = icalendar.Event()
    cal.add_component(event)

    event.add("uid", id)
    event.add("summary", summary)
    event.add("description", description)
    event.add("dtstamp", datetime.today())
    event.add("dtstart", dtstart)
    event.add("dtend", dtend)

    if image:
        if isinstance(image, str) and image.startswith("https://"):
            event.add("image", image, paramters={"value": "uri"})
        else:
            image = util._load_bytes(image)
            event.add(
                "image",
                base64.b64encode(image),
                parameters={
                    "value": "binary",
                    "encoding": "base64",
                    "fmtype": filetype.guess(image).mime,
                },
            )
    if url:
        event.add("url", url)
    if location:
        event.add("location", location)

    return cal.to_ical().decode("utf-8")


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
