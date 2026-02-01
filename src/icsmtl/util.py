import re
from datetime import date, datetime, timedelta


def parse_ics(ics_content):
    """Extract title and date string from ICS content.

    Returns (title, date_str) where date_str is 'YYYY-MM-DD'.
    Handles both DTSTART:... and DTSTART;TZID=...:... formats.
    """
    title = date_str = None
    for line in ics_content.splitlines():
        if line.startswith("SUMMARY:"):
            title = line[len("SUMMARY:"):]
        elif line.startswith("DTSTART"):
            # e.g. DTSTART;TZID=America/Montreal:20260207T220000 or DTSTART:20260207T220000
            val = line.split(":", 1)[-1]
            date_str = f"{val[:4]}-{val[4:6]}-{val[6:8]}"
    return title, date_str


def _parse_ics_datetime(val):
    """Parse an ICS datetime value like '20260207T220000' into a datetime."""
    if "T" in val:
        return datetime.strptime(val, "%Y%m%dT%H%M%S")
    return date.strptime(val, "%Y%m%d")


def _format_ics_datetime(dt):
    """Format a datetime back into ICS format like '20260207T220000'."""
    if isinstance(dt, datetime):
        return dt.strftime("%Y%m%dT%H%M%S")
    elif isinstance(dt, date):
        return dt.strftime("%Y%m%d")
    else:
        raise ValueError(f"{dt} is not a date/time")


# Matches DTSTART or DTEND lines, with or without ;TZID=... parameters
_DT_RE = re.compile(r"^(DT(?:START|END))(?:;[^:]*)?:(\d{8}(?:T\d{6})?)", re.MULTILINE)

# TODO: maybe can take some code from radicale to handle this ics date parsing stuff

def redate_ics(ics_content, new_start_date):
    """Shift DTSTART/DTEND in ICS content so the event starts on new_start_date.

    If the input has no DTSTART, DTSTART is set to new_start_date.
    If the input has no DTEND, neither does the output.
    If it has DTSTART and it's a timestamp, its time component is copied onto new_start_date.
    If it has both, the original event duration is preserved.

    Args:
        ics_content: ICS string.
        new_start_date: A datetime.date for the correct start date.

    Returns:
        The rewritten ICS string.


    You can move an event with a start end end *date* (but no time) forward to the future:

    >>> dt = date(2027,8,23)
    >>> ics_content = \"""BEGIN:VCALENDAR
    ... VERSION:2.0
    ... PRODID:-//Lawb//EN
    ... BEGIN:VEVENT
    ... DTSTAMP:20260131T235538Z
    ... DTSTART:20260213
    ... DTEND:20260215
    ... SUMMARY:deep
    ... LOCATION:Entre Nous
    ... DESCRIPTION:deep with Daura\\\\, Wetdoge\\\\, Neonlichter
    ... END:VEVENT
    ... END:VCALENDAR
    ... \"""
    >>>
    >>> print(redate_ics(ics_content, dt).strip())
    BEGIN:VCALENDAR
    VERSION:2.0
    PRODID:-//Lawb//EN
    BEGIN:VEVENT
    DTSTAMP:20260131T235538Z
    DTSTART:20270823
    DTEND:20270825
    SUMMARY:deep
    LOCATION:Entre Nous
    DESCRIPTION:deep with Daura\\, Wetdoge\\, Neonlichter
    END:VEVENT
    END:VCALENDAR


    You can set an event with a start and end time back to the roman empire:

    >>> dt = date(107,1,19)
    >>> ics_content = \"""
    ... BEGIN:VCALENDAR
    ... VERSION:2.0
    ... PRODID:-//Lawb//EN
    ... BEGIN:VEVENT
    ... DTSTAMP:20260201T002206Z
    ... DTSTART:20080425T080000
    ... DTEND:20080425T090000
    ... SUMMARY:BitCHes Gay af th3se Days
    ... DESCRIPTION:BitCHes Gay af th3se Days\\\\,\\\\, <33\\\\nLis Dalton Badgalquirit\\\\nDATCHA\\\\nNov 15th\\\\nLast Login: 11/15/2009
    ... END:VEVENT
    ... END:VCALENDAR
    ... \""".strip()
    >>>
    >>> print(redate_ics(ics_content, dt))
    BEGIN:VCALENDAR
    VERSION:2.0
    PRODID:-//Lawb//EN
    BEGIN:VEVENT
    DTSTAMP:20260201T002206Z
    DTSTART:01070119T080000
    DTEND:01070119T090000
    SUMMARY:BitCHes Gay af th3se Days
    DESCRIPTION:BitCHes Gay af th3se Days\\,\\, <33\\nLis Dalton Badgalquirit\\nDATCHA\\nNov 15th\\nLast Login: 11/15/2009
    END:VEVENT
    END:VCALENDAR

    It's okay to correct an OCR mistake even if the event has no end:

    >>> dt = date(2025,12,17)
    >>> ics_content = \"""
    ... BEGIN:VCALENDAR
    ... VERSION:2.0
    ... BEGIN:VEVENT
    ... DTSTAMP:20260201T002343Z
    ... DTSTART:20251227T220000
    ... SUMMARY:Winterlude
    ... LOCATION:3487 BOUL SAINT-LAURENT
    ... DESCRIPTION:WINTERLUDE 10PM-3AM 12.27.25 featuring BABAGANOUSCHKA CORI DJORSA MEEN MOREEN HURAKKAN NO POLICE PRML
    ... END:VEVENT
    ... END:VCALENDAR
    ... \""".strip()
    >>> print(redate_ics(ics_content, dt))
    BEGIN:VCALENDAR
    VERSION:2.0
    BEGIN:VEVENT
    DTSTAMP:20260201T002343Z
    DTSTART:20251217T220000
    SUMMARY:Winterlude
    LOCATION:3487 BOUL SAINT-LAURENT
    DESCRIPTION:WINTERLUDE 10PM-3AM 12.27.25 featuring BABAGANOUSCHKA CORI DJORSA MEEN MOREEN HURAKKAN NO POLICE PRML
    END:VEVENT
    END:VCALENDAR


    An event without a date can be given one:

    >>> dt = date(2025,6,5)
    >>> ics_content = \"""
    ... BEGIN:VCALENDAR
    ... VERSION:2.0
    ... BEGIN:VEVENT
    ... DTSTAMP:20260201T002510Z
    ... SUMMARY:DOMESICLE #2401 La Rama Records
    ... DESCRIPTION:DOMESICLE #2401 La Rama Records featuring Luca Lozano (UK) & Mr. Ho (HK) with balgalquirit b2b donotstealmyname and D4000 Melesul3
    ... END:VEVENT
    ... END:VCALENDAR
    ... \""".strip()
    >>> print(redate_ics(ics_content, dt))
    BEGIN:VCALENDAR
    VERSION:2.0
    BEGIN:VEVENT
    DTSTART:20250605
    DTSTAMP:20260201T002510Z
    SUMMARY:DOMESICLE #2401 La Rama Records
    DESCRIPTION:DOMESICLE #2401 La Rama Records featuring Luca Lozano (UK) & Mr. Ho (HK) with balgalquirit b2b donotstealmyname and D4000 Melesul3
    END:VEVENT
    END:VCALENDAR

    """
    # Extract old DTSTART and DTEND values and their properties (e.g. TZID)
    old_start = old_end = None
    for m in _DT_RE.finditer(ics_content):
        key = m.group(1)
        value = m.group(2)

        if key == "DTSTART":
            old_start = _parse_ics_datetime(value)
        if key == "DTEND":
            old_end = _parse_ics_datetime(value)

    # new_start and new_end are Union[date, datetime]; calendar events can EITHER give a timestamp OR just a day.
    new_start = new_end = None

    if isinstance(old_start, datetime):
        # copy the time portion onto the new date
        new_start = datetime.combine(new_start_date, old_start.time())
    else:
        # old_start was a date OR undefined => force it to new start
        new_start = new_start_date

    # compute new_end, preserving event duration
    # but if the event didn't havea duration then leave it undefined
    if old_start is not None and old_end is not None:
        new_end = new_start + (old_end - old_start)

    # shove in a start point
    # XXX janky
    if "DTSTART" not in ics_content:
        ics_content = ics_content.replace("BEGIN:VEVENT", "BEGIN:VEVENT\nDTSTART:00000000")

    def _replace(m):
        if new_start is not None and m.group(1).startswith("DTSTART"):
            prefix, _ = m.group(0).split(":",1)
            return prefix + ":" + _format_ics_datetime(new_start)
        if new_end is not None and m.group(1).startswith("DTEND"):
            prefix, _ = m.group(0).split(":",1)
            return prefix + ":" + _format_ics_datetime(new_end)
        return m.group(0)


    return _DT_RE.sub(_replace, ics_content)

if __name__ == '__main__':
    import doctest
    doctest.testmod()
