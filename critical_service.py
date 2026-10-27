#!/usr/bin/env python3
"""Lightweight authentication service with a stochastic fatal fault injector."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import socket
import socketserver
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


USERS = {
    "alice": hashlib.sha256(b"wonderland").hexdigest(),
    "bob": hashlib.sha256(b"builder").hexdigest(),
}
TOKEN_KEY = b"cs456-demo-token-key"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def issue_token(username: str) -> str:
    payload = f"{username}:{int(time.time())}"
    signature = hmac.new(TOKEN_KEY, payload.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{payload}:{signature}"


def authenticate(request: dict[str, Any]) -> dict[str, Any]:
    username = str(request.get("username", ""))
    password_hash = hashlib.sha256(str(request.get("password", "")).encode()).hexdigest()
    stored_hash = USERS.get(username)
    if stored_hash and hmac.compare_digest(password_hash, stored_hash):
        return {"ok": True, "token": issue_token(username), "issued_at": utc_timestamp()}
    return {"ok": False, "error": "invalid credentials", "issued_at": utc_timestamp()}


class AuthenticationHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(3.0)
        try:
            raw = self.rfile.readline(8192)
            if not raw:
                return
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
            response = authenticate(request)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            response = {"ok": False, "error": f"bad request: {exc}", "issued_at": utc_timestamp()}
        except TimeoutError:
            response = {"ok": False, "error": "request timeout", "issued_at": utc_timestamp()}
        self.wfile.write((json.dumps(response, separators=(",", ":")) + "\n").encode())
        print(
            f"{utc_timestamp()} SERVICE request from={self.client_address[0]} "
            f"result={'accepted' if response.get('ok') else 'rejected'}",
            flush=True,
        )


class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def heartbeat_loop(
    stop_event: threading.Event,
    monitor_host: str,
    monitor_port: int,
    interval: float,
    service_id: str,
    capture_file: Path,
) -> None:
    sequence = 0
    destination = (monitor_host, monitor_port)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        while not stop_event.is_set():
            sequence += 1
            message = {
                "type": "HEARTBEAT",
                "service_id": service_id,
                "sequence": sequence,
                "sent_at": utc_timestamp(),
                "status": "ready",
            }
            encoded = json.dumps(message, separators=(",", ":")).encode("utf-8")
            udp_socket.sendto(encoded, destination)
            capture_file.write_text(json.dumps(message, indent=2) + "\n", encoding="utf-8")
            print(f"{utc_timestamp()} SERVICE heartbeat sequence={sequence}", flush=True)
            stop_event.wait(interval)


def fault_injector(minimum: float, maximum: float) -> None:
    delay = secrets.SystemRandom().uniform(minimum, maximum)
    print(
        f"{utc_timestamp()} SERVICE stochastic fault injector armed "
        f"window={minimum:.1f}-{maximum:.1f}s",
        flush=True,
    )
    time.sleep(delay)
    print(
        f"{utc_timestamp()} SERVICE FATAL simulated memory-corruption crash",
        flush=True,
    )
    os._exit(70)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--monitor-host", default="127.0.0.1")
    parser.add_argument("--monitor-port", type=int, default=5051)
    parser.add_argument("--service-id", default="auth-service-1")
    parser.add_argument("--heartbeat-interval", type=float, default=1.0)
    parser.add_argument("--crash-min", type=float, default=12.0)
    parser.add_argument("--crash-max", type=float, default=24.0)
    parser.add_argument("--disable-crash", action="store_true")
    parser.add_argument("--capture-file", type=Path, default=Path("last_heartbeat.json"))
    args = parser.parse_args()
    if args.heartbeat_interval <= 0:
        parser.error("--heartbeat-interval must be positive")
    if args.crash_min <= 0 or args.crash_max < args.crash_min:
        parser.error("crash window must satisfy 0 < minimum <= maximum")
    return args


def main() -> int:
    args = parse_args()
    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(
            stop_event,
            args.monitor_host,
            args.monitor_port,
            args.heartbeat_interval,
            args.service_id,
            args.capture_file,
        ),
        name="heartbeat-emitter",
        daemon=True,
    )
    heartbeat_thread.start()
    if not args.disable_crash:
        threading.Thread(
            target=fault_injector,
            args=(args.crash_min, args.crash_max),
            name="fault-injector",
            daemon=True,
        ).start()

    try:
        with ReusableThreadingTCPServer((args.host, args.port), AuthenticationHandler) as server:
            print(
                f"{utc_timestamp()} SERVICE listening tcp://{args.host}:{args.port} "
                f"heartbeat=udp://{args.monitor_host}:{args.monitor_port}",
                flush=True,
            )
            server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print(f"{utc_timestamp()} SERVICE stopping", flush=True)
    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=2.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
