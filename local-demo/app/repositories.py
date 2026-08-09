from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
import httpx


class MockRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.customers = self._load("customers.json")
        self.vehicles = self._load("vehicles.json")
        self.products = self._load("tire_products.json")
        self.prices = self._load("tire_prices.json")
        self.orders = self._load("orders.json")
        self.campaigns = self._load("campaigns.json")

    def _load(self, name: str) -> list[dict[str, Any]]:
        with (self.data_dir / name).open("r", encoding="utf-8") as f:
            return json.load(f)

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        return next((x for x in self.customers if x["customer_id"] == customer_id), None)

    def get_vehicle(self, customer_id: str) -> dict[str, Any] | None:
        return next((x for x in self.vehicles if x["customer_id"] == customer_id), None)

    def search_products(self, spec: dict[str, int], brand: str | None = None) -> list[dict[str, Any]]:
        hits = []
        for p in self.products:
            if any(spec.get(k) and p.get(k) != spec[k] for k in ("width_mm", "aspect_ratio", "rim_inch")):
                continue
            if brand and brand.lower() not in p["brand"].lower():
                continue
            hits.append(p)
        return hits[:5]

    def prices_for(self, sku_ids: list[str], region_id: str) -> list[dict[str, Any]]:
        return [x for x in self.prices if x["sku_id"] in sku_ids and x["region_id"] == region_id]

    def orders_for(self, customer_id: str, order_id: str | None = None) -> list[dict[str, Any]]:
        return [
            x for x in self.orders
            if x["customer_id"] == customer_id and (order_id is None or x["order_id"] == order_id)
        ]

    def active_campaigns(self, region_id: str) -> list[dict[str, Any]]:
        return [x for x in self.campaigns if region_id in x["region_ids"] and x["status"] == "active"]


class KnowledgeRepository:
    """Small local vector-store substitute; interface is intentionally Milvus-shaped."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        with (data_dir / "knowledge_chunks.json").open("r", encoding="utf-8") as f:
            self.chunks: list[dict[str, Any]] = json.load(f)
        vector_path = data_dir / "knowledge_vectors.json"
        self.vectors: dict[str, list[float]] = {}
        if vector_path.exists():
            with vector_path.open("r", encoding="utf-8") as f:
                self.vectors = json.load(f)

    @staticmethod
    def _tokens(text: str) -> set[str]:
        normalized = text.lower().replace("/", " ").replace("r", " r")
        grams = {normalized[i:i + 2] for i in range(max(0, len(normalized) - 1))}
        words = set(normalized.split())
        return {x for x in grams | words if x.strip()}

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        q = self._tokens(query)
        scored = []
        for chunk in self.chunks:
            c = self._tokens(chunk["content"] + " " + " ".join(chunk.get("keywords", [])))
            score = len(q & c) / max(1, len(q))
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{**chunk, "score": round(score, 4)} for score, chunk in scored[:top_k]]

    async def search_async(self, query: str, base_url: str, model: str, top_k: int = 3) -> list[dict[str, Any]]:
        if not self.vectors:
            return self.search(query, top_k)
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(f"{base_url}/api/embed", json={"model": model, "input": query})
                response.raise_for_status()
                query_vector = response.json()["embeddings"][0]
        except Exception:
            return self.search(query, top_k)
        qnorm = math.sqrt(sum(x * x for x in query_vector)) or 1.0
        scored = []
        by_id = {x["chunk_id"]: x for x in self.chunks}
        for chunk_id, vector in self.vectors.items():
            if chunk_id not in by_id or len(vector) != len(query_vector):
                continue
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            score = sum(a * b for a, b in zip(query_vector, vector)) / (qnorm * norm)
            scored.append((score, by_id[chunk_id]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{**chunk, "score": round(score, 4)} for score, chunk in scored[:top_k]]
