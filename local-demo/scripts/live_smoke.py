from __future__ import annotations

import json
import sys
import time
import uuid
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


QUESTIONS = [
    "225/55R17是什么意思？",
    "我的车换一套轮胎多少钱？",
    "我的订单预约到几点？",
]


def main():
    base = "http://127.0.0.1:8000"
    with httpx.Client(timeout=180) as client:
        health = client.get(f"{base}/api/v1/health").json()
        print("health", json.dumps(health, ensure_ascii=False))
        cid = client.post(f"{base}/api/v1/conversations", json={"customer_id": "u_001"}).json()["conversation_id"]
        for question in QUESTIONS:
            started = time.perf_counter()
            response = client.post(
                f"{base}/api/v1/conversations/{cid}/messages",
                json={"message_id": str(uuid.uuid4()), "text": question},
            )
            response.raise_for_status()
            body = response.json()
            print(json.dumps({
                "question": question,
                "intent": body["intent"],
                "status": body["status"],
                "answer": body["answer"],
                "citations": len(body["citations"]),
                "timings_ms": body["timings_ms"],
                "wall_ms": round((time.perf_counter() - started) * 1000, 2),
            }, ensure_ascii=False))


if __name__ == "__main__":
    main()
