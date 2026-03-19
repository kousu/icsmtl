import io
from pathlib import Path
import unicodedata
from typing import IO, Tuple
from types import NoneType
from datetime import date, time, datetime, timedelta


def sanitize_title(title):
    """Sanitize a title for use in filenames."""
    name = unicodedata.normalize("NFKD", title)
    name = name.encode("ascii", "ignore").decode("ascii")
    return name.replace(" ", "_").replace("/", "_")


def filename(event):
    """Build filename as {YYYY-MM-DD}-{sanitized_title}.ics."""
    title = sanitize_title(event["title"])
    if event.get("dtstart"):
        date = event["dtstart"].strftime("%Y-%m-%d")
        return f"{date}-{title}.ics"
    else:
        return f"{title}.ics"


def _load_bytes(data: str | Path | bytes | IO[bytes]) -> bytes:
    """
    Get the contents of data whatever form it's in:
    - if a string (or Path), assume it's a path and load it
    - if it's a file object, read it
    - if it's already bytes, return it
    """
    if isinstance(data, str) or isinstance(data, Path):
        with open(data, "rb") as data:
            data = data.read()
    elif isinstance(data, (io.RawIOBase, io.BufferedIOBase)):
        data = data.read()
    assert isinstance(
        data, bytes
    ), "At this point, data should have been coerced to bytes"
    return data

def interpret_datetime(
    start_date: date | None, end_date: date | None, start_time: time | None, end_time: time | None
) -> Tuple[date | datetime, date | datetime]:
    """
    mangle the date info into dtstart/dtend, doing our best to guess missing information if it wasn't on the flyer or parsed badly
    """

    if not isinstance(start_date, (date, NoneType)):
        raise TypeError("start_date")
    if not isinstance(end_date, (date, NoneType)):
        raise TypeError("end_date")
    if not isinstance(start_time, (time, NoneType)):
        raise TypeError("start_time")
    if not isinstance(end_time, (time, NoneType)):
        raise TypeError("end_time")

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
