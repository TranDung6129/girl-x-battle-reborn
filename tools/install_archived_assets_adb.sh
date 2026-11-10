#!/usr/bin/env bash
# Install the preserved 1.631.0 resource archive into a USB-connected device.
# The APK searches its writable Cocos path for res/web before bundled assets.
set -euo pipefail

readonly EXPECTED_SHA256='2c6dfd574ca01d917f263bb9e16abe4681ffb7c682382856af0a9661a15631ae'
readonly REMOTE_ROOT='/sdcard/Android/data/com.carolgames.gxb/files'

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/gxb1_lazy_unified_assets_verified_1.631.0_25420.tar.zst" >&2
  exit 2
fi

archive=$1
for command in adb sha256sum tar zstd mktemp; do
  command -v "$command" >/dev/null || {
    echo "Required command not found: $command" >&2
    exit 1
  }
done
[[ -f "$archive" ]] || { echo "Archive not found: $archive" >&2; exit 1; }

actual_sha256=$(sha256sum "$archive" | awk '{print $1}')
[[ "$actual_sha256" == "$EXPECTED_SHA256" ]] || {
  echo "Checksum mismatch; refusing to install this archive." >&2
  echo "Expected: $EXPECTED_SHA256" >&2
  echo "Actual:   $actual_sha256" >&2
  exit 1
}

adb get-state >/dev/null
temporary_dir=$(mktemp -d -t gxb-assets.XXXXXX)
trap 'rm -rf "$temporary_dir"' EXIT

echo "Extracting the verified resource archive…"
zstd -dc "$archive" | tar -x -C "$temporary_dir"
[[ -d "$temporary_dir/res/web" ]] || {
  echo "Archive does not contain res/web; refusing to alter the device." >&2
  exit 1
}

asset_size=$(du -sh "$temporary_dir/res" | awk '{print $1}')
echo "Installing $asset_size under $REMOTE_ROOT/res on the device…"
adb shell am force-stop com.carolgames.gxb
adb shell mkdir -p "$REMOTE_ROOT"
adb push "$temporary_dir/res" "$REMOTE_ROOT/"
adb shell test -d "$REMOTE_ROOT/res/web"

echo
echo "Assets installed. Start the offline server, run adb reverse tcp:18080 tcp:18080, then launch the game."
