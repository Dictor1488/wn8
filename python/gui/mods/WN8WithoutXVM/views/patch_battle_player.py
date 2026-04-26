import weakref
from functools import wraps

from ..utils import (
    logger,
    get_format_battles
)
from ..settings.config_param import g_configParams

import logging
logger.setLevel(logging.DEBUG)


class PatchBattlePlayer(object):
    """
    Reliable TAB stats patch.

    Do not extend BattlePlayer schema with custom WULF fields. That approach is
    version-fragile and can silently write to wrong property slots. Instead we
    use the already rendered userName field, so TAB shows stats even when the
    custom Gameface bundle is not decoding extra fields yet.
    """

    def __init__(self, stats_manager):
        self._original_fill_player_model = None
        self._original_invalidate_personal_info = None
        self._patches_applied = False
        self._stats_manager = stats_manager
        # vehicleId -> (player, vehicleInfo, original_user_name, tab_view_ref)
        self._active_players = {}
        self._tab_view_instances = []
        stats_manager.add_update_callback(self._on_stats_updated)

    def _on_stats_updated(self, account_id):
        try:
            for vid, (player, info, original_user_name, tv_ref) in list(self._active_players.items()):
                if info.get('accountDBID') == account_id:
                    self._set_tab_name(player, info, original_user_name)
                    tv = tv_ref() if tv_ref else None
                    if tv is not None:
                        try:
                            tv.modifyBattlePlayer(player)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug('[PatchBattlePlayer] update failed: %s', e)

    def _strip_old_stats_prefix(self, user_name):
        try:
            name = user_name or u''
            if name.startswith(u'[') and u'] ' in name:
                return name.split(u'] ', 1)[1]
            return name
        except Exception:
            return user_name or u''

    def _build_stats_prefix(self, stats):
        parts = []
        try:
            if g_configParams.showWn8.value:
                wn8 = int(stats.get('wn8', 0) or 0)
                if wn8:
                    parts.append(str(wn8))
        except Exception:
            pass
        try:
            if g_configParams.showWinrate.value:
                winrate = float(stats.get('winrate', 0) or 0)
                if winrate:
                    parts.append('%.1f%%' % winrate)
        except Exception:
            pass
        try:
            if g_configParams.showBattles.value:
                battles = int(stats.get('battles', 0) or 0)
                if battles:
                    parts.append(get_format_battles(battles))
        except Exception:
            pass
        return u'|'.join([unicode(p) if not isinstance(p, unicode) else p for p in parts])

    def _set_tab_name(self, player, vehicleInfo, original_user_name):
        try:
            account_id = vehicleInfo.get('accountDBID') if vehicleInfo else None
            if not account_id:
                return

            stats = self._stats_manager.get_cached_stats(account_id)
            if not stats:
                return

            prefix = self._build_stats_prefix(stats)
            clean_name = self._strip_old_stats_prefix(original_user_name)
            if not clean_name:
                clean_name = u''

            display_name = u'[%s] %s' % (prefix, clean_name) if prefix else clean_name

            if hasattr(player, 'setUserName'):
                player.setUserName(display_name)
                logger.debug('[PatchBattlePlayer] TAB name set for %s: %s', account_id, display_name)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _set_tab_name failed: %s', e)

    def _monkey_patch_battle_player(self):
        logger.debug('[PatchBattlePlayer] Using visible userName TAB transport')
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
                if player is not None:
                    self._register_tab_view_instance(tv_self)
                    tv_ref = weakref.ref(tv_self)
                    original_user_name = u''
                    try:
                        if hasattr(player, 'getUserName'):
                            original_user_name = self._strip_old_stats_prefix(player.getUserName() or u'')
                    except Exception:
                        original_user_name = u''
                    self._active_players[vehicleId] = (player, vehicleInfo or {}, original_user_name, tv_ref)
                    self._set_tab_name(player, vehicleInfo or {}, original_user_name)
                return player

            TabView._fillPlayerModel = patched_fill_player_model

            if hasattr(TabView, '_invalidatePersonalInfo'):
                self._original_invalidate_personal_info = TabView._invalidatePersonalInfo

                @wraps(self._original_invalidate_personal_info)
                def patched_invalidate(tv_self, player):
                    self._original_invalidate_personal_info(tv_self, player)
                    try:
                        if hasattr(player, 'getVehicleId'):
                            vid = player.getVehicleId()
                            if vid and vid in self._active_players:
                                p, info, original_user_name, _ = self._active_players[vid]
                                self._set_tab_name(p, info, original_user_name)
                    except Exception as e:
                        logger.debug('[PatchBattlePlayer] invalidate: %s', e)

                TabView._invalidatePersonalInfo = patched_invalidate

            logger.debug('[PatchBattlePlayer] TabView patched with visible userName stats')
            return True
        except Exception as e:
            logger.error('[PatchBattlePlayer] TabView patch failed: %s', e)
            import traceback
            logger.error('[PatchBattlePlayer] %s', traceback.format_exc())
            return False

    def _register_tab_view_instance(self, tv_self):
        try:
            for ref in self._tab_view_instances:
                if ref() is tv_self:
                    return
            self._tab_view_instances.append(weakref.ref(tv_self))
        except Exception:
            pass

    def apply_patches(self):
        if self._patches_applied:
            return True
        success = 0
        if self._monkey_patch_battle_player():
            success += 1
        if self._monkey_patch_tab_view():
            success += 1
        self._patches_applied = success == 2
        logger.debug('[PatchBattlePlayer] apply: %s/2', success)
        return self._patches_applied

    def remove_patches(self):
        try:
            if self._stats_manager:
                try:
                    self._stats_manager.remove_update_callback(self._on_stats_updated)
                except Exception:
                    pass
            if not self._patches_applied:
                self._active_players.clear()
                self._tab_view_instances = []
                return True

            from gui.impl.battle.battle_page.tab_view import TabView

            if self._original_fill_player_model:
                TabView._fillPlayerModel = self._original_fill_player_model
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
