from __future__ import annotations

import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .llm import LocalLLM
from .config import settings
from .repositories import KnowledgeRepository, MockRepository


class GraphState(TypedDict, total=False):
    text: str
    customer_id: str
    trace_id: str
    route: dict[str, Any]
    intent: str
    evidence: list[dict[str, Any]]
    answer: str
    status: str
    handoff_id: str | None
    citations: list[dict[str, Any]]
    timings_ms: dict[str, float]
    visual_result: dict[str, Any]
    visual_context: str


class TireServiceGraph:
    def __init__(self, repo: MockRepository, knowledge: KnowledgeRepository):
        self.repo = repo
        self.knowledge = knowledge
        self.llm = LocalLLM()
        self.graph = self._build()

    def _build(self):
        builder = StateGraph(GraphState)
        builder.add_node("risk_guard", self.risk_guard)
        builder.add_node("route", self.route)
        builder.add_node("retrieve", self.retrieve)
        builder.add_node("generate", self.generate)
        builder.add_node("handoff", self.handoff)
        builder.add_node("verify", self.verify)
        builder.add_node("visual_context", self.visual_context)
        builder.add_edge(START, "visual_context")
        builder.add_edge("visual_context", "risk_guard")
        builder.add_conditional_edges("risk_guard", self.after_risk, {"handoff": "handoff", "verify": "verify", "route": "route"})
        builder.add_conditional_edges("route", self.after_route, {"handoff": "handoff", "retrieve": "retrieve"})
        builder.add_edge("retrieve", "generate")
        builder.add_edge("generate", "verify")
        builder.add_edge("verify", END)
        builder.add_edge("handoff", END)
        return builder.compile()

    async def visual_context(self, state: GraphState) -> GraphState:
        visual = state.get("visual_result") or {}
        if not visual:
            return {}
        detections = visual.get("detections", [])
        blocks = visual.get("ocr_blocks", visual.get("ocr", []))
        summary = visual.get("summary") or visual.get("description") or ""
        labels = [str(item.get("label", "")) for item in detections[:12] if item.get("label")]
        texts = [str(item.get("text", "")) for item in blocks[:20] if item.get("text")]
        context = f"图像识别摘要：{summary}；检测对象：{', '.join(labels)}；OCR文字：{' '.join(texts)}"
        return {"visual_context": context, "text": f"{state['text']}\n{context}"}

    async def risk_guard(self, state: GraphState) -> GraphState:
        text = state["text"]
        high_risk = any(k in text for k in ("退款", "退货", "退钱", "投诉", "人工"))
        safety = any(k in text for k in ("鼓包", "爆胎", "露帘线", "还能上高速"))
        if safety:
            return {
                "intent": "safety_risk",
                "status": "completed",
                "answer": "这可能涉及行车安全。请不要继续高速或长距离行驶，并尽快由专业人员现场检查；如已明显失压、鼓包或露帘线，建议停止使用并联系救援。",
                "evidence": [],
            }
        if high_risk:
            return {"intent": "handoff", "status": "handoff"}
        return {}

    @staticmethod
    def after_risk(state: GraphState) -> str:
        if state.get("status") == "handoff":
            return "handoff"
        if state.get("answer"):
            return "verify"
        return "route"

    async def route(self, state: GraphState) -> GraphState:
        started = time.perf_counter()
        route = await self.llm.route(state["text"])
        timings = dict(state.get("timings_ms", {}))
        timings["route_model"] = round((time.perf_counter() - started) * 1000, 2)
        return {"route": route, "intent": route.get("intent", "out_of_scope"), "timings_ms": timings}

    @staticmethod
    def after_route(state: GraphState) -> str:
        return "handoff" if state.get("intent") in ("refund", "handoff") else "retrieve"

    async def retrieve(self, state: GraphState) -> GraphState:
        started = time.perf_counter()
        intent = state["intent"]
        route = state.get("route", {})
        customer = self.repo.get_customer(state["customer_id"]) or {"region_id": "shanghai"}
        vehicle = self.repo.get_vehicle(state["customer_id"])
        evidence: list[dict[str, Any]] = []

        if intent == "tire_knowledge":
            for chunk in await self.knowledge.search_async(
                state["text"], settings.ollama_base_url, settings.embed_model
            ):
                evidence.append({**chunk, "evidence_type": "knowledge"})
        elif intent in ("product_price", "tire_fitment"):
            spec = dict(route.get("slots", {}))
            if not spec and vehicle:
                spec = {k: vehicle[k] for k in ("width_mm", "aspect_ratio", "rim_inch")}
            products = self.repo.search_products(spec)
            evidence.extend({**p, "evidence_type": "product", "evidence_id": f"product:{p['sku_id']}"} for p in products)
            prices = self.repo.prices_for([p["sku_id"] for p in products], customer["region_id"])
            evidence.extend({**p, "evidence_type": "price", "evidence_id": f"price:{p['price_id']}"} for p in prices)
        elif intent == "order_query":
            evidence.extend({**o, "evidence_type": "order", "evidence_id": f"order:{o['order_id']}"} for o in self.repo.orders_for(state["customer_id"]))
        elif intent == "campaign_query":
            evidence.extend({**c, "evidence_type": "campaign", "evidence_id": f"campaign:{c['campaign_id']}"} for c in self.repo.active_campaigns(customer["region_id"]))

        timings = dict(state.get("timings_ms", {}))
        timings["retrieve"] = round((time.perf_counter() - started) * 1000, 2)
        citations = []
        for e in evidence[:5]:
            citations.append({
                "evidence_id": e.get("evidence_id", f"chunk:{e.get('chunk_id', 'unknown')}"),
                "source": e.get("source_uri", e.get("evidence_type", "mock")),
                "title": e.get("title", e.get("series", e.get("name", e.get("order_id", "业务数据")))),
                "updated_at": e.get("updated_at"),
            })
        return {"evidence": evidence, "citations": citations, "timings_ms": timings}

    async def generate(self, state: GraphState) -> GraphState:
        if state.get("answer"):
            return {}
        started = time.perf_counter()
        answer = await self.llm.answer(state["text"], state["intent"], state.get("evidence", []))
        timings = dict(state.get("timings_ms", {}))
        timings["answer_model"] = round((time.perf_counter() - started) * 1000, 2)
        return {"answer": answer, "status": "completed", "timings_ms": timings}

    async def verify(self, state: GraphState) -> GraphState:
        if state.get("intent") not in ("out_of_scope",) and not state.get("answer"):
            return {"status": "handoff", "handoff_id": f"h_{uuid.uuid4().hex[:10]}", "answer": "暂时无法生成可靠回答，已为您转接人工客服。"}
        if state.get("intent") == "out_of_scope":
            return {"answer": "我目前主要处理轮胎选购、规格、保养、价格、活动和订单问题。您可以换一个轮胎相关的问题试试。", "status": "completed"}
        if state.get("intent") in ("product_price", "tire_fitment"):
            answer = state.get("answer", "")
            if "上海" not in answer or "更新时间" not in answer:
                products = [x for x in state.get("evidence", []) if x.get("evidence_type") == "product"]
                prices = [x for x in state.get("evidence", []) if x.get("evidence_type") == "price"]
                if products and prices:
                    product_by_sku = {x["sku_id"]: x for x in products}
                    lines = []
                    for price in prices[:3]:
                        product = product_by_sku.get(price["sku_id"])
                        if product:
                            lines.append(f"{product['brand']} {product['series']}：¥{price['sale_price']}/条")
                    if lines:
                        return {"answer": "根据已绑定车辆规格，上海地区候选价格为：" + "；".join(lines) + f"。数据更新时间 {prices[0]['updated_at']}，最终适配与价格以结算校验为准。"}
        return {}

    async def handoff(self, state: GraphState) -> GraphState:
        handoff_id = f"h_{uuid.uuid4().hex[:10]}"
        return {
            "handoff_id": handoff_id,
            "status": "handoff",
            "answer": f"已为您创建人工客服任务，编号 {handoff_id}。Demo 不会实际修改订单或执行退款。",
            "citations": [],
        }

    async def invoke(self, text: str, customer_id: str, trace_id: str,
                     visual_result: dict[str, Any] | None = None) -> GraphState:
        return await self.graph.ainvoke({
            "text": text,
            "customer_id": customer_id,
            "trace_id": trace_id,
            "timings_ms": {},
            "evidence": [],
            "citations": [],
            "visual_result": visual_result or {},
        })
