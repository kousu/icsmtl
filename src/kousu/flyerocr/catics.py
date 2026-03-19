import sys
import argparse
from itertools import chain

import icalendar

PRODID = "-//icsmtl//ics-cat//EN"


def cat(files):
    cal = icalendar.Calendar()
    cal["prodid"] = PRODID
    for event in chain(*(icalendar.Calendar.from_ical(p).events for p in files)):
        cal.add_component(event)

    return cal


def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple .ics files into a single VCALENDAR"
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Input .ics files",
    )
    args = parser.parse_args()

    sys.stdout.buffer.write(
        cat(args.inputs).to_ical()
    )  # .buffer because icalendar works in bytes


if __name__ == "__main__":
    main()
