from fastapi.testclient import TestClient

from app.main import app, workflow


client = TestClient(app)


def conversation() -> str:
    response = client.post("/api/v1/conversations", json={"customer_id": "u_001"})
    assert response.status_code == 200
    return response.json()["conversation_id"]


def ask(text: str, message_id: str = "m_1") -> dict:
    cid = conversation()
    response = client.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"message_id": message_id, "text": text},
    )
    assert response.status_code == 200
    return response.json()


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["mock_counts"]["products"] >= 5


def test_tire_knowledge():
    result = ask("225/55R17是什么意思？")
    assert result["intent"] == "tire_knowledge"
    assert result["status"] == "completed"
    assert result["citations"]


def test_price_uses_vehicle():
    result = ask("我的车换一套轮胎多少钱？")
    assert result["intent"] in ("product_price", "tire_fitment")
    assert "¥" in result["answer"]
    assert result["debug"]["evidence_count"] >= 2


def test_order_is_scoped_to_customer():
    result = ask("我的订单预约到几点？")
    assert result["intent"] == "order_query"
    assert "o_001" in result["answer"]
    assert "o_002" not in result["answer"]


def test_refund_handoff():
    result = ask("这个订单我要退款")
    assert result["status"] == "handoff"
    assert result["handoff_id"]


def test_safety_rule_precedes_model():
    result = ask("轮胎鼓包了还能上高速吗？")
    assert result["intent"] == "safety_risk"
    assert "不要继续高速" in result["answer"]
    assert "route_model" not in result["timings_ms"]


def test_mock_es_term_filter():
    response = client.post(
        "/mock-es/tire_product_current/_search",
        json={"size": 10, "query": {"bool": {"filter": [{"term": {"rim_inch": 17}}]}}},
    )
    assert response.status_code == 200
    hits = response.json()["hits"]["hits"]
    assert hits and all(x["_source"]["rim_inch"] == 17 for x in hits)


async def test_price_gate_adds_required_fields():
    state = {
        "intent": "product_price",
        "answer": "这款轮胎399元。",
        "evidence": [
            {"evidence_type": "product", "sku_id": "sku_001", "brand": "示例品牌A", "series": "Comfort X1"},
            {"evidence_type": "price", "sku_id": "sku_001", "sale_price": 399.0, "updated_at": "2026-08-09T11:00:00+08:00"},
        ],
    }
    result = await workflow.verify(state)
    assert "上海地区" in result["answer"]
    assert "数据更新时间" in result["answer"]


def test_sse_stream_contract():
    cid = conversation()
    with client.stream(
        "POST",
        f"/api/v1/conversations/{cid}/messages/stream",
        json={"message_id": "stream_1", "text": "225/55R17是什么意思？"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "event: message.accepted" in body
    assert "event: answer.delta" in body
    assert "event: citation" in body
    assert "event: answer.completed" in body
