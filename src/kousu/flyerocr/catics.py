import argparse
import re
import sys
from contextlib import nullcontext
from itertools import chain

import icalendar

PRODID = "-//icsmtl//catics//EN"


def extract_vevents(ics_text):
    """Extract all VEVENT blocks from an ICS string."""
    return re.findall(
        r"^BEGIN:VEVENT\r?\n.*?^END:VEVENT\r?\n",
        ics_text,
        re.DOTALL | re.MULTILINE,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple .ics files into a single VCALENDAR"
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Input .ics files",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output file (default: stdout)",
    )
    args = parser.parse_args()

    cal = icalendar.Calendar()
    cal["prodid"] = PRODID
    for event in chain(*(icalendar.Calendar.from_ical(p).events for p in args.inputs)):
        cal.add_component(event)

    if args.output == "-":
        c = nullcontext(sys.stdout.buffer)
    else:
        c = open(args.output, "wb")

    with c as fd:
        fd.write(cal.to_ical())


if __name__ == "__main__":
    main()
