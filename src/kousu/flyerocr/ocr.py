import os
import io
from pathlib import Path
from typing import IO
from textwrap import dedent
from datetime import date, time
import json
import base64
import traceback
import hashlib
import logging

import filetype
from xdg.BaseDirectory import xdg_cache_home
import requests  # TODO: httpx?

from .util import _load_bytes, interpret_datetime

log = logging.getLogger(__name__)

USER_AGENT = "icsmtl/0.1"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip().split("\n", 1)[0]
CACHE_DIR = os.path.join(xdg_cache_home, "kousu", "flyersocr")
ANTHROPIC_MAX_IMAGE_SIZE = 5242880  # 5MB limit; this is on the *base64 encoded size*


class NotEventError(ValueError):
    pass


def ask_claude_about_image(image: str | Path | bytes | IO[bytes], prompt: str) -> str:

    # there is an 'import anthropic' library
    # but it adds 17MB (!) to the venv and, for this simple case,
    # the code looks almost identical. So no.

    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    image_data = _load_bytes(image)

    if len(image_data) >= 6 / 8 * ANTHROPIC_MAX_IMAGE_SIZE:
        # 3/4 is because this limit is on the *base64* encoded size. base64 encodes
        # at 8 bits per 6 bits, so the actual image limit is smaller, about 3.5MB.
        # in this case, shrink and re-encode as lossy JPG. If the image was so large
        # it broke their limit it will still be legible even as a JPG.
        image_data = cap_image_size(image_data, 6 / 8 * ANTHROPIC_MAX_IMAGE_SIZE)

    media_type = filetype.guess(image_data).mime
    supported = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if media_type not in supported:  # or .startswith("image/") ?
        raise ValueError(
            f"Unsupported image type '{media_type}'. Must be one of: {supported}"
        )

    image_data = base64.standard_b64encode(image_data).decode("utf-8")

    if os.environ.get("DONT_ASK_CLAUDE"):
        return dedent("""
            {
              "is_event": true,
              "title": "Trashed. the debut.",
              "date": "2026-01-08",
              "end_date": "2026-01-09",
              "start_time": "22:00",
              "end_time": "03:00",
              "location": "Bar Barbossa, Montreal",
              "price": "$6 ATD",
              "url": null,
              "description": "the first volume of an electronic club night that seeks to explore the relationship between partying and social interaction. honestly, we just want you to come and have a good time.\n\nwith dj sets by: sineila, billy bondage, online threat, fangsie, & sophia fay.\n\nhosts: ariane, zak, logan — your new best friends who are gonna help you meet your new best friend.\n\nAlso featuring: dollgrip, yt2mp3, thugdoll"
            }""")

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
            "x-api-key": ANTHROPIC_API_KEY,
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

    if "error" in resp.json():
        # if anthropic told us details about what went wrong, use them
        # TODO somehow include json.response()['error']['type'] without going overboard
        raise Exception(resp.json()["error"]["message"])
    else:
        # fall back to returning normal HTTP errors
        resp.raise_for_status()

    return resp.json()["content"][0]["text"]


def _ocr_flyer_uncached(
    image: str | Path | bytes | IO[bytes], caption: str | None = None
):
    """Extract event info from a flyer image.

    Args:
        image: A file path (str/PathLike), raw bytes, or PIL Image.

    Returns:
        (title, date, ics_content) from the first event in the API response.
    """

    now = date.today()
    # add this to the prompt to debug things:
    # - reasoning: an explanation in plain english of your reasoning chain for selecting each value
    event = ask_claude_about_image(
        image,
        dedent(f"""
        Try to identify the event within this flyer. Determine the title and if available
        the date, time, location, price, performers, ticket or information URLs,
        and special instructions. {"There is a caption to help fill in missing details." if caption else ""}

        Dates and Times:
        Be aware it is possible for events to run overnight.
        Minimize |date - {now.strftime('%Y-%m-%d')}| and prefer shorter events (<= 24h) to longer ones.
        If the event appears to be far from now or appears to run for many days, consider possible typos
        or misreads in the OCR.

        Output:
        Return a JSON object with:

        - is_event: bool (REQUIRED)
        - title: string (REQUIRED)
        - date: YYYY-MM-DD (use {now.strftime('%Y')} if year not shown)
        - end_date: YYYY-MM-DD or null (for multi-day events)
        - start_time: HH:MM (24h) or null
        - end_time: HH:MM (24h) or null
        - location: venue/address or null
        - price: price or null
        - url: URL or null
        - performers: list[string] or null
        - description: Include other details not included in the other fields using the ORIGINAL wording from the flyer. If there are no other details, leave it null.

        Rules:
        - Every event MUST have a title
        - Response must be ONLY valid, parseable JSON.
        - Do NOT put the title, date, time, price, performers or location in the description.
        - Do NOT wrap the output in markdown code quotes.
        - Do NOT wrap the output in '```json'.
        - Do NOT include a preface nor summary.

        {"<caption>{caption}</caption>" if caption else ""}
    """).lstrip(),
    )

    # DEBUG
    # print(event)
    # print()

    # strip markdown code quotes (Haiku in particular seems to be a fan of these)
    event = event.strip()
    if event.startswith("```") and event.endswith("```"):
        event = "\n".join(event.split("\n")[1:-1])

    return event


def _ocr_flyer_cached(
    image: str | Path | bytes | IO[bytes], caption: str | None = None
):
    filename = None
    if isinstance(image, (str, Path)):
        filename = str(image)
    image = _load_bytes(image)

    # hashing the flyer lets us cache it so we don't burn lots of OCR cost
    flyer_hash = hashlib.sha256(image).hexdigest()
    os.makedirs(CACHE_DIR, exist_ok=True)
    json_path = os.path.join(CACHE_DIR, f"{flyer_hash}.json")
    exc_path = os.path.join(CACHE_DIR, f"{flyer_hash}.exc")

    if os.path.exists(exc_path):
        log.warn("Flyer has a cached exception %s", exc_path)
        with open(exc_path, "r") as fd:
            raise Exception(f"Cached error: {fd.readline()}")

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as fd:
            log.info(
                f"Loading OCR {"for " + filename + " " if filename else ""}from '{json_path}'"
            )
            event = fd.read()
    else:
        try:
            log.info("Asking Claude%s", (f" about {filename}" if filename else ""))
            event = _ocr_flyer_uncached(image, caption)
        except Exception as exc:
            with open(exc_path, "w") as fd:
                print(f"{exc}", file=fd)
                traceback.print_exc(file=fd)
            raise exc

        with open(json_path, "w", encoding="utf-8") as fd:
            log.info("Caching Claude's answer to %s", json_path)
            fd.write(event)

    try:
        # try to parse
        event = json.loads(event)
    except Exception as exc:
        raise ValueError(f"Claude returned malformed json:\n\n{event}") from exc

    if not event.get("is_event", False) or not event.get("date"):
        desc = event.get("description", "")
        raise NotEventError(desc)

    event["id"] = flyer_hash

    return event


def ocr_flyer(image: str | Path | bytes | IO[bytes], caption: str | None = None):
    event = _ocr_flyer_cached(image, caption)

    # (loose) Typechecks

    event["is_event"] = bool(event.get("is_event", False))

    for type, fmt, fields in [
        (date, "%Y-%m-%d", ["date", "end_date"]),
        (time, "%H:%M", ["start_time", "end_time"]),
    ]:
        for field in fields:
            # this makes sure
            #   - dates become datetime.date objects
            #   - times become datetime.time objects
            # - but missing or otherwise unparseable => None
            if event.get(field):
                value, event[field] = event[field], None
                try:
                    event[field] = type.strptime(value, fmt)
                except ValueError as exc:
                    log.warn("Unable to parse %s '%s': %s", type.__name__, value, exc)

    log.debug(event)
    # Fixup time
    dtstart, dtend = interpret_datetime(
        event.get("date"),
        event.get("end_date"),
        event.get("start_time"),
        event.get("end_time"),
    )

    for field in ["date", "end_date", "start_time", "end_time"]:
        if field in event:
            del event[field]

    event["dtstart"] = dtstart
    event["dtend"] = dtend

    log.debug(event)

    return event


def cap_image_size(image, size, jpeg_quality=85):
    """
    Re-scale image as a JPG to <= size
    """
    from PIL import Image  # import *here* to avoid the import cost until it's needed

    image = _load_bytes(image)
    img = Image.open(io.BytesIO(image)).convert("RGB")

    w, h = img.size

    while True:
        buffer = io.BytesIO()
        shrunk = img.resize((w, h), Image.LANCZOS)
        shrunk.save(buffer, format="JPEG", quality=jpeg_quality)
        Size = buffer.tell()

        if Size <= size:
            return buffer.getvalue()

        # In the given image (based on its inherent complexity) each pixel takes
        # on average Size/(w*h). We want to have an image that's size large, though,
        # If we scale both dimensions by some scale factor c and set:
        # Size * c <= size
        #        c <= size/Size
        #
        # If we pick c = size/Size * safety_margin ; (with 0 < margin < 1)
        # then we will will satisfy this without losing too much detail.
        # The safety_margin gives extra room in case our assumptions about the compressor aren't totally accurate.
        #
        # We then make the assumption that in the scaled image
        # each pixel will still take Size/(w*h) bytes on average,
        # and that we will scale it to keep the aspect ratio, so we scale width and
        # height by the same value sqrt(c).
        # Then the final size is
        # approximate inherent complexity of the given image, which means the final size is
        #    (Size)/(w*h) * (w*sqrt(c)) * (h*sqrt(c)) <= size
        #    Size*c <= size
        # as required
        #
        safety_margin = 0.95
        c = size / Size * safety_margin
        w, h = int(w * (c) ** (0.5)), int(h * (c) ** (0.5))
