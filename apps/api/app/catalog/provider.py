from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class FetchResult:
    status_code: int
    etag: str | None
    payload: Any | None


class DxRatingCatalogProvider:
    def __init__(self, url: str, timeout_seconds: float = 30.0) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds

    async def fetch(self, previous_etag: str | None = None) -> FetchResult:
        headers = {"Accept": "application/json", "User-Agent": "MaiUp/0.1 catalog-sync"}
        if previous_etag:
            headers["If-None-Match"] = previous_etag
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(self.url, headers=headers)
        if response.status_code == 304:
            return FetchResult(status_code=304, etag=previous_etag, payload=None)
        response.raise_for_status()
        return FetchResult(
            status_code=response.status_code,
            etag=response.headers.get("etag"),
            payload=response.json(),
        )


class JsonCatalogProvider(DxRatingCatalogProvider):
    """Fetch an auxiliary JSON catalog without relying on conditional requests."""

    async def fetch(self) -> FetchResult:
        return await super().fetch()
