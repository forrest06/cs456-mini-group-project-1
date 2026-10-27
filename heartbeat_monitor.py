#!/usr/bin/env python3
"""Independent UDP monitor for push-based service heartbeats."""

from __future__ import annotations

import argparse
import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def append_event(path: Path, event: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, separators=(",", ":")) + "\n")


def parse_heartbeat(payload: bytes, expected_service_id: str) -> dict[str, Any]:
    message = json.loads(payload.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("payload is not a JSON object")
    required = {"type", "service_id", "sequence", "sent_at", "status"}
    if not required.issubset(message):
        raise ValueError("missing required heartbeat fields")
    if message["type"] != "HEARTBEAT" or message["service_id"] != expected_service_id:
        raise ValueError("unexpected message type or service identifier")
    if not isinstance(message["sequence"], int):
        raise ValueError("sequence must be an integer")
    return message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5051)
    parser.add_argument("--service-id", default="auth-service-1")
    parser.add_argument("--heartbeat-interval", type=float, default=1.0)
    parser.add_argument("--missed-threshold", type=int, default=3)
    parser.add_argument("--timeout-window", type=float, default=3.5)
    parser.add_argument("--log-file", type=Path, default=Path("monitor_incidents.jsonl"))
    args = parser.parse_args()
    if args.heartbeat_interval <= 0 or args.missed_threshold < 1 or args.timeout_window <= 0:
        parser.error("timing values must be positive and missed threshold must be at least 1")
    return args


def main() -> int:
    args = parse_args()
    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    last_received: float | None = None
    fault_reported = False
    last_sequence: int | None = None

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind((args.host, args.port))
        udp_socket.settimeout(min(0.25, args.heartbeat_interval / 2))
        print(
            f"{utc_timestamp()} MONITOR listening udp://{args.host}:{args.port} "
            f"T={args.heartbeat_interval:.2f}s N={args.missed_threshold} W={args.timeout_window:.2f}s",
            flush=True,
        )

        try:
            while True:
                try:
                    payload, sender = udp_socket.recvfrom(8192)
                    message = parse_heartbeat(payload, args.service_id)
                except socket.timeout:
                    message = None
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                    print(f"{utc_timestamp()} MONITOR ignored invalid packet reason={exc}", flush=True)
                    continue

                now = time.monotonic()
                if message is not None:
                    previous = last_sequence
                    last_received = now
                    last_sequence = int(message["sequence"])
                    if fault_reported:
                        print(
                            f"{utc_timestamp()} MONITOR RECOVERY service={args.service_id} "
                            f"sender={sender[0]}:{sender[1]}",
                            flush=True,
                        )
                        fault_reported = False
                    replay_hint = " duplicate-or-reordered" if previous is not None and last_sequence <= previous else ""
                    print(
                        f"{utc_timestamp()} MONITOR HEALTHY service={args.service_id} "
                        f"sequence={last_sequence}{replay_hint}",
                        flush=True,
                    )
                    continue

                if last_received is None or fault_reported:
                    continue
                elapsed = now - last_received
                missed = int(elapsed / args.heartbeat_interval)
                if missed >= args.missed_threshold and elapsed >= args.timeout_window:
                    event = {
                        "event": "HEARTBEAT_TIMEOUT",
                        "detected_at": utc_timestamp(),
                        "service_id": args.service_id,
                        "seconds_since_last_beat": round(elapsed, 3),
                        "missed_beats": missed,
                        "timeout_window_seconds": args.timeout_window,
                    }
                    append_event(args.log_file, event)
                    print(
                        f"{event['detected_at']} MONITOR ALERT service={args.service_id} "
                        f"unresponsive elapsed={elapsed:.2f}s missed={missed} incident_logged={args.log_file}",
                        flush=True,
                    )
                    fault_reported = True
        except KeyboardInterrupt:
            print(f"{utc_timestamp()} MONITOR stopping", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
