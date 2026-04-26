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

# TAB/Gameface renders existing BattlePlayer fields reliably.
# Adding custom WULF properties is fragile between WoT versions, so we pass
# WN8 data through userName and decode it in TabView.js / DOM patch.
ENCODE_SEPARATOR = u'\t'


class PatchBattlePlayer(object):

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
                    self._set_encoded_name(player, info, original_user_name)
                    tv = tv_ref() if tv_ref else None
                    if tv is not None:
                        try:
                            tv.modifyBattlePlayer(player)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug('[PatchBattlePlayer] update failed: %s', e)

    def _decode_original_name(self, user_name):
        try:
            if user_name and ENCODE_SEPARATOR in user_name:
                return user_name.split(ENCODE_SEPARATOR, 1)[0]
        except Exception:
            pass
        return user_name or u''

    def _set_encoded_name(self, player, vehicleInfo, original_user_name):
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

            wn8_text = str(wn8) if g_configParams.showWn8.value and wn8 else ''
            wn8_color = get_wn8_color(wn8) if wn8 else '#FFFFFF'
            winrate_text = ('%.1f' % winrate) if g_configParams.showWinrate.value and winrate else ''
            winrate_color = get_winrate_color(winrate) if winrate else '#FFFFFF'
            battles_text = get_format_battles(battles) if g_configParams.showBattles.value and battles else ''
            battles_color = get_battles_color(battles) if battles else '#FFFFFF'

            encoded = ENCODE_SEPARATOR.join((
                original_user_name or u'',
                wn8_text,
                wn8_color,
                winrate_text,
                winrate_color,
                battles_text,
                battles_color,
            ))

            if hasattr(player, 'setUserName'):
                player.setUserName(encoded)
                logger.debug('[PatchBattlePlayer] encoded TAB stats set wn8=%s wr=%s battles=%s for %s',
                             wn8_text, winrate_text, battles_text, account_id)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _set_encoded_name failed: %s', e)

    def _monkey_patch_battle_player(self):
        # No BattlePlayer schema extension here. Existing userName is safer and
        # survives client-side model changes better than _addStringProperty slots.
        logger.debug('[PatchBattlePlayer] Using encoded userName transport')
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
                            original_user_name = self._decode_original_name(player.getUserName() or u'')
                    except Exception:
                        original_user_name = u''
                    self._active_players[vehicleId] = (player, vehicleInfo or {}, original_user_name, tv_ref)
                    self._set_encoded_name(player, vehicleInfo or {}, original_user_name)
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
                                self._set_encoded_name(p, info, original_user_name)
                    except Exception as e:
                        logger.debug('[PatchBattlePlayer] invalidate: %s', e)

                TabView._invalidatePersonalInfo = patched_invalidate

            logger.debug('[PatchBattlePlayer] TabView patched with encoded userName')
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
