import argparse
import os

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

from icsmtl.util import make_ics, make_filename

DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), "events")
PRODID = "-//icsmtl//meetup//EN"

EVENTS_QUERY = gql("""
query ($urlname: String!) {
  groupByUrlname(urlname: $urlname) {
    id
    name
    events(first: 50) {
      edges {
        node {
          id
          eventUrl
          dateTime
          description
          title
          venue {
            name
            address
            postalCode
            city
          }
        }
      }
    }
  }
}
""")


def build_location(venue):
    """Build a LOCATION string from a venue dict, omitting name if it equals address."""
    if not venue:
        return None
    parts = []
    name = venue.get("name") or ""
    address = venue.get("address") or ""
    if name and name != address:
        parts.append(name)
    if address:
        parts.append(address)
    if venue.get("postalCode"):
        parts.append(venue["postalCode"])
    if venue.get("city"):
        parts.append(venue["city"])
    return ", ".join(parts) if parts else None


def main():
    parser = argparse.ArgumentParser(
        description="Scrape events from a Meetup group into .ics files"
    )
    parser.add_argument(
        "urlname",
        help="The group's URL name (e.g. yellowdoor)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Base output directory for .ics files (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()
    output_dir = os.path.join(args.output_dir, "meetup", args.urlname)

    transport = RequestsHTTPTransport(url="https://www.meetup.com/gql2")
    client = Client(transport=transport, fetch_schema_from_transport=False)

    result = client.execute(EVENTS_QUERY, variable_values={"urlname": args.urlname})

    group = result["groupByUrlname"]
    edges = group["events"]["edges"]

    if not edges:
        print(f"No events found for {args.urlname}.")
        return

    os.makedirs(output_dir, exist_ok=True)

    count = 0
    for edge in edges:
        event = edge["node"]

        title = event["title"]
        event_url = event["eventUrl"]
        description = event.get("description") or ""

        # dateTime is ISO 8601 with offset, e.g. "2026-02-02T12:30:00-05:00"
        # Strip offset (first 19 chars) and convert T to space for format_datetime
        raw_dt = event["dateTime"][:19]  # "2026-02-02T12:30:00"
        dtstart = raw_dt.replace("T", " ")  # "2026-02-02 12:30:00"
        # No end time from the API; use start time as end time
        dtend = dtstart

        location = build_location(event.get("venue"))

        ics_text = make_ics(
            title,
            description,
            dtstart,
            dtend,
            prodid=PRODID,
            location=location,
            url=event_url or None,
        )
        filename = make_filename(dtstart, title)
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(ics_text)

        count += 1

    print(f"Wrote {count} .ics files to {output_dir}")


if __name__ == "__main__":
    main()
