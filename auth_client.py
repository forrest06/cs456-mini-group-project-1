#!/usr/bin/env python3
"""Send one JSON credential request to the demo authentication service."""

from __future__ import annotations

import argparse
import json
import socket


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--username", default="alice")
    parser.add_argument("--password", default="wonderland")
    args = parser.parse_args()

    request = json.dumps({"username": args.username, "password": args.password}) + "\n"
    with socket.create_connection((args.host, args.port), timeout=3.0) as tcp_socket:
        tcp_socket.sendall(request.encode("utf-8"))
        response = tcp_socket.makefile("r", encoding="utf-8").readline()
    print(json.dumps(json.loads(response), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
