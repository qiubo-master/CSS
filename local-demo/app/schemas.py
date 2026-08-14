from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    customer_id: str = "u_001"
    channel: str = "web"


class CreateConversationResponse(BaseModel):
    conversation_id: str
    customer_id: str


class MessageRequest(BaseModel):
    message_id: str
    text: str = Field(min_length=1, max_length=2000)
    image_ids: list[str] = Field(default_factory=list, max_length=4)


class Citation(BaseModel):
    evidence_id: str
    source: str
    title: str
    updated_at: str | None = None


class MessageResponse(BaseModel):
    answer_id: str
    conversation_id: str
    status: Literal["completed", "need_clarification", "handoff"]
    intent: str
    answer: str
    citations: list[Citation] = []
    handoff_id: str | None = None
    trace_id: str
    timings_ms: dict[str, float] = {}
    debug: dict[str, Any] = {}


class ProductQuery(BaseModel):
    width_mm: int | None = None
    aspect_ratio: int | None = None
    rim_inch: int | None = None
    brand: str | None = None
    region_id: str = "shanghai"


class OrderQuery(BaseModel):
    customer_id: str
    order_id: str | None = None

