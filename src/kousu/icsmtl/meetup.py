import argparse
import os
import glob
from pathlib import Path
from datetime import datetime
import logging

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

from kousu.flyerocr.ics import save as save_ics
from kousu.flyerocr.catics import cat as cat_ics
from kousu.flyerocr.util import interpret_datetime

log = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.WARN,
    format="%(asctime)s %(levelname)-6s %(name)+25s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


DEFAULT_OUTPUT_DIR = "./events/"

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

parser = argparse.ArgumentParser(
    description="Scrape events from a Meetup group into .ics files"
)
parser.add_argument(
    "-v", "--verbose", action="count", default=0, help="Enable verbose logging"
)
parser.add_argument(
    "-o",
    "--output-dir",
    default=DEFAULT_OUTPUT_DIR,
    help=f"Base output directory for .ics files (default: {DEFAULT_OUTPUT_DIR})",
)
parser.add_argument(
    "urlname",
    help="The group's URL name (e.g. yellowdoor)",
)


def location_string(venue):
    if not venue:
        return None
    parts = []
    name = venue.get("name") or ""
    address = venue.get("address") or ""
    if name and name != address:
        # sometimes the name field duplicates the address when there isn't an explicit name set
        parts.append(name)
    if address:
        parts.append(address)
    if venue.get("postalCode"):
        parts.append(venue["postalCode"])
    if venue.get("city"):
        parts.append(venue["city"])
    return ", ".join(parts) if parts else None


def scrape_event(edge):
    event = edge["node"]

    logging.debug("%s", event)

    dtstart = datetime.fromisoformat(event["dateTime"])
    # No end time from the API, so guess
    dtstart, dtend = interpret_datetime(dtstart.date(), None, dtstart.time(), None)

    event = {
        "title": event["title"],
        "dtstart": dtstart,
        "dtend": dtend,
        "description": event.get("description"),
        "location": location_string(event.get("venue")),
        "url": event["eventUrl"],
        #'price': ... ?,
    }

    return event


def scrape(group: str, output_dir: str | Path):
    transport = RequestsHTTPTransport(url="https://www.meetup.com/gql2")
    client = Client(transport=transport, fetch_schema_from_transport=False)

    result = client.execute(EVENTS_QUERY, variable_values={"urlname": group})

    group = result["groupByUrlname"]
    edges = group["events"]["edges"]

    if not edges:
        print(f"No events found for {group}.")
        return

    for edge in edges:
        event = scrape_event(edge)
        filename = save_ics(event, output_dir)
        print(f"\t{event['url']} => {filename}")


def main():
    args = parser.parse_args()
    output_dir = os.path.join(args.output_dir, "meetup", args.urlname)

    if args.verbose > 0:
        logging.getLogger().setLevel(logging.INFO)
    if args.verbose > 1:
        logging.getLogger().setLevel(logging.DEBUG)

    scrape(args.urlname, output_dir)

    merged_calendar = cat_ics(glob.glob(os.path.join(output_dir, "*.ics")))
    with open(output_dir + ".ics", "wb") as fd:
        fd.write(merged_calendar.to_ical())
        print("Output to", os.path.relpath(fd.name, "."))


if __name__ == "__main__":
    main()
