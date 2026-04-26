import weakref

import BigWorld
from PlayerEvents import g_playerEvents

from .battle_modes import is_supported
from .settings.config_param import g_configParams
from .utils import logger, override, restore_overrides


class BattleProvider(object):


    MAX_RETRIES = 10
    _instance = None
    _hooked = False

    def __init__(self, statsManager, panelView):
        logger.debug('[BattleProvider] Initializing...')

        self._arena = None
        self._playerTeam = None
        self._statsManager = statsManager
        self._panelView = panelView
        self._battleSessionId = 0
        self._retryCount = 0
        self._isBattleActive = False
        self._loadedAccounts = set()
        self._fallbackSubscribed = False

        BattleProvider._instance = self
        self._installOverrides()

        logger.debug('[BattleProvider] Initialized')

    def _installOverrides(self):

        if BattleProvider._hooked:
            return
        try:
            from Avatar import PlayerAvatar

            @override(PlayerAvatar, 'onBecomePlayer')
            def hooked_onBecomePlayer(base, avatar, *args, **kwargs):
                base(avatar, *args, **kwargs)
                inst = BattleProvider._instance
                if inst is not None:
                    inst._onAvatarReady()

            @override(PlayerAvatar, 'onBecomeNonPlayer')
            def hooked_onBecomeNonPlayer(base, avatar, *args, **kwargs):
                inst = BattleProvider._instance
                if inst is not None:
                    inst._onAvatarBecomeNonPlayer()
                base(avatar, *args, **kwargs)

            BattleProvider._hooked = True
            logger.debug('[BattleProvider] Hooked PlayerAvatar directly')
        except Exception:
            logger.exception('[BattleProvider] Avatar hook failed, falling back to g_playerEvents')
            g_playerEvents.onAvatarReady += self._onAvatarReady
            g_playerEvents.onAvatarBecomeNonPlayer += self._onAvatarBecomeNonPlayer
            self._fallbackSubscribed = True

    def fini(self):
        logger.debug('[BattleProvider] Finalizing...')
        self._battleSessionId += 1
        self._isBattleActive = False
        self._arena = None
        self._playerTeam = None
        self._loadedAccounts.clear()
        BattleProvider._instance = None

        if self._fallbackSubscribed:
            try:
                g_playerEvents.onAvatarReady -= self._onAvatarReady
                g_playerEvents.onAvatarBecomeNonPlayer -= self._onAvatarBecomeNonPlayer
            except Exception:
                logger.exception('[BattleProvider] Error unsubscribing g_playerEvents')
            self._fallbackSubscribed = False

        restore_overrides()
        BattleProvider._hooked = False

    def getArena(self):
        return self._arena

    def _onAvatarReady(self):
        logger.debug('[BattleProvider] Avatar ready')
        try:
            if not g_configParams.enabled.value:
                logger.debug('[BattleProvider] Mod disabled - skipping')
                return
        except Exception:
            logger.exception('[BattleProvider] Failed to check config')
            return

        self._battleSessionId += 1
        self._retryCount = 0
        self._loadedAccounts.clear()
        self._tryInitializeBattle(self._battleSessionId)

    def _tryInitializeBattle(self, sessionId):
        if sessionId != self._battleSessionId:
            return

        try:
            player = BigWorld.player()
            if player is None:
                self._scheduleRetry(sessionId, 'player is None')
                return

            arena = getattr(player, 'arena', None)
            if arena is None:
                self._scheduleRetry(sessionId, 'arena is None')
                return

            if not hasattr(player, 'team') or not hasattr(player, 'playerVehicleID'):
                self._scheduleRetry(sessionId, 'player attrs not ready')
                return

            self._onBattleReady(player, arena)

        except Exception:
            logger.exception('[BattleProvider] Error in _tryInitializeBattle')

    def _scheduleRetry(self, sessionId, reason):
        if self._retryCount >= self.MAX_RETRIES:
            logger.error('[BattleProvider] Giving up after %s retries (%s)',
                         self.MAX_RETRIES, reason)
            return
        self._retryCount += 1
        logger.debug('[BattleProvider] Retry %s/%s: %s',
                     self._retryCount, self.MAX_RETRIES, reason)

        ref = weakref.ref(self)

        def _retry():
            inst = ref()
            if inst is None:
                return
            if inst._battleSessionId != sessionId:
                return
            inst._tryInitializeBattle(sessionId)

        BigWorld.callback(0.5, _retry)

    def _onBattleReady(self, player, arena):
        if not is_supported(arena):
            logger.debug('[BattleProvider] Battle mode not supported (guiType=%s bonusType=%s) - skipping',
                         getattr(arena, 'guiType', None), getattr(arena, 'bonusType', None))
            return

        self._arena = arena
        self._playerTeam = player.team
        self._isBattleActive = True

        logger.debug('[BattleProvider] Player team: %s', self._playerTeam)
        logger.debug('[BattleProvider] Arena acquired: %s vehicles',
                     len(arena.vehicles) if arena.vehicles else 0)

        if self._panelView is not None:
            self._panelView.setArena(arena)
            self._panelView.initialize()

        sessionId = self._battleSessionId
        ref = weakref.ref(self)

        def _startLoading():
            inst = ref()
            if inst is None:
                return
            if inst._battleSessionId != sessionId:
                return
            inst._loadAllPlayersStats()

        BigWorld.callback(0.5, _startLoading)

    def _loadAllPlayersStats(self):
        if not self._isBattleActive:
            return
        if not self._arena or not self._arena.vehicles:
            logger.debug('[BattleProvider] No arena or vehicles')
            return

        accountIds = []
        for vehicleData in self._arena.vehicles.values():
            accountId = vehicleData.get('accountDBID')
            if accountId and accountId not in self._loadedAccounts:
                accountIds.append(accountId)

        logger.debug('[BattleProvider] Loading stats for %s players', len(accountIds))

        for accountId in accountIds:
            self._loadedAccounts.add(accountId)
            self._statsManager.get_player_stats(accountId, self._onPlayerStatsLoaded)

    def _onPlayerStatsLoaded(self, accountId, stats):
        if not self._isBattleActive:
            return

        logger.debug('[BattleProvider] Stats loaded for account %s: %s', accountId, stats)

        try:
            if self._panelView is not None and stats:
                self._panelView._updatePlayerDisplay(accountId, stats)
        except Exception:
            logger.exception('[BattleProvider] Error updating for account %s', accountId)

    def _onAvatarBecomeNonPlayer(self):
        logger.debug('[BattleProvider] Avatar become non-player')

        self._battleSessionId += 1
        self._isBattleActive = False
        self._arena = None
        self._playerTeam = None
        self._loadedAccounts.clear()

        try:
            if self._panelView is not None:
                self._panelView.setArena(None)
                self._panelView.finalize()

            if self._statsManager is not None:
                self._statsManager.clear_cache()
        except Exception:
            logger.exception('[BattleProvider] Failed to stop battle session')
        finally:
            self._arena = None
            self._playerTeam = None
            self._retryCount = 0
            self._loadedAccounts.clear()

    def getPlayerStats(self, accountId):
        if self._statsManager is not None:
            return self._statsManager.get_cached_stats(accountId)
        return None

    def isStatsLoaded(self, accountId):
        if self._statsManager is not None:
            return self._statsManager.is_stats_loaded(accountId)
        return False
