#!/usr/bin/env python3
"""Run original client handlers: <assets/src_64> <luajit>, no Android UI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from offline_server import Config, offline_start_detail, response_for
from patch_bootstrap_url import default_main_background


def lua(value):
    if isinstance(value, dict):
        return '{' + ','.join('[' + lua(k) + ']=' + lua(v) for k, v in value.items()) + '}'
    if isinstance(value, list):
        return '{' + ','.join(map(lua, value)) + '}'
    return json.dumps(value)


root, executable = Path(sys.argv[1]).resolve(), sys.argv[2]
bg = root / 'app/common/tables/LibraryBGTable.lua'
with tempfile.TemporaryDirectory() as folder:
    patched = Path(folder) / 'LibraryBGTable.lua'
    patched.write_bytes(default_main_background(bg.read_bytes()))
    code = f'''
local root = {lua(str(root))}
function class() return {{}} end
xyd = {{tables = {{translation = {{}}}}}}
package.preload['framework.scheduler'] = function() return {{}} end
function import(name)
    if name ~= 'app.common.tables.TableParser' then return {{}} end
    return {{parse = function(name, callback)
        local data = dofile(root .. '/data/tables/' .. name .. '.lua')
        for _, values in pairs(data.rows) do
            local row = {{}}
            for i, key in ipairs(data.keys) do row[key] = values[i] end
            callback(row)
        end
    end}}
end
local Original = dofile({lua(str(bg))})
local original = setmetatable({{}}, {{__index=Original}})
original:ctor()
assert(original:getBG(nil) == '')
local Patched = dofile({lua(str(patched))})
local fixed = setmetatable({{}}, {{__index=Patched}})
fixed:ctor()
assert(fixed:getBG(nil) == 'images/main_scene.png')
for id=1,12 do assert(fixed:getBG(id) == original:getBG(id)) end
print('PASS: original nil background reproduced; fallback fixed; all 12 valid paths preserved')
local Player = dofile(root .. '/app/model/SelfPlayer.lua')
local player = setmetatable({{}}, {{__index=Player}})
local ok, err = pcall(function() player:worldMapEvent_({{params={{}}}}) end)
assert(not ok and tostring(err):find('table expected'))
player:worldMapLoginEvent_({{params={lua(offline_start_detail(0)['112'])}}})
assert(player.normal_chapter_id == 1 and player.normal_campaign_id == 100001)
player:worldMapEvent_({{params={lua(response_for({'mid':112}, Config('127.0.0.1',18080)))}}})
assert(player.worldMaps_[100001].star == 0)
assert(player.worldMaps_[100019].dailyLimit == 3)
assert(player.worldMaps_[24163].resetCount == 0)
local n = 0
for _ in pairs(player.worldMaps_) do n = n + 1 end
assert(n == 35)
print('PASS: original pairs(nil) reproduced; login/map responses accepted by original SelfPlayer bytecode')
player.funcIDs = {lua(offline_start_detail(0)['17']['func_ids'])}
player:genOpenFuncMap()
assert(player:isFuncOpen(96))
assert(not player:isFuncOpen(5))
local functions = dofile(root .. '/data/tables/function.lua')
local expected = {{}}
for _, row in pairs(functions.rows) do
    local data = {{}}
    for i,k in ipairs(functions.keys) do data[k] = row[i] end
    local kind, level = data.level:match('^(%d+)|(%d+)$')
    if kind == '1' and tonumber(level) <= 100 and tonumber(data.open_control) == 1 then
        expected[tonumber(data.id)] = true
        assert(player:isFuncOpen(tonumber(data.id)))
    end
end
for _, id in ipairs(player.funcIDs) do assert(expected[id]) end
local summons = dofile(root .. '/data/tables/summon.lua')
for _, row in pairs(summons.rows) do
    local data = {{}}
    for i,k in ipairs(summons.keys) do data[k] = row[i] end
    if tonumber(data.id) == 4 then assert(tonumber(data.summon_num) == 6) end
end
print('PASS: original feature-gate handler unlocks Gachapon; function flags and SX count match APK tables')
'''
    subprocess.run([executable, '-'], input=code, text=True, check=True)
