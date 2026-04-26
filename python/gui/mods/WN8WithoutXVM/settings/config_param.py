from .config_param_types import (
    CheckboxParameter,
    DropdownParameter,
    OptionItem
)
from .translations import Translator


class WinratePosition(object):
    NEAR_ICON = 'near_icon'
    BEFORE_VEHICLE = 'before_vehicle'
    NONE = 'none'


class ApiRegion(object):
    EU = 'eu'
    NA = 'na'
    ASIA = 'asia'


class ConfigParams(object):

    def __init__(self):
        self.enabled = CheckboxParameter(
            ['enabled'],
            defaultValue=True
        )

        self.showWn8 = CheckboxParameter(
            ['show-wn8'],
            defaultValue=True
        )

        self.showWinrate = CheckboxParameter(
            ['show-winrate'],
            defaultValue=True
        )

        self.showBattles = CheckboxParameter(
            ['show-battles'],
            defaultValue=True
        )

        self.panelWinratePosition = DropdownParameter(
            ['panel-winrate-position'],
            [
                OptionItem(WinratePosition.NEAR_ICON, 0, Translator.WINRATE_NEAR_ICON),
                OptionItem(WinratePosition.BEFORE_VEHICLE, 1, Translator.WINRATE_BEFORE_VEHICLE),
                OptionItem(WinratePosition.NONE, 2, Translator.WINRATE_NONE),
            ],
            defaultValue=WinratePosition.NEAR_ICON
        )

        self.wgApiRegion = DropdownParameter(
            ['wg-api-region'],
            [
                OptionItem(ApiRegion.EU, 0, Translator.REGION_EU),
                OptionItem(ApiRegion.NA, 1, Translator.REGION_NA),
                OptionItem(ApiRegion.ASIA, 2, Translator.REGION_ASIA),
            ],
            defaultValue=ApiRegion.EU
        )

    def items(self):
        result = {}
        for attrName in dir(self):
            if not attrName.startswith('_') and attrName != 'items':
                try:
                    attr = getattr(self, attrName)
                    if hasattr(attr, 'tokenName') and hasattr(attr, 'defaultValue'):
                        result[attr.tokenName] = attr
                except Exception:
                    continue
        return result


g_configParams = ConfigParams()
