from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from critical_service import authenticate
from heartbeat_monitor import parse_heartbeat


class AuthenticationTests(unittest.TestCase):
    def test_valid_credentials_issue_token(self) -> None:
        result = authenticate({"username": "alice", "password": "wonderland"})
        self.assertTrue(result["ok"])
        self.assertIn("token", result)

    def test_invalid_credentials_are_rejected(self) -> None:
        result = authenticate({"username": "alice", "password": "incorrect"})
        self.assertFalse(result["ok"])


class HeartbeatTests(unittest.TestCase):
    def test_valid_heartbeat_is_accepted(self) -> None:
        message = {
            "type": "HEARTBEAT",
            "service_id": "auth-service-1",
            "sequence": 4,
            "sent_at": "2026-10-26T20:00:00.000+00:00",
            "status": "ready",
        }
        parsed = parse_heartbeat(json.dumps(message).encode(), "auth-service-1")
        self.assertEqual(parsed["sequence"], 4)

    def test_wrong_service_is_rejected(self) -> None:
        message = {
            "type": "HEARTBEAT",
            "service_id": "wrong-service",
            "sequence": 4,
            "sent_at": "2026-10-26T20:00:00.000+00:00",
            "status": "ready",
        }
        with self.assertRaises(ValueError):
            parse_heartbeat(json.dumps(message).encode(), "auth-service-1")


if __name__ == "__main__":
    unittest.main()
