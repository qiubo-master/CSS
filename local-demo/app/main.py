from __future__ import annotations

import json
import asyncio
import time
import uuid
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from .config import ROOT, settings
from .graph import TireServiceGraph
from .repositories import KnowledgeRepository, MockRepository
from .foundation import FoundationClient
from .schemas import (
    CreateConversationRequest,
    CreateConversationResponse,
    MessageRequest,
    MessageResponse,
    OrderQuery,
    ProductQuery,
)


app = FastAPI(title="轮胎智能客服本地 Demo", version="0.1.0")
repo = MockRepository(settings.data_dir)
knowledge = KnowledgeRepository(settings.data_dir)
workflow = TireServiceGraph(repo, knowledge)
foundation = FoundationClient()
conversations: dict[str, dict[str, Any]] = {}
message_cache: dict[str, MessageResponse] = {}
UPLOAD_DIR = settings.data_dir / "uploads"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": (".webp", (b"RIFF",)),
}


@app.get("/")
async def index():
    return FileResponse(ROOT / "app" / "web" / "index.html")


@app.get("/api/v1/health")
async def health():
    return {
        "status": "ok",
        "llm_mode": settings.llm_mode,
        "ollama_available": await workflow.llm.available(),
        "chat_model": settings.chat_model,
        "vision_backend": foundation.backend if foundation.enabled else "disabled",
        "vision_model": settings.vision_model if foundation.enabled and foundation.backend == "ollama" else None,
        "vision_available": await foundation.available(),
        "vector_backend": "ollama-vector-json" if knowledge.vectors else "lexical-fallback (Milvus adapter boundary)",
        "mock_counts": {
            "customers": len(repo.customers), "vehicles": len(repo.vehicles),
            "products": len(repo.products), "orders": len(repo.orders),
            "knowledge_chunks": len(knowledge.chunks),
        },
    }


@app.post("/api/v1/uploads/images", status_code=201)
async def upload_image(
    request: Request,
    content_type: str | None = Header(default=None),
    x_filename: str | None = Header(default=None),
):
    media_type = (content_type or "").split(";", 1)[0].lower()
    image_type = IMAGE_TYPES.get(media_type)
    if not image_type:
        raise HTTPException(415, "Only JPEG, PNG and WebP images are supported")

    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Image exceeds the 10 MB limit")
    if not content:
        raise HTTPException(400, "Image is empty")

    suffix, signatures = image_type
    if media_type == "image/webp":
        valid_signature = content.startswith(signatures[0]) and content[8:12] == b"WEBP"
    else:
        valid_signature = any(content.startswith(signature) for signature in signatures)
    if not valid_signature:
        raise HTTPException(400, "File content does not match its image type")

    image_id = f"img_{uuid.uuid4().hex}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / f"{image_id}{suffix}"
    target.write_bytes(content)
    safe_name = Path(x_filename or target.name).name[:160]
    return {
        "image_id": image_id,
        "filename": safe_name,
        "content_type": media_type,
        "size": len(content),
        "url": f"/api/v1/uploads/images/{image_id}",
        "vision_status": "ready" if await foundation.available() else "unavailable",
    }


@app.get("/api/v1/uploads/images/{image_id}")
async def get_uploaded_image(image_id: str):
    if not re.fullmatch(r"img_[0-9a-f]{32}", image_id):
        raise HTTPException(404, "Image not found")
    matches = list(UPLOAD_DIR.glob(f"{image_id}.*")) if UPLOAD_DIR.exists() else []
    if len(matches) != 1 or matches[0].suffix not in {".jpg", ".png", ".webp"}:
        raise HTTPException(404, "Image not found")
    return FileResponse(matches[0])


@app.post("/api/v1/conversations", response_model=CreateConversationResponse)
async def create_conversation(body: CreateConversationRequest):
    if not repo.get_customer(body.customer_id):
        raise HTTPException(404, "Mock customer not found")
    cid = f"c_{uuid.uuid4().hex[:12]}"
    conversations[cid] = {"customer_id": body.customer_id, "messages": [], "created_at": time.time()}
    return CreateConversationResponse(conversation_id=cid, customer_id=body.customer_id)


@app.post("/api/v1/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(conversation_id: str, body: MessageRequest):
    conversation = conversations.get(conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    missing_images = [
        image_id for image_id in body.image_ids
        if not re.fullmatch(r"img_[0-9a-f]{32}", image_id)
        or not any(UPLOAD_DIR.glob(f"{image_id}.*"))
    ]
    if missing_images:
        raise HTTPException(400, {"message": "Unknown image attachment", "image_ids": missing_images})
    cache_key = f"{conversation_id}:{body.message_id}"
    if cache_key in message_cache:
        return message_cache[cache_key]
    trace_id = f"tr_{uuid.uuid4().hex[:12]}"
    visual_results = []
    visual_error = None
    if body.image_ids and foundation.enabled:
        try:
            for image_id in body.image_ids:
                image_path = next(UPLOAD_DIR.glob(f"{image_id}.*"))
                visual_results.append(await foundation.analyze(image_path, body.text))
        except Exception as exc:
            visual_error = f"{type(exc).__name__}: {exc}"
    visual_result = visual_results[0] if visual_results else {}
    result = await workflow.invoke(body.text, conversation["customer_id"], trace_id, visual_result)
    response = MessageResponse(
        answer_id=f"a_{uuid.uuid4().hex[:12]}",
        conversation_id=conversation_id,
        status=result.get("status", "completed"),
        intent=result.get("intent", "unknown"),
        answer=result.get("answer", ""),
        citations=result.get("citations", []),
        handoff_id=result.get("handoff_id"),
        trace_id=trace_id,
        timings_ms=result.get("timings_ms", {}),
        debug={
            "route": result.get("route", {}),
            "evidence_count": len(result.get("evidence", [])),
            "image_ids": body.image_ids,
            "vision_status": ("completed" if visual_results else "degraded" if body.image_ids else "not_requested"),
            "vision_results": visual_results,
            "vision_error": visual_error,
        },
    )
    conversation["messages"].append({"role": "user", "text": body.text, "image_ids": body.image_ids})
    conversation["messages"].append({"role": "assistant", "text": response.answer})
    message_cache[cache_key] = response
    return response


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/v1/conversations/{conversation_id}/messages/stream")
async def stream_message(conversation_id: str, body: MessageRequest):
    if conversation_id not in conversations:
        raise HTTPException(404, "Conversation not found")

    async def events():
        yield _sse("message.accepted", {"conversation_id": conversation_id, "message_id": body.message_id})
        yield _sse("tool.status", {"stage": "routing", "message": "正在识别意图并检索信息"})
        try:
            result = await send_message(conversation_id, body)
        except Exception as exc:
            yield _sse("answer.error", {
                "code": "generation_failed",
                "message": "本次回答生成失败，请稍后重试",
                "detail": type(exc).__name__,
            })
            return
        yield _sse("tool.status", {"stage": "verified", "message": "答案已通过业务规则校验"})
        text = result.answer
        chunk_size = 6
        for offset in range(0, len(text), chunk_size):
            yield _sse("answer.delta", {"text": text[offset:offset + chunk_size]})
            await asyncio.sleep(0.025)
        for citation in result.citations:
            yield _sse("citation", citation.model_dump())
        yield _sse("answer.completed", {
            "answer_id": result.answer_id,
            "status": result.status,
            "intent": result.intent,
            "handoff_id": result.handoff_id,
            "trace_id": result.trace_id,
            "timings_ms": result.timings_ms,
            "debug": result.debug,
        })

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/mock/customers/{customer_id}")
async def mock_customer(customer_id: str):
    item = repo.get_customer(customer_id)
    if not item:
        raise HTTPException(404, "Customer not found")
    return item


@app.get("/mock/customers/{customer_id}/vehicles")
async def mock_vehicles(customer_id: str):
    return [x for x in repo.vehicles if x["customer_id"] == customer_id]


@app.post("/mock/search/products")
async def mock_products(body: ProductQuery):
    return {"hits": repo.search_products(body.model_dump(exclude_none=True), body.brand)}


@app.post("/mock/orders/query")
async def mock_orders(body: OrderQuery):
    return {"hits": repo.orders_for(body.customer_id, body.order_id)}


@app.post("/mock-es/{index_name}/_search")
async def mock_es(index_name: str, body: dict[str, Any]):
    size = min(int(body.get("size", 10)), 50)
    mapping = {
        "tire_product_current": repo.products,
        "tire_price_current": repo.prices,
        "tire_order_current": repo.orders,
        "tire_campaign_current": repo.campaigns,
    }
    if index_name not in mapping:
        raise HTTPException(404, "Mock index not found")
    rows = mapping[index_name]
    filters = body.get("query", {}).get("bool", {}).get("filter", [])
    for item in filters:
        if "term" in item:
            key, value = next(iter(item["term"].items()))
            rows = [x for x in rows if x.get(key) == value]
        elif "terms" in item:
            key, values = next(iter(item["terms"].items()))
            rows = [x for x in rows if x.get(key) in values]
    return {"hits": {"total": {"value": len(rows), "relation": "eq"}, "hits": [{"_source": x} for x in rows[:size]]}}
