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
        # vehicleId -> (player, vehicleInfo, weakref до TabView)
        self._active_players = {}
        self._tab_view_instances = []
        self._original_property_count = None
        self._base_index = None
        stats_manager.add_update_callback(self._on_stats_updated)

    # ------------------------------------------------------------------
    # Property count discovery
    # ------------------------------------------------------------------

    def _discover_property_count(self, original_init):
        try:
            argspec = inspect.getargspec(original_init)
            logger.debug('[PatchBattlePlayer] BattlePlayer.__init__ args=%s defaults=%s',
                         argspec.args, argspec.defaults)
            if argspec.defaults and 'properties' in argspec.args:
                idx = argspec.args.index('properties') - 1
                if 0 <= idx < len(argspec.defaults):
                    self._original_property_count = argspec.defaults[idx]
                    logger.debug('[PatchBattlePlayer] property count from defaults: %s',
                                 self._original_property_count)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] inspect failed: %s', e)

        if self._original_property_count is None:
            self._original_property_count = 37
            logger.warning('[PatchBattlePlayer] Using fallback property count: 37')

        self._base_index = self._original_property_count
        logger.debug('[PatchBattlePlayer] Final base_index=%s', self._base_index)

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

    # ------------------------------------------------------------------
    # Stats update — викликається коли WG API повернув стату
    # ------------------------------------------------------------------

    def _on_stats_updated(self, account_id):
        try:
            updated = []
            for vehicle_id, (player, vehicle_info, tv_ref) in list(self._active_players.items()):
                if vehicle_info.get('accountDBID') == account_id:
                    self._set_values(player, vehicle_info)
                    tv = tv_ref() if tv_ref else None
                    updated.append((player, tv))

            # Примусовий рефреш через modifyBattlePlayer або _invalidatePersonalInfo
            for player, tv in updated:
                if tv is not None:
                    self._refresh_player(tv, player)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _on_stats_updated failed: %s', e)

    def _refresh_player(self, tv, player):
        """Тригерить оновлення DOM для конкретного гравця."""
        try:
            # Спосіб 1: modifyBattlePlayer — публічний API для модів
            if hasattr(tv, 'modifyBattlePlayer'):
                tv.modifyBattlePlayer(player)
                return
            # Спосіб 2: _invalidatePersonalInfo
            if self._original_invalidate_personal_info:
                self._original_invalidate_personal_info(tv, player)
            elif hasattr(tv, '_invalidatePersonalInfo'):
                tv._invalidatePersonalInfo(player)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _refresh_player failed: %s', e)

    # ------------------------------------------------------------------
    # BattlePlayer patch
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # TabView patch — патчимо обидва методи заповнення
    # ------------------------------------------------------------------

    def _monkey_patch_tab_view(self):
        try:
            from gui.impl.battle.battle_page.tab_view import TabView
        except Exception as e:
            logger.error('[PatchBattlePlayer] TabView import failed: %s', e)
            return False

        try:
            # Патчимо _fillPlayerModel
            self._original_fill_player_model = TabView._fillPlayerModel

            @wraps(self._original_fill_player_model)
            def patched_fill_player_model(tv_self, vehicleId, vehicleInfo):
                player = self._original_fill_player_model(tv_self, vehicleId, vehicleInfo)
                if player is not None:
                    self._register_tab_view_instance(tv_self)
                    tv_ref = weakref.ref(tv_self)
                    self._active_players[vehicleId] = (player, vehicleInfo or {}, tv_ref)
                    self._set_values(player, vehicleInfo or {})
                    logger.debug('[PatchBattlePlayer] _fillPlayerModel vehicleId=%s', vehicleId)
                return player

            TabView._fillPlayerModel = patched_fill_player_model

            # Патчимо _fillPlayerListModel якщо є
            if hasattr(TabView, '_fillPlayerListModel'):
                self._original_fill_player_list_model = TabView._fillPlayerListModel

                @wraps(self._original_fill_player_list_model)
                def patched_fill_player_list_model(tv_self, *args, **kwargs):
                    result = self._original_fill_player_list_model(tv_self, *args, **kwargs)
                    self._register_tab_view_instance(tv_self)
                    logger.debug('[PatchBattlePlayer] _fillPlayerListModel called')
                    return result

                TabView._fillPlayerListModel = patched_fill_player_list_model

            # Патчимо _invalidatePersonalInfo
            if hasattr(TabView, '_invalidatePersonalInfo'):
                self._original_invalidate_personal_info = TabView._invalidatePersonalInfo

                @wraps(self._original_invalidate_personal_info)
                def patched_invalidate(tv_self, player):
                    self._original_invalidate_personal_info(tv_self, player)
                    try:
                        if hasattr(player, 'getVehicleId'):
                            vid = player.getVehicleId()
                            if vid and vid in self._active_players:
                                p, info, _ = self._active_players[vid]
                                self._set_values(p, info)
                    except Exception as e:
                        logger.debug('[PatchBattlePlayer] invalidate refresh failed: %s', e)

                TabView._invalidatePersonalInfo = patched_invalidate

            logger.debug('[PatchBattlePlayer] TabView patched successfully')
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
            logger.debug('[PatchBattlePlayer] TabView instance registered')
        except Exception as e:
            logger.debug('[PatchBattlePlayer] register instance failed: %s', e)

    # ------------------------------------------------------------------
    # Set stat values on BattlePlayer model
    # ------------------------------------------------------------------

    def _set_values(self, player, vehicleInfo):
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
                if g_configParams.showWn8.value and wn8:
                    player.setWn8(str(wn8))
                    logger.debug('[PatchBattlePlayer] Set wn8=%s for account %s', wn8, account_id)
                else:
                    player.setWn8('')

            if hasattr(player, 'setWinrate'):
                if g_configParams.showWinrate.value and winrate:
                    player.setWinrate('%.1f%%' % winrate)
                else:
                    player.setWinrate('')

            if hasattr(player, 'setBattles'):
                if g_configParams.showBattles.value and battles:
                    player.setBattles(get_format_battles(battles))
                else:
                    player.setBattles('')

        except Exception as e:
            logger.debug('[PatchBattlePlayer] setValues failed: %s', e)

    # ------------------------------------------------------------------
    # Apply / remove
    # ------------------------------------------------------------------

    def apply_patches(self):
        if self._patches_applied:
            return True
        success = 0
        if self._monkey_patch_battle_player():
            success += 1
        if self._monkey_patch_tab_view():
            success += 1
        self._patches_applied = success == 2
        logger.debug('[PatchBattlePlayer] apply_patches result: %s/2', success)
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
                self._tab_view_instances = []
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
