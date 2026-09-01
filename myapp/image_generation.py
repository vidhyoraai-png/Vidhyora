"""NVIDIA FLUX image generation and editing for the AI chat."""

import base64
import binascii
import io
import re
from dataclasses import dataclass

import requests
from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError


FLUX_API_URL = (
    "https://ai.api.nvidia.com/v1/genai/"
    "black-forest-labs/flux.2-klein-4b"
)
REQUEST_TIMEOUT_SECONDS = 120
MAX_PROMPT_CHARS = 10_000


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    extension: str


class ImageGenerationError(Exception):
    """A safe, user-facing failure from the image generation service."""

    def __init__(self, message, *, status_code=503):
        super().__init__(message)
        self.status_code = status_code


def _safe_error(response):
    status_code = response.status_code
    try:
        detail = str(response.json().get("detail", "")).lower()
    except (ValueError, AttributeError):
        detail = ""
    if status_code == 422 and "expected: example_id" in detail:
        return ImageGenerationError(
            "Image generation works, but uploading a photo to edit is currently under maintenance and will be back soon. Try describing a new image to generate instead.",
            status_code=400,
        )
    if status_code == 429:
        return ImageGenerationError(
            "The image-generation limit has been reached. Please wait and try again later.",
            status_code=429,
        )
    if status_code in (400, 413, 422):
        return ImageGenerationError(
            "NVIDIA could not process that prompt or image. Try a clear prompt and a smaller PNG or JPEG image.",
            status_code=400,
        )
    if status_code in (401, 403):
        return ImageGenerationError(
            "Image generation is not configured correctly right now. Please contact support.",
        )
    if status_code == 404:
        return ImageGenerationError(
            "The FLUX image model is not available for this NVIDIA account right now.",
        )
    return ImageGenerationError(
        "NVIDIA's image service is temporarily unavailable. Please try again in a moment.",
    )


def _api_key(*, editing=False):
    # Editing can use a separately entitled NVIDIA account/key while normal
    # prompt-to-image generation keeps its existing credential.
    setting_name = "NVIDIA_FLUX_EDIT_API_KEY" if editing else "NVIDIA_FLUX_API_KEY"
    return getattr(settings, setting_name, "").strip()


_IMAGE_DATA_URI_RE = re.compile(
    r"^data:image/(?:png|jpe?g|webp);base64,(?P<data>[A-Za-z0-9+/=\r\n]+)$",
    re.IGNORECASE,
)


def _normalize_source_image(data_uri):
    """Decode, orient, resize and re-encode a browser image for FLUX."""
    match = _IMAGE_DATA_URI_RE.fullmatch(data_uri or "")
    if not match:
        raise ImageGenerationError(
            "The attached image is not a valid PNG, JPEG, or WebP image.",
            status_code=400,
        )
    try:
        raw = base64.b64decode(match.group("data"), validate=True)
        with Image.open(io.BytesIO(raw)) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
    except (ValueError, binascii.Error, UnidentifiedImageError, OSError) as exc:
        raise ImageGenerationError(
            "The attached image could not be decoded. Try uploading it again as PNG or JPEG.",
            status_code=400,
        ) from exc

    image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    if image.mode != "RGB":
        # JPEG has no alpha channel. Flatten transparent pixels onto white so
        # they do not unexpectedly become black in the model input.
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        image = background.convert("RGB")

    encoded = b""
    for quality in (88, 78, 68, 58):
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        encoded = output.getvalue()
        if len(encoded) <= 600_000:
            break
    return "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")


def _decode_artifact(payload):
    artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
    artifact = artifacts[0] if artifacts and isinstance(artifacts[0], dict) else None
    finish_reason = artifact.get("finishReason") if artifact else None
    if finish_reason == "CONTENT_FILTERED":
        raise ImageGenerationError(
            "That image request was blocked by NVIDIA's content filter. Try a different prompt or image.",
            status_code=400,
        )
    if finish_reason == "ERROR":
        raise ImageGenerationError("NVIDIA could not generate that image. Please try again.")
    encoded = artifact.get("base64") if artifact else None
    if not isinstance(encoded, str) or not encoded:
        raise ImageGenerationError("NVIDIA returned no image. Please try again.")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ImageGenerationError("NVIDIA returned an unreadable image. Please try again.")
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        extension = "png"
    elif content.startswith(b"\xff\xd8\xff"):
        extension = "jpg"
    elif content.startswith((b"RIFF",)) and content[8:12] == b"WEBP":
        extension = "webp"
    else:
        raise ImageGenerationError("NVIDIA returned an unsupported image format. Please try again.")
    return GeneratedImage(content=content, extension=extension)


def generate_image(prompt, source_image=None):
    """Generate an image, or edit ``source_image`` when one is supplied.

    ``source_image`` is the browser-provided PNG/JPEG data URI. It is decoded
    and normalized before being placed in FLUX's reference-image array.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ImageGenerationError(
            "Describe the image you want to generate or how you want the attached image changed.",
            status_code=400,
        )
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ImageGenerationError("That image prompt is too long.", status_code=400)

    editing = bool(source_image)
    key = _api_key(editing=editing)
    if not key:
        setting_name = "NVIDIA_FLUX_EDIT_API_KEY" if editing else "NVIDIA_FLUX_API_KEY"
        raise ImageGenerationError(
            f"Image generation is not configured yet. Set {setting_name} on the server.",
        )

    body = {
        "prompt": prompt,
        "width": 1024,
        "height": 1024,
        "steps": 4,
        "samples": 1,
        "seed": 0,
    }
    if editing:
        # FLUX.2 supports multiple references; NVIDIA's current hosted
        # request template therefore expects an array even for one image.
        body["image"] = [_normalize_source_image(source_image)]

    try:
        response = requests.post(
            FLUX_API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise ImageGenerationError(
            "Could not reach NVIDIA's image service. Please try again."
        ) from exc

    if response.status_code != 200:
        raise _safe_error(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise ImageGenerationError("NVIDIA returned an invalid response. Please try again.") from exc
    return _decode_artifact(payload)
