import argparse
import re
import sys


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
        "-o", "--output",
        default="-",
        help="Output file (default: stdout)",
    )
    args = parser.parse_args()

    paths = args.inputs

    # if not paths:
    #     print("No input files.", file=sys.stderr)
    #     sys.exit(1)

    vevents = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            vevents.extend(extract_vevents(f.read()))

    # if not vevents:
    #     print("No VEVENT blocks found in input files.", file=sys.stderr)
    #     sys.exit(1)

    lines = [
        "BEGIN:VCALENDAR\r\n",
        "VERSION:2.0\r\n",
        f"PRODID:{PRODID}\r\n",
    ]
    for vevent in vevents:
        # Normalize to CRLF
        lines.append(vevent.replace("\r\n", "\n").replace("\n", "\r\n"))
    lines.append("END:VCALENDAR\r\n")

    output = "".join(lines)

    if args.output == "-":
        sys.stdout.write(output)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {len(vevents)} event(s) to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
