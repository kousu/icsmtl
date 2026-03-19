import io
from pathlib import Path
import unicodedata
from typing import IO


def sanitize_title(title):
    """Sanitize a title for use in filenames."""
    name = unicodedata.normalize("NFKD", title)
    name = name.encode("ascii", "ignore").decode("ascii")
    return name.replace(" ", "_").replace("/", "_")


def make_filename(event):
    """Build filename as {YYYY-MM-DD}-{sanitized_title}.ics."""
    title = sanitize_title(event["title"])
    if event.get("date"):
        date = event["date"].strftime("%Y-%m-%d")
        return f"{date}-{title}.ics"
    else:
        return f"{title}.ics"


def _load_bytes(data: str | Path | bytes | IO[bytes]) -> bytes:
    """
    Get the contents of data whatever form it's in:
    - if a string (or Path), assume it's a path and load it
    - if it's a file object, read it
    - if it's already bytes, return it
    """
    if isinstance(data, str) or isinstance(data, Path):
        with open(data, "rb") as data:
            data = data.read()
    elif isinstance(data, (io.RawIOBase, io.BufferedIOBase)):
        data = data.read()
    assert isinstance(
        data, bytes
    ), "At this point, data should have been coerced to bytes"
    return data
