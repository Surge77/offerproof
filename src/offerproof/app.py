"""Local web app: one page and one JSON endpoint. Meant to run on 127.0.0.1 only."""

from dataclasses import asdict
from importlib import resources
import os
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from offerproof.extract import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, OllamaExtractor
from offerproof.verdict import MAX_MESSAGE_CHARS, Extractor, check


class CheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    use_model: bool = True


def default_extractor() -> Extractor:
    return OllamaExtractor(
        base_url=os.environ.get("OFFERPROOF_OLLAMA_URL", DEFAULT_OLLAMA_URL),
        model=os.environ.get("OFFERPROOF_MODEL", DEFAULT_MODEL),
    )


def create_app(make_extractor: Callable[[], Extractor] = default_extractor) -> FastAPI:
    app = FastAPI(title="OfferProof", docs_url=None, redoc_url=None)
    extractor = make_extractor()
    page = resources.files("offerproof").joinpath("static", "index.html").read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return page

    @app.post("/api/check")
    async def check_offer(request: CheckRequest) -> dict[str, Any]:
        # The model call blocks for seconds; keep it off the event loop.
        result = await run_in_threadpool(check, request.text, extractor if request.use_model else None)
        return asdict(result)

    return app
