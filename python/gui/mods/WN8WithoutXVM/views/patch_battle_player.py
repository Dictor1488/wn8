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

# Примусово вмикаємо DEBUG лог незалежно від .debug_mods
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
        self._original_invalidate_personal_info = None
        self._patches_applied = False
        self._stats_manager = stats_manager
        self._active_players = {}
        self._tab_view_instances = []
        self._original_property_count = None
        self._base_index = None
        stats_manager.add_update_callback(self._on_stats_updated)

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
            try:
                from gui.impl.gen.view_models.common.battle_player import BattlePlayer
                tmp = object.__new__(BattlePlayer)
                original_init(tmp)
                for attr in ('_propertiesCount', '_propertyCount', '_properties_count'):
                    if hasattr(tmp, attr):
                        self._original_property_count = getattr(tmp, attr)
                        logger.debug('[PatchBattlePlayer] property count from %s: %s',
                                     attr, self._original_property_count)
                        break
            except Exception as e:
                logger.debug('[PatchBattlePlayer] tmp instance discovery failed: %s', e)

        if self._original_property_count is None:
            try:
                from gui.impl.gen.view_models.common.battle_player import BattlePlayer
                count = sum(
                    1 for name in dir(BattlePlayer)
                    if name.startswith('get') and callable(getattr(BattlePlayer, name, None))
                    and hasattr(BattlePlayer, 'set' + name[3:])
                )
                if count > 0:
                    self._original_property_count = count
                    logger.debug('[PatchBattlePlayer] property count from getter scan: %s', count)
            except Exception as e:
                logger.debug('[PatchBattlePlayer] getter scan failed: %s', e)

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

    def _on_stats_updated(self, account_id):
        try:
            updated_players = []
            for vehicle_id, (player, vehicle_info) in list(self._active_players.items()):
                if vehicle_info.get('accountDBID') == account_id:
                    self._set_values(player, vehicle_info)
                    updated_players.append(player)
            if updated_players:
                self._force_refresh_tab_view(updated_players)
        except Exception as e:
            logger.debug('[PatchBattlePlayer] update failed: %s', e)

    def _force_refresh_tab_view(self, players):
        dead = []
        for ref in self._tab_view_instances:
            tv = ref()
            if tv is None:
                dead.append(ref)
                continue
            for player in players:
                try:
                    if self._original_invalidate_personal_info:
                        self._original_invalidate_personal_info(tv, player)
                    elif hasattr(tv, '_invalidatePersonalInfo'):
                        tv._invalidatePersonalInfo(player)
                except Exception as e:
                    logger.debug('[PatchBattlePlayer] force refresh failed: %s', e)
        for ref in dead:
            try:
                self._tab_view_instances.remove(ref)
            except ValueError:
                pass

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
            # Діагностика — виводимо всі методи TabView
            tab_methods = [m for m in dir(TabView) if not m.startswith('__')]
            logger.debug('[PatchBattlePlayer] TabView methods: %s', tab_methods)

            # Шукаємо правильний метод для заповнення моделі гравця
            fill_method_name = None
            for candidate in ('_fillPlayerModel', 'fillPlayerModel', '_fillPlayer',
                              '_updatePlayer', '_addPlayer', '_buildPlayerModel'):
                if hasattr(TabView, candidate):
                    fill_method_name = candidate
                    logger.debug('[PatchBattlePlayer] Found fill method: %s', candidate)
                    break

            if fill_method_name is None:
                logger.error('[PatchBattlePlayer] No fill player method found in TabView!')
                return False

            self._original_fill_player_model = getattr(TabView, fill_method_name)

            def patched_fill(tv_self, *args, **kwargs):
                result = self._original_fill_player_model(tv_self, *args, **kwargs)
                try:
                    self._register_tab_view_instance(tv_self)
                    # args[0] — vehicleId, args[1] — vehicleInfo (якщо є)
                    vehicleId = args[0] if args else kwargs.get('vehicleId')
                    vehicleInfo = args[1] if len(args) > 1 else kwargs.get('vehicleInfo')
                    player = result
                    if player and vehicleId is not None:
                        if vehicleInfo is None:
                            # Спробуємо знайти vehicleInfo через інший шлях
                            logger.debug('[PatchBattlePlayer] vehicleInfo is None for %s', vehicleId)
                        self._active_players[vehicleId] = (player, vehicleInfo or {})
                        self._set_values(player, vehicleInfo or {})
                        logger.debug('[PatchBattlePlayer] Filled player model for vehicleId=%s', vehicleId)
                except Exception as e:
                    logger.debug('[PatchBattlePlayer] patched_fill error: %s', e)
                return result

            setattr(TabView, fill_method_name, patched_fill)

            # Патч invalidate
            invalidate_name = None
            for candidate in ('_invalidatePersonalInfo', 'invalidatePersonalInfo',
                              '_invalidatePlayer', '_refreshPlayer'):
                if hasattr(TabView, candidate):
                    invalidate_name = candidate
                    logger.debug('[PatchBattlePlayer] Found invalidate method: %s', candidate)
                    break

            if invalidate_name:
                self._original_invalidate_personal_info = getattr(TabView, invalidate_name)

                def patched_invalidate(tv_self, player):
                    self._original_invalidate_personal_info(tv_self, player)
                    try:
                        if hasattr(player, 'getVehicleId'):
                            vehicleId = player.getVehicleId()
                            if vehicleId and vehicleId in self._active_players:
                                _, info = self._active_players[vehicleId]
                                self._set_values(player, info)
                    except Exception as e:
                        logger.debug('[PatchBattlePlayer] invalidate refresh failed: %s', e)

                setattr(TabView, invalidate_name, patched_invalidate)

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

    def _set_values(self, player, vehicleInfo):
        try:
            account_id = vehicleInfo.get('accountDBID') if vehicleInfo else None
            if not account_id:
                logger.debug('[PatchBattlePlayer] _set_values: no accountDBID in vehicleInfo')
                return

            stats = self._stats_manager.get_cached_stats(account_id)
            if not stats:
                logger.debug('[PatchBattlePlayer] _set_values: no cached stats for %s', account_id)
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
