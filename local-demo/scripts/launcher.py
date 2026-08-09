from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
AI_RUNTIME = Path(os.environ.get("AI_RUNTIME_DIR", r"C:\AI"))
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)


def listening(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def detached(command: list[str], cwd: Path, env: dict[str, str], log_name: str) -> None:
    out = open(LOGS / f"{log_name}.out.log", "ab", buffering=0)
    err = open(LOGS / f"{log_name}.err.log", "ab", buffering=0)
    subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=out,
        stderr=err,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        close_fds=True,
    )


def main():
    env = os.environ.copy()
    # The one-click launcher is the real-model profile. Tests set LLM_MODE
    # directly when they start their own in-process application.
    llm_mode = "auto"
    env.update({
        "OLLAMA_MODELS": str(AI_RUNTIME / "models"),
        "OLLAMA_HOST": "127.0.0.1:11434",
        "OLLAMA_KEEP_ALIVE": "2m",
        "CUDA_VISIBLE_DEVICES": "-1",
        "GGML_VK_VISIBLE_DEVICES": "-1",
        "OLLAMA_LLM_LIBRARY": "cpu",
        "DEMO_DATA_DIR": str(ROOT / "data"),
        # Stable local demo default. Set LLM_MODE=auto before launching to use Ollama.
        "LLM_MODE": llm_mode,
    })
    if llm_mode != "mock" and not listening(11434):
        detached([str(AI_RUNTIME / "ollama" / "ollama.exe"), "serve"], AI_RUNTIME / "ollama", env, "ollama")
    if not listening(8000):
        detached([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"], ROOT, env, "demo")
    deadline = time.time() + 20
    while time.time() < deadline:
        if listening(8000):
            with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health", timeout=5) as response:
                print(json.dumps(json.load(response), ensure_ascii=False))
            print("Local: http://127.0.0.1:8000")
            print("LAN:   http://<this-PC-IPv4>:8000")
            return
        time.sleep(1)
    raise SystemExit("Demo failed to start; check local-demo/logs")


if __name__ == "__main__":
    main()
