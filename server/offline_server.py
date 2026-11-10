#!/usr/bin/env python3
"""Minimal, local-only Girl X Battle companion API.

This is intentionally a diagnostic MVP.  It implements the bootstrap and
login path found in the APK and records every request for incremental schema
work.  It is not an emulator of the original online service.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


MID_VERSION_CHECK = 2
MID_RETRIEVE_TOKEN = 1
MID_LOAD_ANNOUNCE = 7
MID_LOAD_PLAYER_INFO = 17
MID_LOAD_USER_REGIONS = 18
MID_QUERY_SERVER_TIME = 3
MID_GET_BUILDING_LIST = 1056
MID_GET_PLAYER_GROUP_BY_KEY = 2864


@dataclass(frozen=True)
class Config:
    host: str
    port: int

    @property
    def api_url(self) -> str:
        return f"http://{self.host}:{self.port}/api/v1"


class Store:
    def __init__(self, database: Path) -> None:
        self.database = database
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS request_log (
                    id INTEGER PRIMARY KEY,
                    received_at INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    mid INTEGER,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def log_request(self, path: str, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO request_log(received_at, path, mid, payload_json) VALUES (?, ?, ?, ?)",
                (int(time.time()), path, payload.get("mid"), json.dumps(payload, ensure_ascii=False)),
            )


def response_for(payload: dict[str, Any], config: Config) -> Any:
    """Return the smallest safe response for the discovered startup calls."""
    mid = payload.get("mid")
    now = int(time.time())

    if mid == 20480:
        return {
            "url": config.api_url,
            "server_id": "offline-1",
            "back_domain": "",
            "res_download_url": "",
        }

    if mid == MID_VERSION_CHECK:
        # Keeping both flags zero makes UpdateScene proceed to startGame_.
        return {"is_appstore": 0, "is_inapp": 0, "need_restart": 0, "is_review": 0}

    if mid == MID_LOAD_USER_REGIONS:
        return {
            "regions": [{"region_id": 1, "name": "Offline"}],
            "players": [],
            "server_time": now,
        }

    if mid == MID_RETRIEVE_TOKEN:
        return {
            "token": "offline-token",
            "region": int(payload.get("region") or 1),
            "log_url": "",
            "is_new": "0",
            "story_type": 0,
            "is_debug": 0,
            "is_old_top": 0,
            "server_time": now,
        }

    if mid == MID_LOAD_ANNOUNCE:
        return {"contents": "[]", "server_time": now}

    if mid == MID_QUERY_SERVER_TIME:
        return {"server_time": now}

    if mid == MID_LOAD_PLAYER_INFO:
        # This is only a starting shape.  Device logs will reveal remaining
        # required fields when the main scene loads.
        return {
            "player_id": 1,
            "playerID": 1,
            "player_name": "Offline Player",
            "playerName": "Offline Player",
            "level": 1,
            "avatar_id": 10001001,
            "avatar_frame_id": 1,
            "server_time": now,
        }

    if mid == MID_GET_BUILDING_LIST:
        # EventCentre.lua reads these fields unconditionally during startup.
        # A level-one, idle building set is enough to open the main UI without
        # enabling the online/event systems behind those buildings.
        idle_building = {"lev": 1, "need_time": 0, "start_time": 0, "new_evolve": 0}
        return {
            "building_list": {str(kind): dict(idle_building) for kind in range(1, 8)},
            "desk_info": {
                "is_making": 0,
                "make_need_time": 0,
                "make_start_time": 0,
                "make_item": 0,
            },
            "pet_cabin_info": {
                "pet_id": 0,
                "is_making": 0,
                "make_need_time": 0,
                "make_start_time": 0,
                "make_item": 0,
            },
            "cabinet_info": {
                "need_time": 0,
                "start_time": 0,
                "recent_complete_skill": 0,
                "cur_learn_skill": 0,
            },
            "server_time": now,
        }

    if mid == MID_GET_PLAYER_GROUP_BY_KEY:
        # SelfPlayer stores this response directly as an A/B group string,
        # rather than as an object.  A deterministic group prevents startup
        # code from treating an unexpected object as a feature flag.
        return "A"

    # Returning HTTP 200 lets the client log and expose the next missing
    # response shape without the generic connection-retry dialog.
    return {"server_time": now, "offline_unimplemented_mid": mid}


def decode_form_payload(body: bytes) -> dict[str, Any]:
    """Decode the URL-encoded JSON request format used by Backend.lua."""
    try:
        fields = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        raw_payload = fields.get("payload", [""])[0]
        payload = json.loads(raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"unsupported request payload: {error}") from error

    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return payload


def make_handler(config: Config, store: Store) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GXBOffline/0.1"

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            path = urlparse(self.path).path

            try:
                payload = decode_form_payload(body)
                store.log_request(path, payload)
                print(f"request path={path} mid={payload.get('mid')} keys={','.join(sorted(payload))}")
                answer = response_for(payload, config)
                self.send_json(HTTPStatus.OK, answer)
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

        def do_GET(self) -> None:  # noqa: N802
            if urlparse(self.path).path == "/healthz":
                self.send_json(HTTPStatus.OK, {"status": "ok", "api_url": config.api_url})
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def send_json(self, status: HTTPStatus, body: Any) -> None:
            encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Girl X Battle protocol MVP")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: loopback only)")
    parser.add_argument("--port", default=18080, type=int, help="TCP port (default: 18080)")
    parser.add_argument("--db", default="offline-state.sqlite3", type=Path, help="SQLite request log path")
    args = parser.parse_args()

    config = Config(args.host, args.port)
    store = Store(args.db)
    server = ThreadingHTTPServer((config.host, config.port), make_handler(config, store))
    print(f"GXB offline MVP listening at {config.api_url}")
    print(f"Request log: {args.db.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
