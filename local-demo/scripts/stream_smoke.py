from __future__ import annotations

import json
import sys
import time
import uuid
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    base = "http://127.0.0.1:8000"
    with httpx.Client(timeout=180) as client:
        cid = client.post(f"{base}/api/v1/conversations", json={"customer_id": "u_001"}).json()["conversation_id"]
        started = time.perf_counter()
        counts: dict[str, int] = {}
        first_ms = None
        completed = None
        with client.stream(
            "POST",
            f"{base}/api/v1/conversations/{cid}/messages/stream",
            json={"message_id": str(uuid.uuid4()), "text": "225/55R17是什么意思？"},
        ) as response:
            response.raise_for_status()
            event = ""
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                    counts[event] = counts.get(event, 0) + 1
                    if first_ms is None:
                        first_ms = round((time.perf_counter() - started) * 1000, 2)
                elif line.startswith("data:") and event == "answer.completed":
                    completed = json.loads(line.split(":", 1)[1].strip())
        print(json.dumps({
            "first_event_ms": first_ms,
            "total_ms": round((time.perf_counter() - started) * 1000, 2),
            "event_counts": counts,
            "completed": completed,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
