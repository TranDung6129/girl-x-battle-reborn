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
ORIGINAL_URL = b"http://119.81.215.217:9000/center/v1"


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


def patch(apk: Path, output: Path, bootstrap_url: str) -> None:
    replacement = equal_length_url(bootstrap_url, len(ORIGINAL_URL))
    with zipfile.ZipFile(apk, "r") as source:
        content = source.read(ENTRY)
        count = content.count(ORIGINAL_URL)
        if count != 1:
            raise ValueError(f"expected one bootstrap URL in {ENTRY}, found {count}")
        patched = content.replace(ORIGINAL_URL, replacement)

        with zipfile.ZipFile(output, "w") as target:
            for info in source.infolist():
                if info.filename.startswith("META-INF/") or info.filename == "stamp-cert-sha256":
                    continue
                data = patched if info.filename == ENTRY else source.read(info.filename)
                target.writestr(info, data, compress_type=info.compress_type)

    print(f"Patched {ENTRY} -> {bootstrap_url}")
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
    args = parser.parse_args()
    if args.input_apk.resolve() == args.output_apk.resolve():
        raise SystemExit("output_apk must be a new path")
    if not args.input_apk.is_file():
        raise SystemExit(f"input APK not found: {args.input_apk}")
    patch(args.input_apk, args.output_apk, args.bootstrap_url)


if __name__ == "__main__":
    main()
