"""Two-stage pipeline: LM Studio vision describes the photo, Jev picks the bin."""

from __future__ import annotations

import base64
import io
import json
import os
import re

import httpx
from PIL import Image

from .bins import FALLBACK_ID, BinItem

LMSTUDIO_BASE_URL = os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL = os.environ.get("LMSTUDIO_MODEL", "")
LMSTUDIO_TIMEOUT = float(os.environ.get("LMSTUDIO_TIMEOUT", "180"))
JEV_TIMEOUT = float(os.environ.get("JEV_TIMEOUT", "60"))

VISION_FIELDS = ["object", "material", "labels", "residue", "condition"]

VISION_PROMPT = (
    "Look at this photo of one waste item. Describe it for a recycling sorter. "
    "Return JSON with exactly these string fields: "
    "object (what the item is), material (primary material), "
    "labels (visible brand or recycling labels, or 'none'), "
    "residue (food or liquid residue: none, light, or heavy, and what), "
    "condition (clean, dirty, broken, etc.). "
    "Use an empty string for anything you cannot tell. Return JSON only."
)

VISION_SCHEMA = {
    "name": "item_description",
    "schema": {
        "type": "object",
        "properties": {field: {"type": "string"} for field in VISION_FIELDS},
        "required": VISION_FIELDS,
        "additionalProperties": False,
    },
}

CLASSIFY_INSTRUCTIONS = (
    "Which trash bin should this item go into? Judge only the described item "
    "against each bin's rules, weighing material, residue, and condition."
)

FALLBACK_RULES = (
    "None of the listed bins fit this item, or the description is too unclear "
    "to decide."
)


class PipelineError(RuntimeError):
    """A stage of the pipeline failed with a message safe to show the user."""


def lmstudio_model() -> str:
    """Configured model id, or the first model the server has loaded."""
    if LMSTUDIO_MODEL:
        return LMSTUDIO_MODEL
    try:
        response = httpx.get(f"{LMSTUDIO_BASE_URL}/models", timeout=10)
        response.raise_for_status()
        models = response.json().get("data", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise PipelineError(f"LM Studio is not reachable at {LMSTUDIO_BASE_URL}") from exc
    if not models:
        raise PipelineError("LM Studio has no model loaded")
    return models[0]["id"]


def prepare_image(image_bytes: bytes) -> bytes:
    """Downscale to a vision-friendly JPEG."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        raise PipelineError("Could not read that photo; try a JPEG or PNG.") from exc
    image = image.convert("RGB")
    image.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _vision_payload(image_b64: str, model: str, structured: bool) -> dict:
    payload: dict = {
        "model": model,
        "temperature": 0,
        "max_tokens": 500,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
    }
    if structured:
        payload["response_format"] = {"type": "json_schema", "json_schema": VISION_SCHEMA}
    return payload


def _parse_vision_content(content: str) -> dict:
    text = content.strip()
    candidates = [text]
    # Fenced JSON block anywhere in the text (reasoning models chat first).
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        candidates.append(fence.group(1))
    # First { through last } span.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    last_error: ValueError | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except ValueError as exc:
            last_error = exc
            continue
        if isinstance(data, dict):
            return {field: str(data.get(field, "")) for field in VISION_FIELDS}
    raise PipelineError("The vision model returned an unreadable description.") from last_error


def describe_item(image_bytes: bytes) -> dict:
    """Ask the local vision model for a structured description of the item."""
    jpeg = prepare_image(image_bytes)
    image_b64 = base64.b64encode(jpeg).decode("ascii")
    model = lmstudio_model()
    last_error: Exception | None = None
    for structured in (True, False):
        try:
            response = httpx.post(
                f"{LMSTUDIO_BASE_URL}/chat/completions",
                json=_vision_payload(image_b64, model, structured),
                timeout=LMSTUDIO_TIMEOUT,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return _parse_vision_content(content)
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            last_error = exc
            continue
    raise PipelineError(f"LM Studio vision request failed: {last_error}") from last_error


def jev_api_key() -> str | None:
    return os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")


def classify_item(description: dict, bins: list[BinItem]) -> dict:
    """Ask Jev which configured bin the described item belongs in."""
    from typesafe_sdk import Choice, TypeSafeClient

    key = jev_api_key()
    if not key:
        raise PipelineError("No Jev API key configured (TYPESAFE_API_KEY / JEV_API_KEY).")
    criteria = {b.id: f"{b.name}. {b.rules}".strip() for b in bins}
    criteria[FALLBACK_ID] = FALLBACK_RULES
    try:
        with TypeSafeClient(api_key=key, timeout=JEV_TIMEOUT) as client:
            response = client.system_one(
                state={"item": description},
                questions={
                    "bin": Choice(
                        instructions=CLASSIFY_INSTRUCTIONS,
                        criteria=criteria,
                    )
                },
            )
    except TypeError:
        # Older SDKs without a timeout kwarg.
        with TypeSafeClient(api_key=key) as client:
            response = client.system_one(
                state={"item": description},
                questions={
                    "bin": Choice(
                        instructions=CLASSIFY_INSTRUCTIONS,
                        criteria=criteria,
                    )
                },
            )
    except Exception as exc:
        raise PipelineError(f"Jev request failed: {exc}") from exc
    answer = response.choices["bin"]
    choice = getattr(answer, "choice", None)
    probabilities = getattr(answer, "probabilities", None) or {}
    confidence = getattr(answer, "confidence", None)
    if choice is None or not probabilities:
        raise PipelineError("Jev returned an unexpected answer shape.")
    if confidence is None:
        confidence = max(probabilities.values())
    return {
        "choice": choice,
        "confidence": float(confidence),
        "probabilities": {k: float(v) for k, v in probabilities.items()},
    }
