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

The base 1.631.0 APK contains both the Lua client and many visual resources,
including `res/windows/summon/summon.csb`, the `lvmeng` character animation,
and the `summon_click`/`mofaniudanji` effects. A `0%` indicator is not evidence
that these files are absent. Other resources are downloaded lazily.

The current installer copies the preserved archive to external
`Android/data/com.carolgames.gxb/files/res/web`. **That copy alone has not been
verified to satisfy the client's cache.** The client constructs its update
root from `getSupportPath() + packageName + '/'` and tracks downloads in
`lazyFile.json`; copying files does not update that catalogue. The installer's
success message confirms the copy, not in-game loading.

The APK's Java `Cocos2dxHelper.init` assigns `sFileDirectory` from
`Activity.getFilesDir().getAbsolutePath()`, and `getCocos2dxWritablePath()`
returns that field. This points to the app's internal files directory, not
the external `/sdcard/Android/data/.../files` directory used by the installer.
Do not assume ADB can write that internal directory on an unrooted device.

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

## Capturing the actual Lua error (no APK reinstall)

The token response now supplies a local `log_url`. The client's existing error
uploader sends compressed Lua tracebacks approximately every 30 seconds after
login. The server decodes the multipart/zlib request, saves it in SQLite's
`client_error_log` table, and prints `CLIENT LUA LOG` followed by the traceback.
It only acknowledges an upload after saving it, because the client deletes its
local copy on HTTP 200. Native crash dumps are not accepted by this endpoint.

Restart the updated server and force-stop/relaunch the app so it fetches a new
token. Reproduce the white Vending screen and leave the app in the foreground
for 40–60 seconds. Copy the `CLIENT LUA LOG` block from the server console.

Protocol checks: `python3 -m unittest discover -s server -p 'test_*.py'` from the
repository root.

## Offline summon sandbox

MID 50 now returns persisted level-one heroes from a small test pool
(`10001001`, `10001002`, `10001003`, `10001004`, `10001006`). Mana Buy 1/10/100
and Crystal Buy 1/10 use the counts in the client tables. These test draws are
free, permit duplicates with distinct instance IDs, and do not reproduce the
original reward rates or economy. Unsupported type/index pairs are rejected.
Heroes are saved transactionally in `offline-state.sqlite3` and included in
the next login's MID 49 roster. Each accepted request is a separate draw;
the original request has no idempotency key, so resending it grants again.

For free exploration the initial forced tutorial is marked complete using the
client's actual `GuideStoryType.GUIDE_END = 100197`. MID 26 saves story state
without allowing stale tutorial uploads to roll this back. This skips the
initial tutorial; it does not unlock all game modes or implement Campaign.
Restart the server and force-stop/relaunch the existing APK to receive this
state. Do not delete the SQLite database if you want to retain drawn heroes.

The result/first-encounter UI and its resources still require Android testing;
successful server draws alone do not prove those screens render correctly.

### Vending traceback fix

The device traceback identifies `SkinDynamicTable.pos` called by
`SummonWindow.sxMachineSetUp` before the window is attached to its parent.
The client tests `main_ids[selected]` for a dynamic skin but looks up animation
coordinates using `partner_id`. The old server paired dynamic `10001001` with
`partner_id=10001003`, which has no `skin_dynamic` row. The server now uses
`10001001` for both featured slots. This preserves the original client layout;
it is not a missing-CSB or missing-Magic-effect fix.

To reproduce the old nil-index exception and verify the corrected lookup using
the original extracted bytecode:

```sh
luajit tools/check_summon_contract.lua path/to/assets/src_64 10001001
```

The server also provides the empty collection/status fields required by the
library, Illusion, friends, and achievement callbacks in the same device log.
This does not implement those game systems or establish that the `0%` resource
loading issue is fixed. The older 0.6 APK still has Magic setup disabled; no new
APK is needed to test these server corrections.
