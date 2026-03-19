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
    start_date: date, end_date: date, start_time: time, end_time: time
) -> Tuple[date | datetime, date | datetime]:
    """
    mangle the date info into dtstart/dtend, doing our best to guess missing information if it wasn't on the flyer or parsed badly
    """

    # there are four inputs, each could be missing or not, so that's 2^4 = 16 cases
    # to cover, plus some subcases
    #
    if not start_date:
        # This eliminates half the cases
        raise ValueError("Start date is required")
        return None, None

    if not start_time and end_time:
        # it doesn't make sense to have an end time without a start time
        # this is almost certainly an OCR mixup, so swap them
        #
        # this eliminates two of the remaining cases, leaving 6
        log.warn("Swapping start and end times")
        start_time, end_time = end_time, start_time

    if not start_time:
        # --- All-day cases -> (date, date) ---
        dtstart = start_date

        if end_date:
            # e.g. "September 8th - October 9th"
            dtend = end_date
        else:
            # e.g. "November the 5th"
            dtend = dtstart + timedelta(days=1)
    else:
        # --- Timed cases -> (datetime, datetime) ---
        dtstart = datetime.combine(start_date, start_time)

        if not end_time:
            if not end_date:
                # e.g. "March 28th, 7pm"
                # default to 3 hour events;
                # Most calendar apps default to 1 hour events, but we use 3 to
                # make imported problems easier to notice. Also most events are
                # 2-3 hours long, let's be real, and even if someone never updates
                # it to an accurate time, a 3 hour block on their calendar isn't
                # going to harm much.
                dtend = dtstart + timedelta(hours=3)
            else:
                # e.g. "February 16th, 5pm - 19th"
                # => degenerate case
                # this might mean _every day starting at 5pm_
                # or it might mean starting at 5pm February 1
                # we interpret this as "February 16th, 5pm -> February 19th, 5pm"
                # which at least shows that it's a multiday event and retains the start time
                log.warn("Missing end time in (%s, %s) -> (%s, %s). Assuming end_time = %s", start_date, start_time, end_date, end_time, start_time)
                dtend = datetime.combine(end_date, start_time)
        else:
            if not end_date:
                # This is case 5; it has two subcases because it's the only one that might have an ambiguous time.
                if end_time > start_time:
                    # e.g. "July 1st, 9am - 5pm"
                    dtend = datetime.combine(start_date, end_time)
                else:
                    # overnight e.g. "October 31st, 7pm - 3am"
                    dtend = datetime.combine(start_date, end_time) + timedelta(days=1)
            else:
                # e.g. "January 17th, 5pm - March 31st, 2am"
                dtend = datetime.combine(end_date, end_time)

    if dtend <= dtstart:
        log.warn("Impossible date range interpreted: %s - %s. This event will not be importable.", dtstart, dtend)

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
