from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient

from app.main import app


QUESTIONS = [
    "225/55R17是什么意思？",
    "我的车换一套轮胎多少钱？",
    "我的订单预约到几点？",
    "现在有什么优惠活动？",
    "轮胎鼓包了还能上高速吗？",
]


def main():
    client = TestClient(app)
    cid = client.post("/api/v1/conversations", json={"customer_id": "u_001"}).json()["conversation_id"]
    times = []
    for i, question in enumerate(QUESTIONS):
        start = time.perf_counter()
        response = client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"message_id": f"bench_{i}", "text": question},
        )
        elapsed = (time.perf_counter() - start) * 1000
        response.raise_for_status()
        body = response.json()
        times.append(elapsed)
        print(f"{elapsed:8.2f} ms | {body['intent']:16s} | {question}")
    ordered = sorted(times)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(f"mean={statistics.mean(times):.2f} ms, p95={p95:.2f} ms")


if __name__ == "__main__":
    main()
