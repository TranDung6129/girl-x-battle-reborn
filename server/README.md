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

The script only changes the primary bootstrap URL in `UpdateScene_64.lua`; it preserves LuaJIT bytecode length by adding ignored URL-query padding and removes the old `META-INF` signatures. The resulting APK must be zipaligned and signed with a key you control before installation. Use only a local companion server and an APK you are permitted to modify.

For convenience, the `Build offline MVP APK` GitHub Actions workflow performs those steps and uploads a signed test APK as an artifact. It uses a newly generated test key on every run; the APK cannot be installed over the original signed game and must not be used for production distribution.
