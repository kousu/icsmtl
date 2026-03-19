import os
import uuid
import base64
import logging
from datetime import datetime
from pathlib import Path

import filetype

from . import util

import icalendar

log = logging.getLogger(__name__)

PRODID = "-//flyerocr//EN"


def make(event, length_limit=None):
    """Build a single-event VCALENDAR string."""
    # log.debug(event)
    id = event.get("id") or str(uuid.uuid6())
    summary = event.get("title")
    dtstart, dtend = event.get("dtstart"), event.get("dtend")
    description = event.get("description")
    location = event.get("location")
    image = event.get("image")
    performers = event.get("performers")
    price = event.get("price")
    url = event.get("url")

    if not dtstart:
        raise ValueError("Event has no date.")

    description = description or ""
    # clip the description for sanity
    # # this should go into make_ics
    if length_limit is not None:
        description = description[:length_limit]
    if performers:
        if isinstance(performers, list):
            performers = "\n".join(f"* {p}" for p in performers)
        description += (
            f"\n\nPerformers:{"\n\n" if "\n" in performers else " "}{performers}"
        )
    if price:
        description += f"\n\nPrice: {price}"
    if url and url not in description:
        description += f"\n\n{url}"
    description = description.strip()

    cal = icalendar.Calendar()
    cal["prodid"] = PRODID

    event = icalendar.Event()
    cal.add_component(event)

    # for key, value in event.items(): event.add(key, value)
    # but there's a couple of exceptions that make it simpler to unroll the loop

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
