#!/usr/bin/env python3
"""Patch the primary bootstrap URL inside this APK's LuaJIT bytecode.

The replacement string is padded as a URL query so its byte length equals the
original constant; no LuaJIT bytecode offsets are changed. Existing APK
signatures are removed; the output must be zipaligned and signed before Android
installs it.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ENTRY = "assets/src_64/UpdateScene_64.lua"
LOADING_ENTRY = "assets/src_64/app/scenes/LoadingScene.lua"
SUMMON_ENTRY = "assets/src_64/app/windows/SummonWindow.lua"
ORIGINAL_URL = b"http://119.81.215.217:9000/center/v1"
SDK_LOGIN_CALL = b"\x17showLoginSdkWindow"
OFFLINE_LOGIN_CALL = b"\x15showLoginWindow_"
SDK_SELECT_SERVER = b"xydSelectServer"
ANDROID_PLATFORM = b"android"
OFFLINE_PLATFORM = b"offroid"


def equal_length_url(url: str, byte_length: int) -> bytes:
    encoded = url.encode("ascii")
    if len(encoded) > byte_length:
        raise ValueError(f"URL is {len(encoded)} bytes; maximum is {byte_length}")
    if len(encoded) == byte_length:
        return encoded

    separator = b"&" if b"?" in encoded else b"?"
    padding_length = byte_length - len(encoded) - len(separator)
    if padding_length < 1:
        raise ValueError("URL leaves no room for safe query padding")
    return encoded + separator + (b"x" * padding_length)


def bypass_android_sdk_login(chunk: bytes) -> bytes:
    """Change the startup branch from SDK login to the built-in login window.

    This is a bytecode-level patch for the supplied 1.631.0 APK.  The LuaJIT
    prototype-size field must shrink by two bytes along with the replacement
    method name.  We fail closed if this known layout changes.
    """
    call_offset = chunk.find(SDK_LOGIN_CALL)
    if call_offset != 256:
        raise ValueError(f"unexpected SDK-login call offset: {call_offset}")
    size_offset = call_offset - 172
    if chunk[size_offset : size_offset + 2] != b"\xa8\x02":
        raise ValueError("unexpected LuaJIT prototype size before SDK-login call")
    patched = (
        chunk[:size_offset]
        + b"\xa6\x02"
        + chunk[size_offset + 2 : call_offset]
        + OFFLINE_LOGIN_CALL
        + chunk[call_offset + len(SDK_LOGIN_CALL) :]
    )
    select_offset = patched.find(SDK_SELECT_SERVER)
    if select_offset < 0 or patched.count(SDK_SELECT_SERVER) != 1:
        raise ValueError("unexpected Android SDK select-server call count")
    # LoadingScene.selectServer() only calls the obsolete vendor SDK when
    # device.platform == "android".  Replacing that *specific* bytecode
    # constant with an equal-length non-platform value makes the function a
    # genuine no-op.  This is safer than redirecting to a made-up Java method:
    # LuaJavaBridge may otherwise abort a callback when the method is absent.
    platform_offset = patched.find(ANDROID_PLATFORM, select_offset, select_offset + 96)
    if platform_offset < 0:
        raise ValueError("could not locate Android branch of selectServer")
    return (
        patched[:platform_offset]
        + OFFLINE_PLATFORM
        + patched[platform_offset + len(ANDROID_PLATFORM) :]
    )


def patch(
    apk: Path,
    output: Path,
    bootstrap_url: str,
    summon_chunk: Path | None = None,
) -> None:
    replacement = equal_length_url(bootstrap_url, len(ORIGINAL_URL))
    with zipfile.ZipFile(apk, "r") as source:
        update_scene = source.read(ENTRY)
        count = update_scene.count(ORIGINAL_URL)
        if count != 1:
            raise ValueError(f"expected one bootstrap URL in {ENTRY}, found {count}")
        patched_entries = {
            ENTRY: update_scene.replace(ORIGINAL_URL, replacement),
            LOADING_ENTRY: bypass_android_sdk_login(source.read(LOADING_ENTRY)),
        }
        if summon_chunk is not None:
            chunk = summon_chunk.read_bytes()
            if not chunk.startswith(b"\x1bLJ\x02"):
                raise ValueError(f"summon chunk is not LuaJIT 2 bytecode: {summon_chunk}")
            patched_entries[SUMMON_ENTRY] = chunk

        with zipfile.ZipFile(output, "w") as target:
            for info in source.infolist():
                if info.filename.startswith("META-INF/") or info.filename == "stamp-cert-sha256":
                    continue
                data = patched_entries.get(info.filename, source.read(info.filename))
                target.writestr(info, data, compress_type=info.compress_type)

    print(f"Patched {ENTRY} -> {bootstrap_url}")
    print(f"Patched {LOADING_ENTRY} to use built-in offline login")
    if summon_chunk is not None:
        print(f"Patched {SUMMON_ENTRY} from {summon_chunk}")
    print(f"Created unsigned APK without META-INF signatures: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_apk", type=Path)
    parser.add_argument("output_apk", type=Path)
    parser.add_argument(
        "--bootstrap-url",
        default="http://127.0.0.1:18080/center/v1",
        help="local center endpoint; must fit in the original URL constant",
    )
    parser.add_argument(
        "--summon-chunk",
        type=Path,
        help="optional compatible LuaJIT bytecode to replace SummonWindow.lua",
    )
    args = parser.parse_args()
    if args.input_apk.resolve() == args.output_apk.resolve():
        raise SystemExit("output_apk must be a new path")
    if not args.input_apk.is_file():
        raise SystemExit(f"input APK not found: {args.input_apk}")
    patch(
        args.input_apk,
        args.output_apk,
        args.bootstrap_url,
        args.summon_chunk,
    )


if __name__ == "__main__":
    main()
