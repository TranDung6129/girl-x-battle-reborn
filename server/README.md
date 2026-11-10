# Offline companion server (MVP)

`offline_server.py` is a deliberately small local server for validating the APK protocol. It implements:

- bootstrap (`mid` 20480) and version check (`mid` 2);
- region list (`mid` 18), token retrieval (`mid` 1), announcement and server time;
- request recording in SQLite so each missing game response can be implemented from evidence.

It binds to `127.0.0.1:18080` by default, so it is not exposed to the network.

```sh
python3 offline_server.py --db offline-state.sqlite3
curl http://127.0.0.1:18080/healthz
```

This is a protocol scaffold, not yet a playable offline server. After the APK connects, inspect the `request_log` SQLite table to implement the next `mid` values with the response shapes required by the client.

To print the recorded requests with `sid`, `token`, and `login_token` redacted:

```sh
python3 show_requests.py offline-state.sqlite3
```

## Patching the APK

On a development machine, create an unsigned copy that targets the local bootstrap endpoint:

```sh
python3 tools/patch_bootstrap_url.py original.apk patched-unsigned.apk
```

The script changes the primary bootstrap URL in `UpdateScene_64.lua`, bypasses the unavailable Android vendor SDK in `LoadingScene.lua` (including its select-server callback), and removes the old `META-INF` signatures. The bootstrap replacement preserves LuaJIT bytecode length with ignored URL-query padding; the SDK bypass uses a guarded version-specific bytecode patch. The resulting APK must be zipaligned and signed with a key you control before installation. Use only a local companion server and an APK you are permitted to modify.

For convenience, the `Build offline MVP APK` GitHub Actions workflow performs those steps and uploads a signed test APK as an artifact. It uses a newly generated test key on every run; the APK cannot be installed over the original signed game and must not be used for production distribution.

## Restoring visual resources

The base 1.631.0 APK contains the Lua client but not the game's downloadable
images, Cocos UI files, skeletons, and sounds. The client looks for those files
under its Android writable directory, specifically
`Android/data/com.carolgames.gxb/files/res/web`.

A community-preserved archive matching 1.631.0 is available from the
[Girls X Battle Asset Archive](https://archive.org/details/girls-x-battle-asset-unified-merge).
Download `gxb1_lazy_unified_assets_verified_1.631.0_25420.tar.zst`, then, with
one Android device connected by ADB, run:

```sh
chmod +x tools/install_archived_assets_adb.sh
tools/install_archived_assets_adb.sh ~/Downloads/gxb1_lazy_unified_assets_verified_1.631.0_25420.tar.zst
```

The installer verifies SHA-256 before extracting or copying anything and only
writes the app's own `files/res` directory. It does not replace the APK.
