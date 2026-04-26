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
    """
    Оскільки додавання нових полів в BattlePlayer C++ schema неможливе,
    використовуємо вже існуючі поля. Зберігаємо WN8 у vehicleName у
    форматі: "WN8|КОЛІР|WINRATE|КОЛІР|BATTLES|КОЛІР|СПРАВЖНЄ_ІМ'Я".
    TabView.js вже рендерить vehicleName в колонці танка.
    
    Але це некрасиво — зламає ім'я танка.
    
    ПРАВИЛЬНЕ рішення: patching _fillPlayerModel + зберігання даних у
    liveTagTooltipTitle яке вже є в schema і може містити HTML.
    TabView.js рендерить його тільки при наведенні мишки — тобто воно
    безпечне для перевикористання.
    
    Але НАЙКРАЩЕ: перевикористати userName — він вже є і рендериться.
    Зберігаємо: "ОРИГІНАЛЬНЕ_ІМ'Я\nWN8_VALUE\nWN8_COLOR\nWINRATE\nWINRATE_COLOR\nBATTLES\nBATTLES_COLOR"
    І в TabView.js читаємо userName.split('\n') для отримання компонентів.
    """

    def __init__(self, stats_manager):
        self._original_fill_player_model = None
        self._original_invalidate_personal_info = None
        self._patches_applied = False
        self._stats_manager = stats_manager
        # vehicleId -> (player, vehicleInfo, original_userName, tv_ref)
        self._active_players = {}
        self._tab_view_instances = []
        stats_manager.add_update_callback(self._on_stats_updated)

    def _on_stats_updated(self, account_id):
        try:
            for vid, (player, info, orig_name, tv_ref) in list(self._active_players.items()):
                if info.get('accountDBID') == account_id:
                    self._set_encoded_name(player, info, orig_name)
                    tv = tv_ref() if tv_ref else None
                    if tv is not None:
                        try:
                            tv.modifyBattlePlayer(player)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug('[PatchBattlePlayer] update failed: %s', e)

    def _set_encoded_name(self, player, vehicleInfo, orig_name):
        """
        Кодує WN8 дані в userName через \n роздільник.
        TabView.js треба патчити щоб розкодовувати.
        """
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

            w = str(wn8) if g_configParams.showWn8.value and wn8 else ''
            wc = get_wn8_color(wn8) if wn8 else ''
            wr = ('%.1f' % winrate) if g_configParams.showWinrate.value and winrate else ''
            wrc = get_winrate_color(winrate) if winrate else ''
            b = get_format_battles(battles) if g_configParams.showBattles.value and battles else ''
            bc = get_battles_color(battles) if battles else ''

            # Кодуємо: NAME\tW\tWC\tWR\tWRC\tB\tBC
            encoded = u'%s\t%s\t%s\t%s\t%s\t%s\t%s' % (
                orig_name or u'', w, wc, wr, wrc, b, bc
            )

            if hasattr(player, 'setUserName'):
                player.setUserName(encoded)
                logger.debug('[PatchBattlePlayer] encoded name set wn8=%s for %s', wn8, account_id)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] _set_encoded_name failed: %s', e)

    def _monkey_patch_battle_player(self):
        # Не патчимо BattlePlayer — використовуємо існуючі поля
        logger.debug('[PatchBattlePlayer] Using userName encoding approach')
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
                    # Зберігаємо оригінальне ім'я
                    orig_name = u''
                    try:
                        if hasattr(player, 'getUserName'):
                            orig_name = player.getUserName() or u''
                    except Exception:
                        pass
                    self._active_players[vehicleId] = (player, vehicleInfo or {}, orig_name, tv_ref)
                    self._set_encoded_name(player, vehicleInfo or {}, orig_name)
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
                                _, info, orig_name, _ = self._active_players[vid]
                                self._set_encoded_name(player, info, orig_name)
                    except Exception as e:
                        logger.debug('[PatchBattlePlayer] invalidate: %s', e)

                TabView._invalidatePersonalInfo = patched_invalidate

            logger.debug('[PatchBattlePlayer] TabView patched (userName encoding)')
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
