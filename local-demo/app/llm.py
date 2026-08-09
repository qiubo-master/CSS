from __future__ import annotations

import json
import re
from typing import Any
import httpx

from .config import settings


class LocalLLM:
    def __init__(self):
        self.mode = settings.llm_mode

    async def available(self) -> bool:
        if self.mode == "mock":
            return False
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{settings.ollama_base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def route(self, text: str) -> dict[str, Any]:
        if await self.available():
            result = await self._ollama_json(self._route_prompt(text))
            if result:
                return self._normalize_route(result, text)
        return self._mock_route(text)

    def _normalize_route(self, result: dict[str, Any], text: str) -> dict[str, Any]:
        allowed_intents = {
            "tire_knowledge", "tire_fitment", "product_price", "order_query",
            "campaign_query", "refund", "handoff", "out_of_scope",
        }
        fallback = self._mock_route(text)
        intent = result.get("intent")
        if intent not in allowed_intents:
            return fallback
        slots = result.get("slots")
        if not isinstance(slots, dict):
            slots = {}
        spec_match = re.search(r"(\d{3})\s*/\s*(\d{2})\s*[rR]\s*(\d{2})", text)
        if spec_match:
            slots.update({"width_mm": int(spec_match[1]), "aspect_ratio": int(spec_match[2]), "rim_inch": int(spec_match[3])})
        tools_by_intent = {
            "tire_knowledge": ["rag"], "tire_fitment": ["products", "prices"],
            "product_price": ["products", "prices"], "order_query": ["orders"],
            "campaign_query": ["campaigns"], "refund": ["handoff"], "handoff": ["handoff"],
            "out_of_scope": [],
        }
        return {
            "intent": intent,
            "confidence": min(1.0, max(0.0, float(result.get("confidence", 0.7)))),
            "slots": slots,
            "missing_slots": result.get("missing_slots", []) if isinstance(result.get("missing_slots", []), list) else [],
            "required_tools": tools_by_intent[intent],
        }

    async def answer(self, text: str, intent: str, evidence: list[dict[str, Any]]) -> str:
        if await self.available():
            prompt = self._answer_prompt(text, intent, evidence)
            async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        "model": settings.chat_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "think": False,
                        "options": {"temperature": 0.1, "num_ctx": 3072, "num_predict": 300},
                    },
                )
                response.raise_for_status()
                return response.json()["message"]["content"].strip()
        return self._mock_answer(text, intent, evidence)

    async def _ollama_json(self, prompt: str) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        "model": settings.chat_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "format": "json",
                        "stream": False,
                        "think": False,
                        "options": {"temperature": 0, "num_ctx": 2048, "num_predict": 180},
                    },
                )
                response.raise_for_status()
                return json.loads(response.json()["message"]["content"])
        except Exception:
            return None

    @staticmethod
    def _route_prompt(text: str) -> str:
        return f"""你是轮胎客服路由器，只输出JSON。
意图枚举：tire_knowledge,tire_fitment,product_price,order_query,campaign_query,refund,handoff,out_of_scope。
字段：intent,confidence,slots,missing_slots,required_tools。slots必须是JSON对象，不能是数组。
工具枚举：rag,products,prices,orders,campaigns,handoff。
用户问题：{text}
"""

    @staticmethod
    def _answer_prompt(text: str, intent: str, evidence: list[dict[str, Any]]) -> str:
        return f"""你是汽车后市场轮胎客服。只能依据给定证据回答，不得编造价格、订单、适配和政策。
用户问题：{text}
意图：{intent}
证据：{json.dumps(evidence, ensure_ascii=False)}
要求：中文简洁回答；涉及价格说明地区和更新时间；信息不足明确追问；不要输出内部JSON或思考过程。
"""

    @staticmethod
    def _mock_route(text: str) -> dict[str, Any]:
        lower = text.lower()
        if any(k in text for k in ("退款", "退货", "退钱")):
            intent, tools = "refund", ["handoff"]
        elif any(k in text for k in ("人工", "客服", "投诉")):
            intent, tools = "handoff", ["handoff"]
        elif any(k in text for k in ("订单", "预约", "物流")):
            intent, tools = "order_query", ["orders"]
        elif any(k in text for k in ("优惠", "活动", "满减")):
            intent, tools = "campaign_query", ["campaigns"]
        elif any(k in text for k in ("多少钱", "价格", "报价")):
            intent, tools = "product_price", ["products", "prices"]
        elif any(k in text for k in ("适合", "推荐", "车型", "换一套")):
            intent, tools = "tire_fitment", ["products", "prices"]
        elif any(k in lower for k in ("轮胎", "r17", "r18", "补胎", "鼓包", "磨损")):
            intent, tools = "tire_knowledge", ["rag"]
        else:
            intent, tools = "out_of_scope", []
        spec = {}
        match = re.search(r"(\d{3})\s*/\s*(\d{2})\s*[rR]\s*(\d{2})", text)
        if match:
            spec = {"width_mm": int(match[1]), "aspect_ratio": int(match[2]), "rim_inch": int(match[3])}
        return {"intent": intent, "confidence": 0.9, "slots": spec, "missing_slots": [], "required_tools": tools}

    @staticmethod
    def _mock_answer(text: str, intent: str, evidence: list[dict[str, Any]]) -> str:
        if not evidence:
            return "目前没有检索到足够信息。请补充车型年款、轮胎规格或订单信息，我再为您查询。"
        if intent == "order_query":
            order = evidence[0]
            return f"您的订单 {order['order_id']} 当前状态为“{order['status']}”，预约时间是 {order.get('appointment_at', '待确认')}。"
        if intent in ("product_price", "tire_fitment"):
            products = [x for x in evidence if x.get("evidence_type") == "product"]
            prices = [x for x in evidence if x.get("evidence_type") == "price"]
            if products and prices:
                p, price = products[0], prices[0]
                return f"根据已绑定车辆规格，候选为 {p['brand']} {p['series']} {p['width_mm']}/{p['aspect_ratio']}R{p['rim_inch']}，上海参考价 ¥{price['sale_price']} /条，数据更新时间 {price['updated_at']}。最终价格以结算校验为准。"
        if intent == "campaign_query":
            c = evidence[0]
            return f"当前可参考活动：{c['name']}。有效期至 {c['end_at']}，实际资格以结算校验为准。"
        return evidence[0].get("content", "已找到相关信息，请查看引用。")
