-- Conservative offline replacement for the Gacha window's controller.
--
-- The 1.631.0 APK already contains its matching summon.csb and textures.  The
-- original controller also creates an optional Magic-Gacha Spine effect during
-- startup, even when that feature is locked.  That effect belongs to a missing
-- lazy resource set and makes this entire window render blank offline.
--
-- Keep the original Cocos Studio layout and make this screen displayable first.
-- Summon transactions are deliberately not implemented by this recovery stub.

local OfflineSummonWindow = class("SummonWindow", import("app.common.ui.BaseWindow"))

function OfflineSummonWindow:ctor(name, params)
    OfflineSummonWindow.super.ctor(self, name, params)
end

function OfflineSummonWindow:willOpen()
    local title = self:nodeByName("top_container")

    if title and title:getChildByName("title_txt") then
        title:getChildByName("title_txt"):setString(
            xyd.tables.translation:translation("SUMMON_WND_TITLE1")
        )
    end

    local back = self:nodeByName("return") or self:closeButton()

    if back then
        back:addTouchEventListener(function(_, event)
            if event == ccui.TouchEventType.ended then
                xyd.WindowManager.get():closeWindow(self)
            end
        end)
    end
end

return OfflineSummonWindow
