from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .config import settings


class FoundationClient:
    @property
    def enabled(self) -> bool:
        return bool(settings.foundation_api_key)

    @property
    def headers(self) -> dict[str, str]:
        return {"X-App-Id": settings.foundation_app_id,
                "X-API-Key": settings.foundation_api_key}

    async def analyze(self, image: Path, question: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=settings.foundation_timeout) as client:
            upload = await client.post(f"{settings.foundation_base_url}/foundation/v1/images",
                                       headers={**self.headers, "Content-Type": self._media_type(image)},
                                       content=image.read_bytes())
            upload.raise_for_status()
            remote_id = upload.json()["image_id"]
            response = await client.post(f"{settings.foundation_base_url}/foundation/v1/vision/analyze",
                                         headers=self.headers,
                                         json={"image_id": remote_id, "scene": "tire_customer_service",
                                               "question": question})
            response.raise_for_status()
            return response.json()["data"]

    @staticmethod
    def _media_type(path: Path) -> str:
        return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp"}[path.suffix.lower()]
