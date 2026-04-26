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


class PatchBattlePlayer(object):

    def __init__(self, stats_manager):
        self._original_fill_player_model = None
        self._original_fill_player_list_model = None
        self._original_invalidate_personal_info = None
        self._patches_applied = False
        self._stats_manager = stats_manager
        self._active_players = {}
        self._tab_view_instances = []
        stats_manager.add_update_callback(self._on_stats_updated)

    def _on_stats_updated(self, account_id):
        try:
            for vehicle_id, (player, vehicle_info, tv_ref) in list(self._active_players.items()):
                if vehicle_info.get('accountDBID') == account_id:
                    self._set_values(player, vehicle_info)
                    tv = tv_ref() if tv_ref else None
                    if tv is not None:
                        self._refresh_player(tv, player)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _on_stats_updated failed: %s', e)

    def _refresh_player(self, tv, player):
        try:
            if hasattr(tv, 'modifyBattlePlayer'):
                tv.modifyBattlePlayer(player)
                logger.debug('[PatchBattlePlayer] modifyBattlePlayer called')
            elif self._original_invalidate_personal_info:
                self._original_invalidate_personal_info(tv, player)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _refresh_player failed: %s', e)

    def _monkey_patch_battle_player(self):
        """
        НЕ патчимо BattlePlayer.__init__ і _initialize.
        Перевіряємо чи WG вже додали wn8/winrate/battles поля напряму.
        """
        try:
            from gui.impl.gen.view_models.common.battle_player import BattlePlayer
            # Діагностика: виводимо всі getter методи оригінального класу
            getters = [m for m in dir(BattlePlayer) if m.startswith('get') and callable(getattr(BattlePlayer, m))]
            logger.debug('[PatchBattlePlayer] BattlePlayer getters: %s', getters)

            # Перевіряємо чи вже є наші поля
            has_wn8 = hasattr(BattlePlayer, 'getWn8') or hasattr(BattlePlayer, 'getWN8')
            has_winrate = hasattr(BattlePlayer, 'getWinrate') or hasattr(BattlePlayer, 'getWinRate')
            has_battles = hasattr(BattlePlayer, 'getBattles')
            logger.debug('[PatchBattlePlayer] has_wn8=%s has_winrate=%s has_battles=%s',
                         has_wn8, has_winrate, has_battles)

            return True
        except Exception as e:
            logger.error('[PatchBattlePlayer] BattlePlayer check failed: %s', e)
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
                    self._active_players[vehicleId] = (player, vehicleInfo or {}, tv_ref)
                    # Діагностика: виводимо всі атрибути player
                    if vehicleInfo and vehicleInfo.get('accountDBID') == list(self._active_players.values())[0][1].get('accountDBID') if self._active_players else False:
                        pass
                    self._set_values(player, vehicleInfo or {})
                    # ДІАГНОСТИКА: виводимо всі getter методи першого гравця
                    if len(self._active_players) == 1:
                        getters = [m for m in dir(player) if m.startswith('get') and callable(getattr(player, m, None))]
                        logger.debug('[PatchBattlePlayer] BattlePlayer instance getters: %s', getters)
                return player

            TabView._fillPlayerModel = patched_fill_player_model

            if hasattr(TabView, '_fillPlayerListModel'):
                self._original_fill_player_list_model = TabView._fillPlayerListModel

                @wraps(self._original_fill_player_list_model)
                def patched_fill_player_list_model(tv_self, *args, **kwargs):
                    result = self._original_fill_player_list_model(tv_self, *args, **kwargs)
                    self._register_tab_view_instance(tv_self)
                    return result

                TabView._fillPlayerListModel = patched_fill_player_list_model

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

            # Спробуємо всі можливі варіанти назв методів
            for setter, value in (
                ('setWn8', str(wn8) if g_configParams.showWn8.value and wn8 else ''),
                ('setWn8Color', wn8_color),
                ('setWN8', str(wn8) if g_configParams.showWn8.value and wn8 else ''),
                ('setWinrate', ('%.1f%%' % winrate) if g_configParams.showWinrate.value and winrate else ''),
                ('setWinrateColor', wr_color),
                ('setWinRate', ('%.1f%%' % winrate) if g_configParams.showWinrate.value and winrate else ''),
                ('setBattles', get_format_battles(battles) if g_configParams.showBattles.value and battles else ''),
                ('setBattlesColor', b_color),
            ):
                if hasattr(player, setter):
                    try:
                        getattr(player, setter)(value)
                    except Exception as e:
                        logger.debug('[PatchBattlePlayer] %s failed: %s', setter, e)

            logger.debug('[PatchBattlePlayer] Set wn8=%s for account %s', wn8, account_id)

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

            from gui.impl.battle.battle_page.tab_view import TabView
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
