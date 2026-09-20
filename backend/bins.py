"""Bin configuration: load, validate, and persist the trash-can taxonomy."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

BINS_PATH = Path(__file__).resolve().parent / "bins.json"

# Appended automatically to every Jev Choice; never part of the stored config.
FALLBACK_ID = "other"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class BinItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    rules: str = Field(default="", max_length=4000)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if value == FALLBACK_ID:
            raise ValueError(f'"{FALLBACK_ID}" is reserved for the unsure fallback')
        if not _ID_RE.match(value):
            raise ValueError("id must be lowercase letters, digits, - or _")
        return value


DEFAULT_BINS = [
    BinItem(
        id="recycle",
        name="Recycle",
        rules="Clean paper, cardboard, metal cans, glass bottles and jars, and rigid "
        "plastics marked recyclable. Must be empty, clean, and dry.",
    ),
    BinItem(
        id="compost",
        name="Compost / Organics",
        rules="Food scraps, food-soiled paper and cardboard, coffee grounds, and yard "
        "trimmings. No plastics, glass, or metal.",
    ),
    BinItem(
        id="landfill",
        name="Landfill",
        rules="Anything that fits no other bin: chip bags, candy wrappers, styrofoam, "
        "broken ceramics, and other non-recyclable, non-compostable waste.",
    ),
    BinItem(
        id="hazardous",
        name="Hazardous / Special",
        rules="Batteries, electronics, paint, chemicals, light bulbs, and medical waste. "
        "These need a drop-off point, never a curbside can.",
    ),
]


def load_bins() -> list[BinItem]:
    """Read the configured bins, falling back to defaults when missing."""
    if not BINS_PATH.is_file():
        return list(DEFAULT_BINS)
    data = json.loads(BINS_PATH.read_text())
    return [BinItem(**item) for item in data["bins"]]


def save_bins(bins: list[BinItem]) -> list[BinItem]:
    """Validate and persist the bins. Needs at least one bin, unique ids."""
    if not bins:
        raise ValueError("at least one bin is required")
    ids = [b.id for b in bins]
    if len(set(ids)) != len(ids):
        raise ValueError("bin ids must be unique")
    BINS_PATH.write_text(
        json.dumps({"bins": [b.model_dump() for b in bins]}, indent=2) + "\n"
    )
    return bins


def reset_bins() -> list[BinItem]:
    """Restore the generic default set."""
    return save_bins(list(DEFAULT_BINS))
