"""Trash-can classifier API: photo in, bin decision out."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Imported after load_dotenv so LMSTUDIO_* / Jev keys from .env are visible
# to pipeline's module-level defaults.
from .bins import BinItem, load_bins, reset_bins, save_bins  # noqa: E402
from .pipeline import (  # noqa: E402
    FALLBACK_ID,
    PipelineError,
    classify_item,
    describe_item,
    jev_api_key,
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
FALLBACK_NAME = "Other / unsure"

app = FastAPI(title="Trash-can classifier")


class BinsBody(BaseModel):
    bins: list[BinItem]


class Probability(BaseModel):
    id: str
    name: str
    p: float


class ClassifyResponse(BaseModel):
    bin_id: str
    bin_name: str
    confidence: float
    runner_up: Probability | None
    probabilities: list[Probability]
    description: dict


def _display_name(bin_id: str, bins: list[BinItem]) -> str:
    if bin_id == FALLBACK_ID:
        return FALLBACK_NAME
    return next((b.name for b in bins if b.id == bin_id), bin_id)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "jev_configured": bool(jev_api_key()),
        "bins": len(load_bins()),
    }


@app.get("/api/bins")
def get_bins() -> dict:
    return {"bins": [b.model_dump() for b in load_bins()]}


@app.put("/api/bins")
def put_bins(body: BinsBody) -> dict:
    try:
        saved = save_bins(body.bins)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"bins": [b.model_dump() for b in saved]}


@app.post("/api/bins/reset")
def post_bins_reset() -> dict:
    return {"bins": [b.model_dump() for b in reset_bins()]}


@app.post("/api/classify", response_model=ClassifyResponse)
def post_classify(image: UploadFile = File(...)) -> ClassifyResponse:
    if not (image.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload a photo (JPEG/PNG).")
    raw = image.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Photo is too large (max 10 MB).")
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload.")
    try:
        bins = load_bins()
        description = describe_item(raw)
        result = classify_item(description, bins)
    except PipelineError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    ranked = sorted(result["probabilities"].items(), key=lambda kv: kv[1], reverse=True)
    probabilities = [
        Probability(id=bid, name=_display_name(bid, bins), p=p) for bid, p in ranked
    ]
    runner_up = probabilities[1] if len(probabilities) > 1 else None
    return ClassifyResponse(
        bin_id=result["choice"],
        bin_name=_display_name(result["choice"], bins),
        confidence=result["confidence"],
        runner_up=runner_up,
        probabilities=probabilities,
        description=description,
    )


DIST = ROOT / "frontend" / "dist"


@app.get("/{full_path:path}")
def frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    if DIST.is_dir():
        candidate = DIST / full_path if full_path else DIST / "index.html"
        if full_path and candidate.is_file() and DIST in candidate.resolve().parents:
            return FileResponse(candidate)
        index = DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
    return JSONResponse(
        {"message": "API is running. Build the frontend: cd frontend && npm install && npm run build"}
    )


def main() -> None:
    import uvicorn

    host = os.environ.get("TRASHCAN_HOST", "127.0.0.1")
    port = int(os.environ.get("TRASHCAN_PORT", "8000"))
    cert = os.environ.get("TRASHCAN_TLS_CERT") or None
    key = os.environ.get("TRASHCAN_TLS_KEY") or None
    if bool(cert) != bool(key):
        raise SystemExit("Set both TRASHCAN_TLS_CERT and TRASHCAN_TLS_KEY, or neither.")
    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        ssl_certfile=cert,
        ssl_keyfile=key,
    )


if __name__ == "__main__":
    main()
