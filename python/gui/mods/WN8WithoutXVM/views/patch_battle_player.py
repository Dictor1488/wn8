import inspect
import weakref
from functools import wraps

from ..utils import (
    logger,
    get_wn8_color,
    get_winrate_color,
    get_battles_color,
    get_format_battles
)
from ..settings.config_param import g_configParams


EXTRA_FIELDS = (
    'winrate',
    'winrate_color',
    'wn8',
    'wn8_color',
    'battles',
    'battles_color',
)

SEP = u'\t'


class PatchBattlePlayer(object):
    """
    TAB stats patch.

    Keep userName untouched. Extra BattlePlayer fields are still filled, but on
    current client they may stay empty in Gameface, so stats are also packed
    into vehicleName. Patched TabView.js must render vehicleName.split(TAB)[0]
    as the visible tank name and use the hidden parts for WN8/WR/battles.
    """

    def __init__(self, stats_manager):
        self._original_battle_player_constructor = None
        self._original_battle_player_initialize = None
        self._original_fill_player_model = None
        self._original_invalidate_personal_info = None
        self._patches_applied = False
        self._stats_manager = stats_manager
        # vehicleId -> (player, vehicleInfo, original_vehicle_name, tabView weakref)
        self._active_players = {}
        self._original_property_count = None
        self._base_index = None
        stats_manager.add_update_callback(self._on_stats_updated)

    def _discover_property_count(self, original_init):
        try:
            argspec = inspect.getargspec(original_init)
            if argspec.defaults and 'properties' in argspec.args:
                idx = argspec.args.index('properties') - 1
                if 0 <= idx < len(argspec.defaults):
                    self._original_property_count = argspec.defaults[idx]
        except Exception as e:
            logger.debug('[PatchBattlePlayer] property discovery failed: %s', e)

        if self._original_property_count is None:
            self._original_property_count = 37
        self._base_index = self._original_property_count
        logger.debug('[PatchBattlePlayer] base_index=%s', self._base_index)

    def _make_getter(self, offset):
        def getter(self_):
            try:
                return self_._getString(self._base_index + offset)
            except Exception:
                return ''
        return getter

    def _make_setter(self, offset):
        def setter(self_, value):
            try:
                self_._setString(self._base_index + offset, value if value else '')
            except Exception:
                pass
        return setter

    def _strip_payload(self, value):
        try:
            value = value or u''
            if SEP in value:
                return value.split(SEP, 1)[0]
            return value
        except Exception:
            return value or u''

    def _refresh_tab_player(self, tv_ref, player):
        try:
            tv = tv_ref() if tv_ref else None
            if tv is not None:
                tv.modifyBattlePlayer(player)
                return True
        except Exception as e:
            logger.debug('[PatchBattlePlayer] modifyBattlePlayer failed: %s', e)
        return False

    def _on_stats_updated(self, account_id):
        try:
            for vehicle_id, (player, vehicle_info, original_vehicle_name, tv_ref) in list(self._active_players.items()):
                if vehicle_info.get('accountDBID') == account_id:
                    if self._set_values(player, vehicle_info, original_vehicle_name):
                        self._refresh_tab_player(tv_ref, player)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] update failed: %s', e)

    def _monkey_patch_battle_player(self):
        try:
            from gui.impl.gen.view_models.common.battle_player import BattlePlayer
        except Exception as e:
            logger.error('[PatchBattlePlayer] BattlePlayer import failed: %s', e)
            return False

        try:
            self._original_battle_player_constructor = BattlePlayer.__init__
            self._original_battle_player_initialize = BattlePlayer._initialize
            self._discover_property_count(self._original_battle_player_constructor)

            extra = len(EXTRA_FIELDS)
            base_count = self._original_property_count

            def patched_constructor(bp_self, properties=None, commands=0):
                if properties is not None and properties != base_count:
                    total = properties + extra
                else:
                    total = base_count + extra
                try:
                    self._original_battle_player_constructor(bp_self, properties=total, commands=commands)
                except Exception:
                    self._original_battle_player_constructor(bp_self, commands=commands)

            def patched_initialize(bp_self):
                try:
                    self._original_battle_player_initialize(bp_self)
                except Exception:
                    return
                try:
                    for field in EXTRA_FIELDS:
                        default = '#FFFFFF' if field.endswith('_color') else ''
                        bp_self._addStringProperty(field, default)
                except Exception as e:
                    logger.debug('[PatchBattlePlayer] addStringProperty failed: %s', e)

            BattlePlayer.__init__ = patched_constructor
            BattlePlayer._initialize = patched_initialize

            method_pairs = (
                ('Winrate', 0), ('WinrateColor', 1),
                ('Wn8', 2), ('Wn8Color', 3),
                ('Battles', 4), ('BattlesColor', 5),
            )
            for method_name, offset in method_pairs:
                setattr(BattlePlayer, 'get' + method_name, self._make_getter(offset))
                setattr(BattlePlayer, 'set' + method_name, self._make_setter(offset))

            logger.debug('[PatchBattlePlayer] BattlePlayer patched (base=%s, extras=%s)', base_count, extra)
            return True
        except Exception as e:
            logger.error('[PatchBattlePlayer] BattlePlayer patch failed: %s', e)
            import traceback
            logger.error('[PatchBattlePlayer] Traceback: %s', traceback.format_exc())
            return False

    def _monkey_patch_tab_view(self):
        try:
            from gui.impl.battle.battle_page.tab_view import TabView
        except Exception as e:
            logger.error('[PatchBattlePlayer] TabView import failed: %s', e)
            return False

        try:
            self._original_fill_player_model = TabView._fillPlayerModel

            @wraps(self._original_fill_player_model)
            def patched_fill_player_model(tv_self, vehicleId, vehicleInfo):
                player = self._original_fill_player_model(tv_self, vehicleId, vehicleInfo)
                if player and vehicleInfo:
                    tv_ref = weakref.ref(tv_self)
                    original_vehicle_name = u''
                    try:
                        if hasattr(player, 'getVehicleName'):
                            original_vehicle_name = self._strip_payload(player.getVehicleName() or u'')
                    except Exception:
                        original_vehicle_name = u''
                    self._active_players[vehicleId] = (player, vehicleInfo, original_vehicle_name, tv_ref)
                    self._set_values(player, vehicleInfo, original_vehicle_name)
                return player

            TabView._fillPlayerModel = patched_fill_player_model

            if hasattr(TabView, '_invalidatePersonalInfo'):
                self._original_invalidate_personal_info = TabView._invalidatePersonalInfo

                @wraps(self._original_invalidate_personal_info)
                def patched_invalidate_personal_info(tv_self, player):
                    self._original_invalidate_personal_info(tv_self, player)
                    try:
                        if hasattr(player, 'getVehicleId'):
                            vehicleId = player.getVehicleId()
                            if vehicleId and vehicleId in self._active_players:
                                _, info, original_vehicle_name, tv_ref = self._active_players[vehicleId]
                                if self._set_values(player, info, original_vehicle_name):
                                    self._refresh_tab_player(tv_ref, player)
                    except Exception as e:
                        logger.debug('[PatchBattlePlayer] invalidate refresh failed: %s', e)

                TabView._invalidatePersonalInfo = patched_invalidate_personal_info

            logger.debug('[PatchBattlePlayer] TabView patched')
            return True
        except Exception as e:
            logger.error('[PatchBattlePlayer] TabView patch failed: %s', e)
            import traceback
            logger.error('[PatchBattlePlayer] Traceback: %s', traceback.format_exc())
            return False

    def _set_values(self, player, vehicleInfo, original_vehicle_name):
        try:
            account_id = vehicleInfo.get('accountDBID') if vehicleInfo else None
            if not account_id:
                return False

            stats = self._stats_manager.get_cached_stats(account_id)
            if not stats:
                return False

            wn8 = int(stats.get('wn8', 0) or 0)
            winrate = float(stats.get('winrate', 0) or 0)
            battles = int(stats.get('battles', 0) or 0)

            wn8_text = str(wn8) if g_configParams.showWn8.value and wn8 else ''
            winrate_text = ('%.1f%%' % winrate) if g_configParams.showWinrate.value and winrate else ''
            battles_text = get_format_battles(battles) if g_configParams.showBattles.value and battles else ''

            wn8_color = get_wn8_color(wn8) if wn8 else '#FFFFFF'
            wr_color = get_winrate_color(winrate) if winrate else '#FFFFFF'
            b_color = get_battles_color(battles) if battles else '#FFFFFF'

            # Fill extra fields too, for clients where they work.
            if hasattr(player, 'setWn8Color'):
                player.setWn8Color(wn8_color)
            if hasattr(player, 'setWinrateColor'):
                player.setWinrateColor(wr_color)
            if hasattr(player, 'setBattlesColor'):
                player.setBattlesColor(b_color)
            if hasattr(player, 'setWn8'):
                player.setWn8(wn8_text)
            if hasattr(player, 'setWinrate'):
                player.setWinrate(winrate_text)
            if hasattr(player, 'setBattles'):
                player.setBattles(battles_text)

            # Reliable transport for current Gameface: visible name is part [0].
            if hasattr(player, 'setVehicleName'):
                payload = SEP.join((
                    original_vehicle_name or u'',
                    wn8_text,
                    wn8_color,
                    winrate_text,
                    wr_color,
                    battles_text,
                    b_color,
                ))
                player.setVehicleName(payload)

            logger.debug('[PatchBattlePlayer] values set acc=%s vehicle=%s wn8=%s wr=%s battles=%s',
                         account_id, original_vehicle_name, wn8_text, winrate_text, battles_text)
            return True
        except Exception as e:
            logger.debug('[PatchBattlePlayer] setValues failed: %s', e)
            return False

    def apply_patches(self):
        if self._patches_applied:
            return True
        success = 0
        if self._monkey_patch_battle_player():
            success += 1
        if self._monkey_patch_tab_view():
            success += 1
        self._patches_applied = success == 2
        return self._patches_applied

    def remove_patches(self):
        try:
            try:
                if self._stats_manager is not None:
                    self._stats_manager.remove_update_callback(self._on_stats_updated)
            except Exception as e:
                logger.debug('[PatchBattlePlayer] callback unsubscribe failed: %s', e)

            if not self._patches_applied:
                self._active_players.clear()
                return True

            from gui.impl.gen.view_models.common.battle_player import BattlePlayer
            from gui.impl.battle.battle_page.tab_view import TabView

            if self._original_battle_player_constructor:
                BattlePlayer.__init__ = self._original_battle_player_constructor
            if self._original_battle_player_initialize:
                BattlePlayer._initialize = self._original_battle_player_initialize
                for method_name in (
                    'getWinrate', 'setWinrate', 'getWinrateColor', 'setWinrateColor',
                    'getWn8', 'setWn8', 'getWn8Color', 'setWn8Color',
                    'getBattles', 'setBattles', 'getBattlesColor', 'setBattlesColor',
                ):
                    if hasattr(BattlePlayer, method_name):
                        try:
                            delattr(BattlePlayer, method_name)
                        except AttributeError:
                            pass

            if self._original_fill_player_model:
                TabView._fillPlayerModel = self._original_fill_player_model
            if self._original_invalidate_personal_info:
                TabView._invalidatePersonalInfo = self._original_invalidate_personal_info

            self._active_players.clear()
            self._patches_applied = False
            return True
        except Exception as e:
            logger.debug('[PatchBattlePlayer] remove failed: %s', e)
            return False

    def is_patched(self):
        return self._patches_applied
