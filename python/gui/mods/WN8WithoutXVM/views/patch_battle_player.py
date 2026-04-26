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

import logging
logger.setLevel(logging.DEBUG)

EXTRA_FIELDS = (
    'winrate',
    'winrate_color',
    'wn8',
    'wn8_color',
    'battles',
    'battles_color',
)


class PatchBattlePlayer(object):

    def __init__(self, stats_manager):
        self._original_battle_player_constructor = None
        self._original_battle_player_initialize = None
        self._original_fill_player_model = None
        self._original_fill_player_list_model = None
        self._original_invalidate_personal_info = None
        self._patches_applied = False
        self._stats_manager = stats_manager
        self._active_players = {}
        self._tab_view_instances = []
        self._original_property_count = None
        self._base_index = None
        # vehicleId -> property_index_map (field_name -> property_index)
        self._player_prop_indices = {}
        stats_manager.add_update_callback(self._on_stats_updated)

    def _discover_property_count(self, original_init):
        try:
            argspec = inspect.getargspec(original_init)
            if argspec.defaults and 'properties' in argspec.args:
                idx = argspec.args.index('properties') - 1
                if 0 <= idx < len(argspec.defaults):
                    self._original_property_count = argspec.defaults[idx]
        except Exception as e:
            logger.debug('[PatchBattlePlayer] inspect failed: %s', e)

        if self._original_property_count is None:
            self._original_property_count = 37

        self._base_index = self._original_property_count
        logger.debug('[PatchBattlePlayer] base_index=%s', self._base_index)

    def _on_stats_updated(self, account_id):
        try:
            for vehicle_id, (player, vehicle_info, tv_ref, prop_map) in list(self._active_players.items()):
                if vehicle_info.get('accountDBID') == account_id:
                    self._set_values(player, vehicle_info, prop_map)
                    tv = tv_ref() if tv_ref else None
                    if tv is not None:
                        self._refresh_player(tv, player)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _on_stats_updated failed: %s', e)

    def _refresh_player(self, tv, player):
        try:
            if hasattr(tv, 'modifyBattlePlayer'):
                tv.modifyBattlePlayer(player)
            elif self._original_invalidate_personal_info:
                self._original_invalidate_personal_info(tv, player)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _refresh_player failed: %s', e)

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
            patch_self = self

            def patched_constructor(bp_self, properties=None, commands=0):
                total = (properties + extra) if (properties is not None and properties != base_count) else (base_count + extra)
                try:
                    patch_self._original_battle_player_constructor(bp_self, properties=total, commands=commands)
                except Exception:
                    patch_self._original_battle_player_constructor(bp_self, commands=commands)

            def patched_initialize(bp_self):
                try:
                    patch_self._original_battle_player_initialize(bp_self)
                except Exception:
                    return
                try:
                    prop_map = {}
                    for field in EXTRA_FIELDS:
                        default = '#FFFFFF' if field.endswith('_color') else ''
                        idx = bp_self._addStringProperty(field, default)
                        prop_map[field] = idx
                        logger.debug('[PatchBattlePlayer] _addStringProperty(%s) -> index=%s', field, idx)

                    # Зберігаємо prop_map на самому об'єкті для подальшого використання
                    object.__setattr__(bp_self, '_wn8_prop_map', prop_map)
                except Exception as e:
                    logger.debug('[PatchBattlePlayer] addStringProperty failed: %s', e)

            BattlePlayer.__init__ = patched_constructor
            BattlePlayer._initialize = patched_initialize

            # Додаємо методи що використовують prop_map або _setString за індексом
            def make_name_setter(field_name):
                def setter(bp_self, value):
                    try:
                        # Спосіб 1: через prop_map + _setPropertyByIndex якщо є
                        prop_map = object.__getattribute__(bp_self, '_wn8_prop_map') if hasattr(bp_self, '_wn8_prop_map') else {}
                        if field_name in prop_map and prop_map[field_name] is not None:
                            idx = prop_map[field_name]
                            if hasattr(bp_self, '_setPropertyByIndex'):
                                bp_self._setPropertyByIndex(idx, value or '')
                                return
                        # Спосіб 2: _setString за offset
                        offset = EXTRA_FIELDS.index(field_name)
                        bp_self._setString(patch_self._base_index + offset, value or '')
                    except Exception as e:
                        logger.debug('[PatchBattlePlayer] setter %s failed: %s', field_name, e)
                return setter

            def make_name_getter(field_name):
                def getter(bp_self):
                    try:
                        prop_map = object.__getattribute__(bp_self, '_wn8_prop_map') if hasattr(bp_self, '_wn8_prop_map') else {}
                        if field_name in prop_map and prop_map[field_name] is not None:
                            idx = prop_map[field_name]
                            if hasattr(bp_self, '_getPropertyByIndex'):
                                return bp_self._getPropertyByIndex(idx)
                        offset = EXTRA_FIELDS.index(field_name)
                        return bp_self._getString(patch_self._base_index + offset)
                    except Exception:
                        return ''
                return getter

            method_map = {
                'winrate': ('Winrate', 'setWinrate', 'getWinrate'),
                'winrate_color': ('WinrateColor', 'setWinrateColor', 'getWinrateColor'),
                'wn8': ('Wn8', 'setWn8', 'getWn8'),
                'wn8_color': ('Wn8Color', 'setWn8Color', 'getWn8Color'),
                'battles': ('Battles', 'setBattles', 'getBattles'),
                'battles_color': ('BattlesColor', 'setBattlesColor', 'getBattlesColor'),
            }

            for field, (cap, setter_name, getter_name) in method_map.items():
                setattr(BattlePlayer, setter_name, make_name_setter(field))
                setattr(BattlePlayer, getter_name, make_name_getter(field))

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
                if player is not None:
                    self._register_tab_view_instance(tv_self)
                    tv_ref = weakref.ref(tv_self)
                    prop_map = getattr(player, '_wn8_prop_map', {}) if hasattr(player, '_wn8_prop_map') else {}
                    self._active_players[vehicleId] = (player, vehicleInfo or {}, tv_ref, prop_map)
                    self._set_values(player, vehicleInfo or {}, prop_map)
                return player

            TabView._fillPlayerModel = patched_fill_player_model

            if hasattr(TabView, '_fillPlayerListModel'):
                self._original_fill_player_list_model = TabView._fillPlayerListModel

                @wraps(self._original_fill_player_list_model)
                def patched_fill_list(tv_self, *args, **kwargs):
                    result = self._original_fill_player_list_model(tv_self, *args, **kwargs)
                    self._register_tab_view_instance(tv_self)
                    return result

                TabView._fillPlayerListModel = patched_fill_list

            if hasattr(TabView, '_invalidatePersonalInfo'):
                self._original_invalidate_personal_info = TabView._invalidatePersonalInfo

                @wraps(self._original_invalidate_personal_info)
                def patched_invalidate(tv_self, player):
                    self._original_invalidate_personal_info(tv_self, player)
                    try:
                        if hasattr(player, 'getVehicleId'):
                            vid = player.getVehicleId()
                            if vid and vid in self._active_players:
                                p, info, _, prop_map = self._active_players[vid]
                                self._set_values(p, info, prop_map)
                    except Exception as e:
                        logger.debug('[PatchBattlePlayer] invalidate refresh failed: %s', e)

                TabView._invalidatePersonalInfo = patched_invalidate

            logger.debug('[PatchBattlePlayer] TabView patched')
            return True
        except Exception as e:
            logger.error('[PatchBattlePlayer] TabView patch failed: %s', e)
            import traceback
            logger.error('[PatchBattlePlayer] Traceback: %s', traceback.format_exc())
            return False

    def _register_tab_view_instance(self, tv_self):
        try:
            for ref in self._tab_view_instances:
                if ref() is tv_self:
                    return
            self._tab_view_instances.append(weakref.ref(tv_self))
        except Exception:
            pass

    def _set_values(self, player, vehicleInfo, prop_map=None):
        try:
            account_id = vehicleInfo.get('accountDBID') if vehicleInfo else None
            if not account_id:
                return

            stats = self._stats_manager.get_cached_stats(account_id)
            if not stats:
                return

            wn8 = int(stats.get('wn8', 0) or 0)
            winrate = float(stats.get('winrate', 0) or 0)
            battles = int(stats.get('battles', 0) or 0)

            wn8_color = get_wn8_color(wn8) if wn8 else '#FFFFFF'
            wr_color = get_winrate_color(winrate) if winrate else '#FFFFFF'
            b_color = get_battles_color(battles) if battles else '#FFFFFF'

            if hasattr(player, 'setWn8Color'):
                player.setWn8Color(wn8_color)
            if hasattr(player, 'setWinrateColor'):
                player.setWinrateColor(wr_color)
            if hasattr(player, 'setBattlesColor'):
                player.setBattlesColor(b_color)

            if hasattr(player, 'setWn8'):
                player.setWn8(str(wn8) if g_configParams.showWn8.value and wn8 else '')

            if hasattr(player, 'setWinrate'):
                player.setWinrate('%.1f%%' % winrate if g_configParams.showWinrate.value and winrate else '')

            if hasattr(player, 'setBattles'):
                player.setBattles(get_format_battles(battles) if g_configParams.showBattles.value and battles else '')

            # Логуємо індекси з prop_map для першого гравця
            if prop_map:
                logger.debug('[PatchBattlePlayer] prop_map=%s for account %s', prop_map, account_id)

        except Exception as e:
            logger.debug('[PatchBattlePlayer] setValues failed: %s', e)

    def apply_patches(self):
        if self._patches_applied:
            return True
        success = 0
        if self._monkey_patch_battle_player():
            success += 1
        if self._monkey_patch_tab_view():
            success += 1
        self._patches_applied = success == 2
        logger.debug('[PatchBattlePlayer] apply_patches: %s/2', success)
        return self._patches_applied

    def remove_patches(self):
        try:
            if self._stats_manager:
                try:
                    self._stats_manager.remove_update_callback(self._on_stats_updated)
                except Exception:
                    pass

            from gui.impl.gen.view_models.common.battle_player import BattlePlayer
            from gui.impl.battle.battle_page.tab_view import TabView

            if self._original_battle_player_constructor:
                BattlePlayer.__init__ = self._original_battle_player_constructor
            if self._original_battle_player_initialize:
                BattlePlayer._initialize = self._original_battle_player_initialize
                for m in ('getWinrate', 'setWinrate', 'getWinrateColor', 'setWinrateColor',
                          'getWn8', 'setWn8', 'getWn8Color', 'setWn8Color',
                          'getBattles', 'setBattles', 'getBattlesColor', 'setBattlesColor'):
                    if hasattr(BattlePlayer, m):
                        try:
                            delattr(BattlePlayer, m)
                        except AttributeError:
                            pass

            if self._original_fill_player_model:
                TabView._fillPlayerModel = self._original_fill_player_model
            if self._original_fill_player_list_model:
                TabView._fillPlayerListModel = self._original_fill_player_list_model
            if self._original_invalidate_personal_info:
                TabView._invalidatePersonalInfo = self._original_invalidate_personal_info

            self._active_players.clear()
            self._tab_view_instances = []
            self._patches_applied = False
            return True
        except Exception as e:
            logger.debug('[PatchBattlePlayer] remove failed: %s', e)
            return False

    def is_patched(self):
        return self._patches_applied
