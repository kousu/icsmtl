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

    # print(prompt)  # DEBUG

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
        Identify the event within this flyer. Determine the title and if available
        the date, time, location, price, performers, ticket or information URLs,
        and special instructions.

        Dates and Times:
        Be aware it is possible for events to run overnight.
        Minimize |date - {now.strftime('%Y-%m-%d')}| and prefer shorter events (<= 24h) to longer ones.
        If the event appears to be far from now or appears to run for many days, consider possible typos
        or misreads in the OCR.

        Output:
        Return a JSON object with:

        - title: string (REQUIRED)
        - date: YYYY-MM-DD (use {now.strftime('%Y')} if year not shown)
        - end_date: YYYY-MM-DD or null (for multi-day events)
        - start_time: HH:MM (24h) or null
        - end_time: HH:MM (24h) or null
        - location: venue/address or null
        - price: price or null
        - url: URL or null
        - description: key details using ORIGINAL wording from the flyer. Include performers and special instructions.

        Rules:
        - Every event MUST have a title
        - Response must be ONLY valid, parseable JSON.
        - Do NOT wrap the output in markdown code quotes.
        - Do NOT wrap the output in '```json'.
        - Do NOT include a preface nor summary.
    """).lstrip())

    # DEBUG
    # print(event)
    # print()

    # strip markdown code quotes (Haiku in particular seems to be a fan of these)
    event=event.strip()
    if event.startswith('```') and event.endswith('```'):
        event = '\n'.join(event.split('\n')[1:-1])

    try:
        event = json.loads(event)
    except Exception as exc:
        raise Exception(f"Claude returned malformed json:\n\n{event}") from exc

    return event
