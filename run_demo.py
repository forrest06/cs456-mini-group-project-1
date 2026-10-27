#!/usr/bin/env python3
"""Run two short demonstrations: baseline detection and heartbeat spoofing."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def stream_output(label: str, process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{label}] {line}", end="", flush=True)


def start(label: str, *arguments: str) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        [PYTHON, *arguments],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    threading.Thread(target=stream_output, args=(label, process), daemon=True).start()
    return process


def stop(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=2.0)


def baseline_phase() -> None:
    print("\n=== PHASE 1 BASELINE CRASH DETECTION ===", flush=True)
    monitor = start(
        "MONITOR",
        "heartbeat_monitor.py",
        "--heartbeat-interval", "0.5",
        "--missed-threshold", "3",
        "--timeout-window", "1.8",
        "--log-file", "demo_baseline_incidents.jsonl",
    )
    time.sleep(0.5)
    service = start(
        "SERVICE",
        "critical_service.py",
        "--heartbeat-interval", "0.5",
        "--crash-min", "3.0",
        "--crash-max", "4.0",
    )
    time.sleep(1.0)
    client = start("CLIENT", "auth_client.py")
    client.wait(timeout=4.0)
    service.wait(timeout=7.0)
    print(f"[DEMO] service exited status={service.returncode}; waiting for monitor alert", flush=True)
    time.sleep(2.4)
    stop(monitor)


def attack_phase() -> None:
    print("\n=== PHASE 2 SPOOFING MASKS DOWNTIME ===", flush=True)
    monitor = start(
        "MONITOR",
        "heartbeat_monitor.py",
        "--heartbeat-interval", "0.5",
        "--missed-threshold", "3",
        "--timeout-window", "1.8",
        "--log-file", "demo_attack_incidents.jsonl",
    )
    time.sleep(0.5)
    service = start(
        "SERVICE",
        "critical_service.py",
        "--heartbeat-interval", "0.5",
        "--crash-min", "3.0",
        "--crash-max", "4.0",
    )
    time.sleep(1.5)
    attacker = start(
        "ATTACK",
        "adversarial_audit.py",
        "--mode", "spoof",
        "--interval", "0.5",
        "--duration", "6.0",
    )
    service.wait(timeout=7.0)
    print(
        f"[DEMO] service exited status={service.returncode}; forged beats continue, so no alert should occur",
        flush=True,
    )
    attacker.wait(timeout=8.0)
    print("[DEMO] attacker stopped; the monitor should now detect the outage", flush=True)
    time.sleep(2.4)
    stop(monitor)


def main() -> int:
    baseline_phase()
    attack_phase()
    print("\n=== DEMO COMPLETE ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
