from __future__ import annotations

import re
import subprocess


def main():
    output = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    pids = set()
    for line in output.splitlines():
        if "LISTENING" not in line:
            continue
        if re.search(r"127\.0\.0\.1:(8000|11434)\s", line):
            match = re.search(r"(\d+)\s*$", line)
            if match:
                pids.add(match.group(1))
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], check=False, capture_output=True)
    print(f"Stopped {len(pids)} listener process(es).")


if __name__ == "__main__":
    main()

