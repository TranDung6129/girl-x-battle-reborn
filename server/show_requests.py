#!/usr/bin/env python3
"""Print recorded offline-server requests without local authentication values."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


REDACTED_KEYS = {"token", "login_token", "sid"}


def redact(value: object) -> object:
    if isinstance(value, dict):
        return {key: ("<redacted>" if key in REDACTED_KEYS else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", nargs="?", default="offline-state.sqlite3", type=Path)
    args = parser.parse_args()
    with sqlite3.connect(args.database) as connection:
        rows = connection.execute(
            "SELECT id, received_at, path, mid, payload_json FROM request_log ORDER BY id"
        ).fetchall()
    for identifier, received_at, path, mid, payload_json in rows:
        payload = redact(json.loads(payload_json))
        print(json.dumps({"id": identifier, "at": received_at, "path": path, "mid": mid, "payload": payload}, ensure_ascii=False))


if __name__ == "__main__":
    main()
