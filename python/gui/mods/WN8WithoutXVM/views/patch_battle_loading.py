from helpers import dependency
from PlayerEvents import g_playerEvents
from gui.battle_control.arena_info.interfaces import IArenaVehiclesController
from skeletons.gui.battle_session import IBattleSessionProvider

from ..utils import logger
from ..settings.config_param import g_configParams


class _WN8PrefetchController(IArenaVehiclesController):
    __slots__ = ('_stats_manager', '_fetched')

    def __init__(self, stats_manager):
        super(_WN8PrefetchController, self).__init__()
        self._stats_manager = stats_manager
        self._fetched = set()

    def getControllerID(self):
        return 0

    def startControl(self, battleCtx, arenaVisitor):
        self._fetched.clear()

    def stopControl(self):
        self._fetched.clear()

    def invalidateArenaInfo(self):
        pass

    def invalidateVehiclesInfo(self, arenaDP):
        try:
            for vo in arenaDP.getVehiclesInfoIterator():
                self._request(vo)
        except Exception:
            logger.exception('[WN8Prefetch] invalidateVehiclesInfo failed')

    def addVehicleInfo(self, vo, arenaDP):
        self._request(vo)

    def updateVehiclesInfo(self, updated, arenaDP):
        try:
            for _flags, vo in updated:
                self._request(vo)
        except Exception:
            logger.exception('[WN8Prefetch] updateVehiclesInfo failed')

    def _request(self, vo):
        try:
            account_id = getattr(getattr(vo, 'player', None), 'accountDBID', 0) or 0
            if not account_id or account_id in self._fetched:
                return
            self._fetched.add(account_id)
            logger.debug('[WN8Prefetch] prefetch stats for %s', account_id)
            self._stats_manager.get_player_stats(account_id)
        except Exception:
            logger.exception('[WN8Prefetch] request failed')


class PatchBattleLoading(object):

    sessionProvider = dependency.descriptor(IBattleSessionProvider)

    def __init__(self, stats_manager):
        self._stats_manager = stats_manager
        self._controller = _WN8PrefetchController(stats_manager)
        self._subscribed = False
        self._registered = False

    def apply_patches(self):
        if self._subscribed:
            return True
        g_playerEvents.onAvatarReady += self._register
        g_playerEvents.onAvatarBecomeNonPlayer += self._unregister
        self._subscribed = True
        logger.debug('[PatchBattleLoading] Subscribed to PlayerEvents')
        return True

    def remove_patches(self):
        self._unregister()
        if self._subscribed:
            try:
                g_playerEvents.onAvatarReady -= self._register
                g_playerEvents.onAvatarBecomeNonPlayer -= self._unregister
            except Exception:
                logger.exception('[PatchBattleLoading] unsubscribe failed')
            self._subscribed = False
        return True

    def _register(self):
        if self._registered:
            return
        try:
            if self.sessionProvider is None:
                logger.debug('[PatchBattleLoading] No sessionProvider yet')
                return
            if self.sessionProvider.addArenaCtrl(self._controller):
                self._registered = True
                logger.debug('[PatchBattleLoading] Prefetch controller registered')
            else:
                logger.debug('[PatchBattleLoading] addArenaCtrl returned False')
        except Exception:
            logger.exception('[PatchBattleLoading] register failed')

    def _unregister(self):
        if not self._registered:
            return
        try:
            if self.sessionProvider is not None:
                self.sessionProvider.removeArenaCtrl(self._controller)
                logger.debug('[PatchBattleLoading] Prefetch controller removed')
        except Exception:
            logger.exception('[PatchBattleLoading] unregister failed')
        finally:
            self._registered = False
