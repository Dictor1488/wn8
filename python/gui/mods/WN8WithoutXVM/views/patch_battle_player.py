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
    """
    Замість патчу BattlePlayer ViewModel (не працює через fixed C++ schema),
    зберігаємо стату в window.__wn8[vehicleId] через engine.call,
    і читаємо її напряму в JS через data-bind-value expressions.
    """

    def __init__(self, stats_manager):
        self._original_fill_player_model = None
        self._original_fill_player_list_model = None
        self._patches_applied = False
        self._stats_manager = stats_manager
        # vehicleId -> accountDBID
        self._vehicle_account_map = {}
        # weakref до TabView інстансів
        self._tab_view_instances = []
        stats_manager.add_update_callback(self._on_stats_updated)

    def _push_to_js(self, vehicle_id, stats):
        """Записує стату в window.__wn8[vehicleId] через engine.call."""
        if not stats:
            return
        try:
            wn8 = int(stats.get('wn8', 0) or 0)
            winrate = float(stats.get('winrate', 0) or 0)
            battles = int(stats.get('battles', 0) or 0)

            w = str(wn8) if g_configParams.showWn8.value and wn8 else ''
            wc = get_wn8_color(wn8) if wn8 else '#FFFFFF'
            wr = ('%.1f%%' % winrate) if g_configParams.showWinrate.value and winrate else ''
            wrc = get_winrate_color(winrate) if winrate else '#FFFFFF'
            b = get_format_battles(battles) if g_configParams.showBattles.value and battles else ''
            bc = get_battles_color(battles) if battles else '#FFFFFF'

            # Формуємо JS код для виконання
            js = (
                'if(!window.__wn8)window.__wn8={};'
                'window.__wn8[%d]={w:%r,wc:%r,wr:%r,wrc:%r,b:%r,bc:%r};'
                'engine.synchronizeModels&&engine.synchronizeModels();'
            ) % (vehicle_id, w, wc, wr, wrc, b, bc)

            # Виконуємо JS через Coherent GT
            try:
                import GUI
                GUI.call('executeScript', js)
                logger.debug('[PatchBattlePlayer] pushed vehicleId=%s wn8=%s', vehicle_id, w)
            except Exception:
                # Спроба через інший API
                try:
                    import BigWorld
                    BigWorld.executeJS(js)
                except Exception as e2:
                    logger.debug('[PatchBattlePlayer] executeJS failed: %s', e2)

        except Exception as e:
            logger.debug('[PatchBattlePlayer] _push_to_js failed: %s', e)

    def _on_stats_updated(self, account_id):
        try:
            stats = self._stats_manager.get_cached_stats(account_id)
            if not stats:
                return
            for vid, acc_id in list(self._vehicle_account_map.items()):
                if acc_id == account_id:
                    self._push_to_js(vid, stats)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _on_stats_updated failed: %s', e)

    def _monkey_patch_battle_player(self):
        # Не патчимо BattlePlayer — використовуємо window.__wn8
        logger.debug('[PatchBattlePlayer] Skipping BattlePlayer patch (using window.__wn8 approach)')
        return True

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
                try:
                    if vehicleInfo:
                        account_id = vehicleInfo.get('accountDBID')
                        if account_id and vehicleId:
                            self._vehicle_account_map[vehicleId] = account_id
                            stats = self._stats_manager.get_cached_stats(account_id)
                            if stats:
                                self._push_to_js(vehicleId, stats)
                            else:
                                logger.debug('[PatchBattlePlayer] no stats yet for vehicleId=%s', vehicleId)
                except Exception as e:
                    logger.debug('[PatchBattlePlayer] fill error: %s', e)
                return player

            TabView._fillPlayerModel = patched_fill_player_model

            if hasattr(TabView, '_fillPlayerListModel'):
                self._original_fill_player_list_model = TabView._fillPlayerListModel

                @wraps(self._original_fill_player_list_model)
                def patched_fill_list(tv_self, *args, **kwargs):
                    return self._original_fill_player_list_model(tv_self, *args, **kwargs)

                TabView._fillPlayerListModel = patched_fill_list

            logger.debug('[PatchBattlePlayer] TabView patched (window.__wn8 approach)')
            return True
        except Exception as e:
            logger.error('[PatchBattlePlayer] TabView patch failed: %s', e)
            import traceback
            logger.error('[PatchBattlePlayer] Traceback: %s', traceback.format_exc())
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

            self._vehicle_account_map.clear()
            self._tab_view_instances = []
            self._patches_applied = False

            # Очищаємо window.__wn8
            try:
                import GUI
                GUI.call('executeScript', 'window.__wn8=undefined;')
            except Exception:
                pass

            return True
        except Exception as e:
            logger.debug('[PatchBattlePlayer] remove failed: %s', e)
            return False

    def is_patched(self):
        return self._patches_applied
