from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.catalog.availability import apply_availability_overrides
from app.catalog.provider import DxRatingCatalogProvider
from app.catalog.service import ingest_catalog
from app.config import get_settings
from app.db.base import Base
from app.db.models import CatalogSnapshot
from app.db.session import SessionLocal, engine


async def sync_catalog() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        previous_etag = session.scalar(
            select(CatalogSnapshot.etag)
            .where(CatalogSnapshot.status == "published")
            .order_by(CatalogSnapshot.published_at.desc())
            .limit(1)
        )
        availability_path = settings.intl_overrides_path.with_name(
            "international_availability.json"
        )
        availability = (
            json.loads(availability_path.read_text(encoding="utf-8"))
            if availability_path.exists()
            else {"schemaVersion": 1, "overrides": []}
        )
        # Re-evaluate local corrections even when the upstream ETag has not changed.
        fetched = await DxRatingCatalogProvider(settings.dxrating_url).fetch(
            None if availability.get("overrides") else previous_etag
        )
        if fetched.status_code == 304:
            print("Catalog is unchanged (HTTP 304).")
            return
        if fetched.payload is None:
            raise RuntimeError("Catalog provider returned no payload")
        result = ingest_catalog(
            session,
            apply_availability_overrides(fetched.payload, availability),
            source_url=settings.dxrating_url,
            current_intl_version=settings.current_intl_version,
            overrides_path=settings.intl_overrides_path,
            raw_catalog_dir=settings.raw_catalog_dir,
            etag=fetched.etag,
        )
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(sync_catalog())
