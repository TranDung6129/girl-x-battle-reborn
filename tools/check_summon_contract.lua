-- Run against the extracted, ORIGINAL APK bytecode, not decompiled source:
-- luajit tools/check_summon_contract.lua <assets/src_64> <partner_id>
local root, partner = assert(arg[1]), assert(tonumber(arg[2]))
function class()
    return {}
end
xyd = {splitToNumber = function(text)
    local values = {}
    for part in text:gmatch('[^|]+') do
        values[#values + 1] = tonumber(part)
    end
    return values
end}
function import(name)
    assert(name == 'app.common.tables.TableParser')
    return {parse = function(filename, callback)
        local data = dofile(root .. '/data/tables/' .. filename)
        for _, values in pairs(data.rows) do
            local row = {}
            for index, key in ipairs(data.keys) do row[key] = values[index] end
            callback(row)
        end
    end}
end
local SkinDynamic = dofile(root .. '/app/common/tables/SkinDynamicTable.lua')
local skin = setmetatable({}, {__index = SkinDynamic})
skin:ctor()
-- Reproduce the exact lookup in the supplied traceback. The old response
-- used 10001003 here even though main_ids[1] selects dynamic 10001001.
local ok, err = pcall(function() return skin:pos(10001003, 1) end)
assert(not ok and tostring(err):find('nil'), 'old response must reproduce nil-index failure')
for position = 1, 7 do
    local value = skin:pos(partner, position)
    assert(type(value.x) == 'number' and type(value.y) == 'number')
end
assert(skin:path(partner) ~= '', 'featured dynamic model needs an animation path')
print('PASS: old featured ID reproduces traceback; corrected ID resolves all 7 animation positions')
