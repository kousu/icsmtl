"""Extract event details from flyer images using a vision API."""

import os
import base64, json
from textwrap import dedent
from datetime import datetime, timedelta
import re

import mimetypes
import requests


USER_AGENT = "icsmtl/0.1"


def ask_claude_about_image(image_path: str, prompt: str) -> str:

    #return json.dumps({'title': 'Fire Horse 火馬年 Lunar New Year Party', 'date': '2020-02-21', 'end_date': None, 'start_time': '19:00', 'end_time': '03:00', 'location': '@parquette', 'price': None, 'description': '18+ | LUNAR NEW YEAR PARTY\n\nPerformers: MIASALAV, kiju b2b sako, Guan (LIVE), Lather Rinse Repeat\n\nPerformers: Traditional Lion Dance, Tokyo the Superstar, Xandrost, Mellyun, log____off\n\nv: o0yu\nInstallation: Glotto\nFood: Laphing Center\nHostesses: 2d girlfriend, anglar\n\nWORKSHOPS 19-22\nRAVE 22-3\n\nstickyrice'})

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    # Detect media type from file extension
    media_type, _ = mimetypes.guess_type(image_path)
    supported = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if media_type not in supported:
        raise ValueError(f"Unsupported image type '{media_type}'. Must be one of: {supported}")

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    print(prompt)

    # Current models (as of early 2026) -- see https://platform.claude.com/docs/en/about-claude/models/overview
    # Claude 4.6 family (latest):
    #   "claude-opus-4-6"              -- most capable, best reasoning
    #   "claude-sonnet-4-6"            -- fast, capable, good balance
    # Claude 4.5 family:
    #   "claude-opus-4-5-20251101"
    #   "claude-sonnet-4-5-20250929"
    #   "claude-haiku-4-5-20251001"    -- fastest, cheapest
    # Older (still available):
    #   "claude-sonnet-4-20250514"
    #   "claude-opus-4-20250514"
    #   "claude-haiku-3-5-20241022"
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "User-Agent": USER_AGENT,
        },
        json={
            "model": "claude-sonnet-4-6",
            # "model": "claude-haiku-4-5-20251001",
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        },
        timeout=60,
    )

    try:
        resp.raise_for_status()
    except Exception as exc:
        try: # to get the 'error' message given by the server
            # XXX this was for the other API so .. maybe doesn't work with claude ?
            raise #Exception(resp.json()['error']) from exc
        except:
            # but if there's no message or something else goes wrong, fall back
            raise exc

    return resp.json()["content"][0]["text"]

def ics_escape(s):
    "escape the characters that are special to the ics format"
    return s.replace('\\', r'\\').replace(',', r'\,').replace(';', r'\;').replace('\n', r'\n')

def build_ics(event, id=None):

    if not id:
        id = str(uuid.uuid6())

    # timestamp generation
    now = datetime.today()
    now = now.isoformat()
    now = now.split('.')[0]
    now = re.sub('[-:]','', now)

    ## mangle the date info into dtstart/dtend
    date, end_date, start_time, end_time = event.get('date'), event.get('end_date'), event.get('start_time'), event.get('end_time')
    if not date:
        raise ValueError("date is required")

    # Ignore end_time if there's no start_time to anchor it
    if end_time and not start_time:
        end_time = None

    date_obj = datetime.strptime(date, "%Y-%m-%d")

    if not start_time:
        # --- All-day cases ---
        # use the DATE format:       YYYYMMDD
        # (we do not impose a timezone = floating local time)
        dtstart = date_obj.strftime("%Y%m%d")
        if end_date:
            # iCal all-day DTEND is exclusive, so add one day to the last day
            end_obj = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            dtend = end_obj.strftime("%Y%m%d")
        else:
            dtend = None
    else:
        # --- Timed cases ---
        # use the DATE-TIME format:    YYYYMMDDTHHmmSS
        # (we do not impose a timezone = floating local time)
        start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        dtstart = start_dt.strftime("%Y%m%dT%H%M%S")

        if end_time:
            end_base = datetime.strptime(end_time, "%H:%M")
            end_dt = start_dt.replace(hour=end_base.hour, minute=end_base.minute, second=0)
            if end_dt <= start_dt:
                # End might be past midnight (e.g. party starts 22:00, ends 03:00)
                end_dt += timedelta(days=1)
            # If an explicit end_date was given, use that date instead
            if end_date:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt = end_dt.replace(year=end_date_obj.year,
                                        month=end_date_obj.month,
                                        day=end_date_obj.day)
        else:
            end_dt = start_dt + timedelta(hours=1)

        dtend = end_dt.strftime("%Y%m%dT%H%M%S")

    ## build the cal
    vcal = dedent(f"""
        BEGIN:VCALENDAR
        VERSION:2.0
        PRODID:-//icsmtl Event Extractor//EN
    """).lstrip()

    vcal += dedent(f"""
        BEGIN:VEVENT
        UID:{ics_escape(id)}@evt
        DTSTAMP:{now}
        DTSTART:{dtstart}
        DTEND:{dtend}
        SUMMARY:{ics_escape(event['title'] or 'Event')}
    """).lstrip()

    if event.get('location', ""):
        vcal += f"LOCATION:{ics_escape(event['location'])}\n"

    if event.get('description', ""):
        vcal += f"DESCRIPTION:{ics_escape(event['description'])}\n"

    vcal += dedent("""
        END:VEVENT
        END:VCALENDAR
    """).lstrip()

    return vcal

def ocr_flyer(image):
    """Extract event info from a flyer image.

    Args:
        image: A file path (str/PathLike), raw bytes, or PIL Image.

    Returns:
        (title, date, ics_content) from the first event in the API response.
    """

    now = datetime.today()
        # add this to the prompt to debug things:
        # - reasoning: an explanation in plain english of your reasoning chain for selecting each value
    event = ask_claude_about_image(image, dedent(f"""
        Identify the event within this flyer. Determine the title and if available the date, time, location and price.

        Dates and Times:
        Today is {now.strftime('%Y-%m-%d')} and the event likely is near; if the date appears far from today, re-check your OCR, the font might just be hard to read.
        If the time format is ambiguous assume the event is given in 12h time. Be aware it is possible for events to run overnight.

        Other text:
        Assume any other text is a description (e.g. performers, special instructions).

        Output:
        Return a JSON object with:

        - title: string (REQUIRED)
        - date: YYYY-MM-DD (use {now.strftime('%Y')} if year not shown)
        - end_date: YYYY-MM-DD or null (for multi-day events)
        - start_time: HH:MM (24h) or null
        - end_time: HH:MM (24h) or null
        - location: venue/address or null
        - price: price or null
        - description: key details using ORIGINAL wording from the image. Include performers, URLs, special instructions.

        Rules:
        - Every event MUST have a title
        - Response must be ONLY valid, parseable JSON.
        - Do NOT wrap the output in markdown code quotes.
        - Do NOT wrap the output in '```json'.
        - Do NOT include a preface nor summary.
    """).lstrip())

    print(event)
    print()

    # strip markdown code quotes (Haiku in particular seems to be a fan of these)
    event=event.strip()
    if event.startswith('```') and event.endswith('```'):
        event = '\n'.join(event.split('\n')[1:-1])

    try:
        event = json.loads(event)
    except Exception as exc:
        raise Exception("Claude returned malformed json") from exc

    print(event)
    print()

    # clip the description for sanity
    if event['description'] is not None:
        event['description'] = event['description'][:500]

    id = os.path.splitext(os.path.basename(image))[0] # use the flyer filename as the event ID in the vCal
    return event["title"], event["date"], build_ics(event, id=id)
