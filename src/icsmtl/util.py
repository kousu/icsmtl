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
