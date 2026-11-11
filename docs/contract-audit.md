# Client/server contract audit

We have original LuaJIT client bytecode, not the original server source. A request
name and its payload do not specify the complete response, durable state changes,
reward distributions or all branch-dependent invariants. Decompiled Lua is only
a reading aid; its control-flow reconstruction can be wrong. Tests should execute
the original bytecode where practical, and Android tests remain necessary for UI.

`client-contract-catalog.json` inventories all 1,210 named MIDs in the supplied
APK and candidate source references. Candidates are encoded string matches, not
verified call sites. The catalog deliberately labels schemas unverified; it is
not 1,210 working endpoints. Regenerate with:

```sh
python3 tools/export_contract_catalog.py path/to/assets/src_64 /path/to/luajit docs/client-contract-catalog.json
```

For each feature, audit request -> model callback -> dispatched event -> window
consumer -> persistence -> failure/retry path. Include initial login bundles,
one/multiple results, duplicate grants, reopen/restart, and locked/unlocked states.
Do not regard HTTP 200 or a non-crashing model test as full UI verification.

## Current repair batch

| Area | Evidence and repair | Remaining limit |
|---|---|---|
| Feature gates | `SelfPlayer.genOpenFuncMap/isFuncOpen` uses `func_ids`, independently of displayed level. Populate level-only gates <=100 with open_control=1 from function.lua. | Campaign/hero-count gates are not fabricated as complete; exposing a button does not implement its backend. |
| Feature guides | utils.lua reads string-keyed `guide_function_ids`; MID 2865 must not reset it to empty. Mark all 20 feature guides complete for free exploration. | Separate from story guide_id. |
| Store activities | MID 229 must contain `list`; otherwise Activities replaces its initialized array with nil and refreshRedMark fails. Return empty list at login and on demand. | No live events or store economy implemented. Store itself has a chapter-2 gate. |
| LoginWindow | Default callback sorts regions descending then selects entry 4 (2 in debug). Supply four local aliases backed by the same offline account. | Does not prove every first-connect failure fixed. |
| Chat | MID 192 formerly returned generic success with nil host/port. Return HTTP 503 so Backend uses its failure callback. | No TCP chat server; background retries are expected. |
| SX draw | summon.lua row 4 has summon_num=6. One result takes a single-item animation path incompatible with SX node positions. Return six results. | Test close/skip on Android; reward pool is sandbox, not original rates. |
| Magic Gachapon | Function 96; MIDs 70/71 grant owned-hero stones and select target; persist items/selection. | Free sandbox, one stone per result, no original economy. |
| Old duplicate heroes | Return MIN(partner_id) per table_id consistently on login and MID49. | All old rows retained for recovery; no deletion or duplicate compensation. Current DB stores no individual hero progression. |

## Still open

- Verify first launch without Retry using a fresh start-to-login device log. The
  uploaded sample begins after login and cannot establish which request failed.
- Verify SX closes after skip and after six complete animations.
- Implement and test actual battle, store inventory/purchases and other unlocked
  systems as complete feature groups. Most catalog entries remain unsupported.
