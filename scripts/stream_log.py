#!/usr/bin/env python3
"""
Prefix streamed process output and mirror it into a log file.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: stream_log.py <label> <log_file>", file=sys.stderr)
        return 1

    label = sys.argv[1]
    log_path = Path(sys.argv[2])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("a", encoding="utf-8") as log_file:
        for raw_line in sys.stdin:
            line = raw_line.rstrip("\n")
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted = f"[{timestamp}] [{label}] {line}"
            print(formatted, flush=True)
            log_file.write(formatted + "\n")
            log_file.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
