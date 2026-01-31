"""Extract event details from flyer images using a vision API."""

import base64
import os

import requests


API_URL = "https://omarieclaire--60ed5100c6f711f08a6642dde27851f2.web.val.run/"
USER_AGENT = "icsmtl/0.1"


def _detect_media_type(data, filename=None):
    """Detect image media type from magic bytes, with filename extension as fallback."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"GIF8":
        return "image/gif"

    if filename is not None:
        ext = os.path.splitext(filename)[1].lower()
        ext_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        if ext in ext_map:
            return ext_map[ext]

    raise ValueError("Cannot detect image media type")


def _prepare_image(image):
    """Normalize image input to (raw_bytes, media_type).

    Accepts a file path (str/PathLike), raw bytes, or a PIL Image.
    """
    if isinstance(image, (str, os.PathLike)):
        path = os.fspath(image)
        with open(path, "rb") as f:
            data = f.read()
        return data, _detect_media_type(data, filename=path)

    if isinstance(image, bytes):
        return image, _detect_media_type(image)

    # Lazy PIL check to avoid hard dependency
    try:
        from PIL import Image
    except ImportError:
        raise TypeError(f"Unsupported image type: {type(image)}")

    if isinstance(image, Image.Image):
        import io

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue(), "image/png"

    raise TypeError(f"Unsupported image type: {type(image)}")


def extract_event_from_flyer(image):
    """Extract event info from a flyer image.

    Args:
        image: A file path (str/PathLike), raw bytes, or PIL Image.

    Returns:
        (title, date, ics_content) from the first event in the API response.
    """
    raw_bytes, media_type = _prepare_image(image)
    b64_str = base64.b64encode(raw_bytes).decode("ascii")

    resp = requests.post(
        API_URL,
        json={"type": "image", "mediaType": media_type, "imageData": b64_str},
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    resp.raise_for_status()

    result = resp.json()
    event = result["events"][0]
    return event["title"], event["date"], event["ics_content"]
