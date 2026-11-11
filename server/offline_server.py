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
import zlib
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as email_policy
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
MID_LOAD_SUMMON_INFO = 56
MAX_LOG_BODY = 2 * 1024 * 1024
MAX_LOG_DECOMPRESSED = 8 * 1024 * 1024


@dataclass(frozen=True)
class Config:
    host: str
    port: int

    @property
    def api_url(self) -> str:
        return f"http://{self.host}:{self.port}/api/v1"

    @property
    def client_log_url(self) -> str:
        return f"http://{self.host}:{self.port}/client-log"


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
                CREATE TABLE IF NOT EXISTS client_error_log (
                    id INTEGER PRIMARY KEY,
                    received_at INTEGER NOT NULL,
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

    def log_client_errors(self, entries: list[dict[str, Any]]) -> None:
        with self.connect() as connection:
            connection.executemany(
                "INSERT INTO client_error_log(received_at, payload_json) VALUES (?, ?)",
                [(int(time.time()), json.dumps(entry, ensure_ascii=False)) for entry in entries],
            )


def offline_player_info(now: int) -> dict[str, Any]:
    """Smallest player record that SelfPlayer.onPlayerInfo_ can initialise."""
    return {
        "player_id": 1,
        "uid": 1,
        "player_name": "Offline Player",
        "lev": 1,
        "exp": 1,
        "region": 1,
        "region_name": "Offline",
        "mana": 100000,
        "crystal": 100000,
        "energy": 100,
        "max_energy": 100,
        "energy_time": now,
        "spirit_energy": 0,
        "spirit_energy_time": now,
        "invitation": 0,
        "invitation_time": now,
        "max_invitation": 0,
        "vip": 0,
        "skill_point": 0,
        "skill_time": now,
        "formation": {},
        "avatar_id": 10001001,
        "avatar_frame_id": 0,
        "player_type": 0,
        "max_lev": 999,
        "max_color": 0,
        "func_ids": [],
        "message_pushes": [],
        "story_id": 0,
        "story_state": 0,
        "guide_id": 0,
        "guild_id": 0,
        "conquer_lev": 0,
        "conquer_loop_id": 1,
        "conquer_region": 0,
    }


def offline_start_detail(now: int) -> dict[str, Any]:
    """Responses bundled inside RETRIEVE_TOKEN by the original service.

    This client does not request these three MIDs after login: it expects them
    under ``detail`` in the token response.  In particular a missing player
    record leaves MainScene with no model and makes the loading screen appear
    to hang.
    """
    return {
        str(MID_LOAD_PLAYER_INFO): offline_player_info(now),
        "49": {"heros": [], "sort_type": 0},
        "81": {"list": [], "spirit_list": [], "sort_type": 0},
    }


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
            "uid": 1,
            "region": int(payload.get("region") or 1),
            "log_url": config.client_log_url,
            "is_new": "0",
            "story_type": 0,
            "is_debug": 0,
            "is_old_top": 0,
            "server_time": now,
            "detail": offline_start_detail(now),
        }

    if mid == MID_LOAD_ANNOUNCE:
        return {"contents": "[]", "server_time": now}

    if mid == MID_QUERY_SERVER_TIME:
        return {"server_time": now}

    if mid == MID_LOAD_PLAYER_INFO:
        return offline_player_info(now)

    if mid == 2784:  # ALBUM_SPECIAL_COLLECT_INFO
        return {"is_award": [], "server_time": now}

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

    if mid == MID_LOAD_SUMMON_INFO:
        # SummonWindow indexes these lists immediately to populate its five
        # featured-character slots.  Use existing 1.631.0 hero table IDs so
        # the restored client resources can resolve their portraits and names.
        return {
            "mana_free_time": 0,
            "crystal_free_time": 0,
            "mana_free_num": 1,
            "main_ids": [10001001, 10001002],
            "second_ids": [10001003, 10001004, 10001006],
            "mana_id": 10001001,
            "pet_id": 10001002,
            "partner_id": 10001003,
            "directional_show_id": 10001004,
            "server_time": now,
        }

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


def decode_client_errors(body: bytes, content_type: str) -> list[dict[str, Any]]:
    """Decode Backend.log's multipart ``payload`` containing zlib JSON.

    Native .dmp uploads use a different multipart shape.  Do not acknowledge
    those: the client treats HTTP 200 as permission to delete its local log.
    """
    if len(body) > MAX_LOG_BODY:
        raise ValueError("client log upload exceeds the size limit")
    message = BytesParser(policy=email_policy).parsebytes(
        b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    if message.get_content_type() != "multipart/form-data" or not message.is_multipart() or message.defects:
        raise ValueError("expected a multipart/form-data client log upload")
    parts = list(message.iter_parts())
    if len(parts) != 1 or parts[0].get_param("name", header="content-disposition") != "payload":
        raise ValueError("expected one compressed payload field; native dumps are not supported")
    compressed = parts[0].get_payload(decode=True)
    if not isinstance(compressed, bytes):
        raise ValueError("client log payload is missing")
    try:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(compressed, MAX_LOG_DECOMPRESSED + 1)
        if len(decoded) > MAX_LOG_DECOMPRESSED or inflater.unconsumed_tail:
            raise ValueError("decompressed client log exceeds the size limit")
        if not inflater.eof or inflater.unused_data:
            raise ValueError("incomplete or trailing compressed client log data")
        entries = json.loads(decoded.decode("utf-8"))
    except (zlib.error, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError(f"invalid compressed client log: {error}") from error
    if not isinstance(entries, list) or not all(isinstance(entry, dict) and isinstance(entry.get("log"), str) for entry in entries):
        raise ValueError("client log must contain a list of objects with log text")
    return entries


def print_client_errors(entries: list[dict[str, Any]]) -> None:
    print(f"CLIENT LUA LOG: received {len(entries)} record(s); saved in client_error_log", flush=True)
    remaining = 32000
    for entry in entries[:20]:
        trace = entry["log"][: min(6000, remaining)]
        # Do not replay control characters from client text into the terminal.
        trace = "".join(char for char in trace if char in "\n\t" or char.isprintable())
        print(trace, flush=True)
        remaining -= len(trace)
        if remaining <= 0:
            break


def make_handler(config: Config, store: Store) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GXBOffline/0.1"

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid Content-Length"})
                self.close_connection = True
                return
            if length < 0 or length > MAX_LOG_BODY:
                self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request body exceeds size limit"})
                self.close_connection = True
                return
            body = self.rfile.read(length)

            try:
                if path == "/client-log":
                    entries = decode_client_errors(body, self.headers.get("Content-Type", ""))
                    store.log_client_errors(entries)
                    print_client_errors(entries)
                    self.send_json(HTTPStatus.OK, {"received": len(entries)})
                    return
                payload = decode_form_payload(body)
                store.log_request(path, payload)
                print(f"request path={path} mid={payload.get('mid')} keys={','.join(sorted(payload))}")
                answer = response_for(payload, config)
                self.send_json(HTTPStatus.OK, answer)
            except (ValueError, UnicodeEncodeError) as error:
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
    print(f"Client Lua errors: {config.client_log_url} (uploaded about every 30 seconds after login)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
