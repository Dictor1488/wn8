import BigWorld
from helpers import dependency
from helpers.CallbackDelayer import CallbackDelayer
from skeletons.gui.battle_session import IBattleSessionProvider

from gui.battle_control.arena_info import vos_collections

from ..utils import logger
from ..settings.config_param import g_configParams, WinratePosition

try:
    from .player_panel import g_events, TYPE_PP
    HAS_PANEL_CORE_UI = g_events is not None
except Exception as e:
    logger.error('[PanelView] playerPanel import failed: %s', e)
    HAS_PANEL_CORE_UI = False
    g_events = None
    TYPE_PP = 'pp'


class PanelView(CallbackDelayer):

    CONTAINER_PP_WINRATE = 'wn8withoutxvm_pp_winrate'

    sessionProvider = dependency.descriptor(IBattleSessionProvider)

    def __init__(self, statsManager):
        CallbackDelayer.__init__(self)
        self._statsManager = statsManager
        self._isInitialized = False
        self._hasPanelCoreUI = HAS_PANEL_CORE_UI
        self._containersCreated = False
        self._arena = None
        self._updatedVehicles = set()
        self._vehicleAccountMap = {}
        self._accountVehicleMap = {}
        self._createdContainers = []
        self._pendingStats = {}
        self._lastUpdateTime = 0
        self._playerTeam = None
        logger.debug('[PanelView] Initialized (hasPanelCoreUI: %s)', self._hasPanelCoreUI)

    def setArena(self, arena):
        self._arena = arena
        self._updatedVehicles.clear()
        self._vehicleAccountMap.clear()
        self._accountVehicleMap.clear()
        self._pendingStats.clear()
        if arena:
            self._buildVehicleMaps()
        logger.debug('[PanelView] Arena set: %s', arena is not None)

    def _buildVehicleMaps(self):
        if not self._arena or not self._arena.vehicles:
            return
        for vehicleID, vehicleData in self._arena.vehicles.items():
            accountDBID = vehicleData.get('accountDBID')
            if accountDBID:
                self._vehicleAccountMap[vehicleID] = accountDBID
                self._accountVehicleMap[accountDBID] = vehicleID

    def initialize(self):
        if not self._hasPanelCoreUI or self._isInitialized:
            return self._isInitialized
        try:
            if g_events:
                g_events.updateMode += self._onUpdateMode
                g_events.onUIReady += self._onUIReady
            self._isInitialized = True
            if g_events and g_events.viewLoad:
                self.delayCallback(0.3, self._initializeContainers)
            logger.debug('[PanelView] Initialized')
            return True
        except Exception as e:
            logger.error('[PanelView] initialize error: %s', e)
            return False

    def _onUIReady(self, *args):
        logger.debug('[PanelView] UI Ready')
        self.delayCallback(0.2, self._initializeContainers)

    def _initializeContainers(self):
        if not self._containersCreated:
            self._createContainers()
        self._processAllPlayers()

    def _onUpdateMode(self):
        currentTime = BigWorld.time()
        if currentTime - self._lastUpdateTime < 0.05:
            return
        self._lastUpdateTime = currentTime
        self.delayCallback(0.02, self._reapplyAllColors)

    def _reapplyAllColors(self):
        if not self._hasPanelCoreUI or not g_events or not g_events.viewLoad:
            return
        try:
            arena = self._getArena()
            if not arena or not arena.vehicles:
                return
            arenaDP = self._getArenaDP()
            if not arenaDP:
                return
            for vehicleID, vehicleData in arena.vehicles.items():
                accountDBID = vehicleData.get('accountDBID')
                if not accountDBID:
                    continue
                stats = self._statsManager.get_cached_stats(accountDBID)
                if stats:
                    self._reapplyVehicleColors(vehicleID, vehicleData, stats, arenaDP)
        except Exception as e:
            logger.error('[PanelView] _reapplyAllColors error: %s', e)

    def _createContainers(self):
        if self._containersCreated:
            return
        if not self._hasPanelCoreUI or not g_events or not g_events.viewLoad:
            logger.debug('[PanelView] Cannot create containers - not ready')
            return
        if not g_events.componentUI:
            logger.debug('[PanelView] Cannot create containers - no componentUI')
            return

        try:
            self._createdContainers = []
            if g_configParams.panelWinratePosition.value == WinratePosition.NEAR_ICON:
                g_events.createPP(self.CONTAINER_PP_WINRATE, self._buildPpWinrateConfig())
                self._createdContainers.append(self.CONTAINER_PP_WINRATE)
                logger.debug('[PanelView] PP Winrate container created')

            self._containersCreated = True
            logger.debug('[PanelView] Containers created: %s', self._createdContainers)

            if self._pendingStats:
                logger.debug('[PanelView] Processing %s pending stats', len(self._pendingStats))
                for accountDBID, stats in self._pendingStats.items():
                    self._updatePlayerDisplay(accountDBID, stats)
                self._pendingStats.clear()
        except Exception as e:
            logger.error('[PanelView] _createContainers error: %s', e)

    def _buildPpWinrateConfig(self):
        state_offsets_left = {'state%d' % s: {'x': 28, 'y': 4} for s in range(8)}
        state_offsets_right = {'state%d' % s: {'x': -78, 'y': 4} for s in range(8)}
        return {
            'textKey': 'pp_winrate',
            'holder': 'vehicleIcon',
            'child': 'vehicleTF',
            'left': {
                'x': 28, 'y': 4, 'width': 50, 'height': 20, 'align': 'left',
                'hideInStates': [8], 'stateOffsets': state_offsets_left,
            },
            'right': {
                'x': -78, 'y': 4, 'width': 50, 'height': 20, 'align': 'right',
                'hideInStates': [8], 'stateOffsets': state_offsets_right,
            },
            'shadow': {
                'distance': 0, 'angle': 90, 'color': '#000000',
                'alpha': 100, 'size': 2, 'strength': 200,
            },
        }

    def _getArena(self):
        if self._arena is not None:
            return self._arena
        try:
            player = BigWorld.player()
            if player and hasattr(player, 'arena'):
                return player.arena
        except Exception as e:
            logger.debug('[PanelView] _getArena error: %s', e)
        return None

    def _getArenaDP(self):
        try:
            sp = self.sessionProvider
            if sp is not None:
                return sp.getArenaDP()
        except Exception as e:
            logger.debug('[PanelView] _getArenaDP error: %s', e)
        return None

    def _processAllPlayers(self):
        if not self._hasPanelCoreUI or not g_events or not g_events.viewLoad:
            return
        try:
            if not self._containersCreated:
                self._createContainers()
                if not self._containersCreated:
                    logger.debug('[PanelView] Containers not ready, retrying...')
                    self.delayCallback(0.5, self._processAllPlayers)
                    return

            arena = self._getArena()
            if not arena or not arena.vehicles:
                return
            arenaDP = self._getArenaDP()
            if not arenaDP:
                return

            self._buildVehicleMaps()
            for vehicleID, vehicleData in arena.vehicles.items():
                accountDBID = vehicleData.get('accountDBID')
                if not accountDBID:
                    continue
                stats = self._statsManager.get_cached_stats(accountDBID)
                if stats:
                    self._applyStatsToVehicle(vehicleID, vehicleData, stats, arenaDP)
                    self._updatedVehicles.add(vehicleID)

            self._pushTabOverlays(arenaDP)
        except Exception as e:
            logger.error('[PanelView] _processAllPlayers error: %s', e)

    def _applyStatsToVehicle(self, vehicleID, vehicleData, stats, arenaDP):
        if not g_events or not g_events.componentUI:
            return
        try:
            listItem = g_events.getPPListItem(vehicleID)
            if not listItem:
                return

            accountDBID = vehicleData.get('accountDBID')
            isAlly = arenaDP.isAllyTeam(vehicleData['team'])
            team = 'left' if isAlly else 'right'

            if not accountDBID:
                self._applyAnonymousPlayer(listItem, vehicleID, team)
                return

            playerInfo = {
                'wn8': stats.get('wn8', 0),
                'wn8_color': stats.get('wn8_color', '#FFFFFF'),
                'winrate': stats.get('winrate', 0),
                'winrate_color': stats.get('winrate_color', '#FFFFFF'),
                'nick': vehicleData.get('name', ''),
                'vehicle': self._getVehicleName(vehicleData),
            }

            self._applyPlayerNameWithWN8(listItem, playerInfo, team)
            self._applyWinrateDisplay(vehicleID, listItem, playerInfo, team)
        except Exception as e:
            logger.error('[PanelView] _applyStatsToVehicle error for %s: %s', vehicleID, e)

    def _applyPlayerNameWithWN8(self, listItem, playerInfo, team):
        try:
            wn8 = playerInfo['wn8']
            wn8Color = playerInfo['wn8_color']
            nick = playerInfo['nick']

            if team == 'left':
                fullText = "<font color='{}'>{}</font> <font color='#CCCCCC'>{}</font>".format(
                    wn8Color, wn8, nick[:14])
                cutText = "<font color='{}'>{}</font>".format(wn8Color, nick[:8])
            else:
                fullText = "<font color='#CCCCCC'>{}</font> <font color='{}'>{}</font>".format(
                    nick[:14], wn8Color, wn8)
                cutText = "<font color='{}'>{}</font>".format(wn8Color, nick[:8])

            if hasattr(listItem, 'playerNameFullTF') and listItem.playerNameFullTF:
                listItem.playerNameFullTF.htmlText = fullText
            if hasattr(listItem, 'playerNameCutTF') and listItem.playerNameCutTF:
                listItem.playerNameCutTF.htmlText = cutText
        except Exception as e:
            logger.error('[PanelView] _applyPlayerNameWithWN8 error: %s', e)

    def _applyWinrateDisplay(self, vehicleID, listItem, playerInfo, team):
        winratePosition = g_configParams.panelWinratePosition.value
        if winratePosition == WinratePosition.NEAR_ICON:
            if self.CONTAINER_PP_WINRATE in self._createdContainers:
                winrateText = "<font color='{}' size='10'><b>{}%</b></font>".format(
                    playerInfo['winrate_color'], playerInfo['winrate'])
                g_events.update(self.CONTAINER_PP_WINRATE, {
                    'vehicleID': vehicleID,
                    'text': winrateText,
                })
                g_events.updatePosition(self.CONTAINER_PP_WINRATE, vehicleID)
        elif winratePosition == WinratePosition.BEFORE_VEHICLE:
            vehicleName = playerInfo['vehicle']
            winrateText = "<font color='{}'>{}%</font> {}".format(
                playerInfo['winrate_color'], playerInfo['winrate'], vehicleName)
            if hasattr(listItem, 'vehicleTF') and listItem.vehicleTF:
                listItem.vehicleTF.htmlText = winrateText

    def _applyAnonymousPlayer(self, listItem, vehicleID, team):
        try:
            if hasattr(listItem, 'playerNameFullTF') and listItem.playerNameFullTF:
                listItem.playerNameFullTF.htmlText = u'<font color="#888888">Anonymous</font>'
            if hasattr(listItem, 'playerNameCutTF') and listItem.playerNameCutTF:
                listItem.playerNameCutTF.htmlText = u'<font color="#888888">Anon</font>'
            if g_configParams.panelWinratePosition.value == WinratePosition.NEAR_ICON:
                if self.CONTAINER_PP_WINRATE in self._createdContainers:
                    g_events.update(self.CONTAINER_PP_WINRATE, {
                        'vehicleID': vehicleID,
                        'text': '',
                    })
        except Exception as e:
            logger.error('[PanelView] _applyAnonymousPlayer error: %s', e)

    def _reapplyVehicleColors(self, vehicleID, vehicleData, stats, arenaDP):
        if not g_events or not g_events.componentUI:
            return
        try:
            listItem = g_events.getPPListItem(vehicleID)
            if not listItem:
                return
            accountDBID = vehicleData.get('accountDBID')
            if not accountDBID:
                return

            isAlly = arenaDP.isAllyTeam(vehicleData['team'])
            team = 'left' if isAlly else 'right'
            wn8 = stats.get('wn8', 0)
            wn8Color = stats.get('wn8_color', '#FFFFFF')
            winrate = stats.get('winrate', 0)
            winrateColor = stats.get('winrate_color', '#FFFFFF')
            nick = vehicleData.get('name', '')

            if team == 'left':
                fullText = "<font color='{}'>{}</font> <font color='#CCCCCC'>{}</font>".format(
                    wn8Color, wn8, nick[:14])
                cutText = "<font color='{}'>{}</font>".format(wn8Color, nick[:8])
            else:
                fullText = "<font color='#CCCCCC'>{}</font> <font color='{}'>{}</font>".format(
                    nick[:14], wn8Color, wn8)
                cutText = "<font color='{}'>{}</font>".format(wn8Color, nick[:8])
            if hasattr(listItem, 'playerNameFullTF') and listItem.playerNameFullTF:
                listItem.playerNameFullTF.htmlText = fullText
            if hasattr(listItem, 'playerNameCutTF') and listItem.playerNameCutTF:
                listItem.playerNameCutTF.htmlText = cutText

            if g_configParams.panelWinratePosition.value == WinratePosition.BEFORE_VEHICLE:
                vehicleName = self._getVehicleName(vehicleData)
                winrateText = "<font color='{}'>{}%</font> {}".format(
                    winrateColor, winrate, vehicleName)
                if hasattr(listItem, 'vehicleTF') and listItem.vehicleTF:
                    listItem.vehicleTF.htmlText = winrateText
        except Exception as e:
            logger.error('[PanelView] _reapplyVehicleColors error for %s: %s', vehicleID, e)

    def _getVehicleName(self, vehicleData):
        try:
            vehicleType = vehicleData.get('vehicleType')
            if vehicleType and hasattr(vehicleType, 'type') and hasattr(vehicleType.type, 'shortUserString'):
                return vehicleType.type.shortUserString
        except Exception:
            pass
        return ''

    def _pushTabOverlays(self, arenaDP):
        """
        For each ally/enemy row push a (vehicleID, WN8-html) pair to our SWF
        overlay. SWF reads playerNameCollection[col*numRows+row] and draws
        our TextField right next to WG name. Works in Random / Stronghold
        / Comp7 (all use battlePage.swf + strongholdBattlePage.swf which
        share FullStatsTable layout).
        """
        if not g_events or not g_events.componentUI:
            return
        try:
            ally_ids = vos_collections.AllyItemsCollection().ids(arenaDP)
            enemy_ids = vos_collections.EnemyItemsCollection().ids(arenaDP)
            allies = [self._buildTabRow(vID) for vID in ally_ids]
            enemies = [self._buildTabRow(vID) for vID in enemy_ids]
            g_events.setTabOverlay(allies, enemies)
        except Exception as e:
            logger.debug('[PanelView] _pushTabOverlays error: %s', e)

    def _buildTabRow(self, vehicleID):
        if not vehicleID:
            return {'vehicleID': 0, 'text': ''}
        arena = self._getArena()
        if not arena or not arena.vehicles:
            return {'vehicleID': vehicleID, 'text': ''}
        vehicleData = arena.vehicles.get(vehicleID) or {}
        accountDBID = vehicleData.get('accountDBID')
        if not accountDBID:
            return {'vehicleID': vehicleID, 'text': ''}
        stats = self._statsManager.get_cached_stats(accountDBID)
        if not stats:
            return {'vehicleID': vehicleID, 'text': ''}

        parts = []
        if g_configParams.showWn8.value:
            wn8 = int(stats.get('wn8', 0) or 0)
            if wn8:
                parts.append("<font color='{}'><b>{}</b></font>".format(
                    stats.get('wn8_color', '#FFFFFF'), wn8))
        if g_configParams.showWinrate.value:
            winrate = float(stats.get('winrate', 0) or 0)
            if winrate > 0:
                parts.append("<font color='{}'>{:.1f}%</font>".format(
                    stats.get('winrate_color', '#FFFFFF'), winrate))
        if g_configParams.showBattles.value:
            battles = int(stats.get('battles', 0) or 0)
            if battles:
                parts.append("<font color='{}'>{}</font>".format(
                    stats.get('battles_color', '#FFFFFF'), battles))

        return {'vehicleID': vehicleID, 'text': ' '.join(parts)}

    def _updatePlayerDisplay(self, accountDBID, stats=None):
        if not stats:
            return
        if not self._containersCreated:
            self._pendingStats[accountDBID] = stats
            return
        vehicleID = self._accountVehicleMap.get(accountDBID)
        if vehicleID is None:
            arena = self._getArena()
            if arena and arena.vehicles:
                for vID, vData in arena.vehicles.items():
                    if vData.get('accountDBID') == accountDBID:
                        vehicleID = vID
                        self._vehicleAccountMap[vID] = accountDBID
                        self._accountVehicleMap[accountDBID] = vID
                        break
        if vehicleID is not None:
            self._updatedVehicles.add(vehicleID)
            self.delayCallback(0.1, self._processAllPlayers)

    def updateAllPlayers(self):
        self.delayCallback(0, self._processAllPlayers)

    def finalize(self):
        if not self._isInitialized:
            return
        try:
            if self._hasPanelCoreUI and g_events:
                try:
                    g_events.updateMode -= self._onUpdateMode
                except Exception:
                    pass
                try:
                    g_events.onUIReady -= self._onUIReady
                except Exception:
                    pass
                g_events.clearTabOverlay()
                g_events.clearCache()
                for container in self._createdContainers:
                    try:
                        g_events.delete(container)
                    except Exception as e:
                        logger.debug('[PanelView] Error deleting %s: %s', container, e)

            self._createdContainers = []
            self._updatedVehicles.clear()
            self._vehicleAccountMap.clear()
            self._accountVehicleMap.clear()
            self._pendingStats.clear()
            self._isInitialized = False
            self._containersCreated = False
            self._arena = None
            self._playerTeam = None
            self.clearCallbacks()
            logger.debug('[PanelView] Finalized')
        except Exception as e:
            logger.error('[PanelView] finalize error: %s', e)

    def destroy(self):
        self.finalize()
        self._statsManager = None
        self._updatedVehicles.clear()
        self._vehicleAccountMap.clear()
        self._accountVehicleMap.clear()
        self._createdContainers = []
        self._pendingStats.clear()
        self._arena = None
        logger.debug('[PanelView] Destroyed')
