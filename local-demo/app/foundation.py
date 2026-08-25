from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import httpx

from .config import settings


class FoundationClient:
    @property
    def enabled(self) -> bool:
        return bool(settings.foundation_api_key or settings.vision_model)

    @property
    def backend(self) -> str:
        return "foundation" if settings.foundation_api_key else "ollama"

    async def available(self) -> bool:
        if not self.enabled:
            return False
        if settings.foundation_api_key:
            return True
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                tags = await client.get(f"{settings.ollama_base_url}/api/tags")
                version = await client.get(f"{settings.ollama_base_url}/api/version")
            tags.raise_for_status()
            version.raise_for_status()
            version_parts = tuple(
                int(part) for part in version.json().get("version", "0.0.0").split(".")[:3]
            )
            model_present = any(
                model.get("name") == settings.vision_model
                for model in tags.json().get("models", [])
            )
            return model_present and version_parts >= (0, 12, 0)
        except Exception:
            return False

    @property
    def headers(self) -> dict[str, str]:
        return {"X-App-Id": settings.foundation_app_id,
                "X-API-Key": settings.foundation_api_key}

    async def analyze(self, image: Path, question: str) -> dict[str, Any]:
        if not settings.foundation_api_key:
            return await self._analyze_with_ollama(image, question)

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

    async def _analyze_with_ollama(self, image: Path, question: str) -> dict[str, Any]:
        prompt = f"""你是轮胎售后视觉检测助手。请分析图片并结合用户问题返回严格 JSON，不要输出 Markdown。
用户问题：{question}
JSON字段：summary（中文图片摘要）、detections（对象数组，每项含label）、ocr_blocks（文字数组，每项含text）、safety_risks（风险字符串数组）。
只描述图片中确实可见的内容；无法确认时明确写无法确认，不得臆测轮胎规格、损伤或品牌。"""
        payload = {
            "model": settings.vision_model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [base64.b64encode(image.read_bytes()).decode("ascii")],
            }],
            "format": "json",
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 700},
        }
        async with httpx.AsyncClient(timeout=settings.foundation_timeout) as client:
            response = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
            response.raise_for_status()
            content = response.json()["message"]["content"].strip()
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("Vision model returned a non-object response")
        return result

    @staticmethod
    def _media_type(path: Path) -> str:
        return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp"}[path.suffix.lower()]
