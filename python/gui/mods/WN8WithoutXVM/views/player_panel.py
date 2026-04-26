import copy
import Event
import BigWorld
from Avatar import PlayerAvatar
from gui.shared.personality import ServicesLocator
from gui.shared import events, g_eventBus, EVENT_BUS_SCOPE
from gui.Scaleform.framework.entities.View import View
from gui.Scaleform.framework import g_entitiesFactories, ScopeTemplates, ViewSettings, ComponentSettings
from frameworks.wulf import WindowLayer
from gui.Scaleform.daapi.view.battle.classic.players_panel import PlayersPanel
from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
from gui.Scaleform.genConsts.BATTLE_VIEW_ALIASES import BATTLE_VIEW_ALIASES
from gui.Scaleform.framework.entities.BaseDAAPIComponent import BaseDAAPIComponent
from gui.Scaleform.daapi.view.meta.PlayersPanelMeta import PlayersPanelMeta
from gui.Scaleform.daapi.view.battle.shared.stats_exchange.stats_ctrl import BattleStatisticsDataController

from ..utils import logger


TYPE_PP = 'pp'
TYPE_TAB = 'tab'
WN8_PLAYER_PANEL_ALIAS = 'wn8wx_playerPanel'
AS3_FLASH_COMPONENT_NAME = 'playerPanel'


class PlayerPanelMeta(BaseDAAPIComponent):

    def _populate(self):
        try:
            super(PlayerPanelMeta, self)._populate()
            if g_events:
                g_events._populate(self)
        except Exception as e:
            logger.error('[PlayerPanel] populate error: %s', e)

    def _dispose(self):
        try:
            if g_events:
                g_events._dispose(self)
            super(PlayerPanelMeta, self)._dispose()
        except Exception as e:
            logger.error('[PlayerPanel] dispose error: %s', e)

    def flashLogS(self, *data):
        logger.debug('[PlayerPanel] Flash: %s', data)

    def as_setStatsDataS(self, vehicleID, data):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_setStatsData(vehicleID, data)
            except Exception as e:
                logger.error('[PlayerPanel] as_setStatsDataS error: %s', e)
        return None

    def as_clearCacheS(self):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_clearCache()
            except Exception as e:
                logger.error('[PlayerPanel] as_clearCacheS error: %s', e)
        return None

    def as_createS(self, container, config):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_create(container, config)
            except Exception as e:
                logger.error('[PlayerPanel] as_createS error: %s', e)
        return None

    def as_updateS(self, container, data):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_update(container, data)
            except Exception as e:
                logger.error('[PlayerPanel] as_updateS error: %s', e)
        return None

    def as_deleteS(self, container):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_delete(container)
            except Exception as e:
                logger.error('[PlayerPanel] as_deleteS error: %s', e)
        return None

    def as_updatePositionS(self, container, vehicleID):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_updatePosition(container, vehicleID)
            except Exception as e:
                logger.error('[PlayerPanel] as_updatePositionS error: %s', e)
        return None

    def as_updateAllPositionsS(self):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_updateAllPositions()
            except Exception as e:
                logger.error('[PlayerPanel] as_updateAllPositionsS error: %s', e)
        return None

    def as_setPanelStateS(self, state):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_setPanelState(state)
            except Exception as e:
                logger.error('[PlayerPanel] as_setPanelStateS error: %s', e)
        return None

    def as_hasOwnPropertyS(self, container):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_hasOwnProperty(container)
            except Exception as e:
                logger.error('[PlayerPanel] as_hasOwnPropertyS error: %s', e)
        return False

    def as_shadowListItemS(self, shadow):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_shadowListItem(shadow)
            except Exception as e:
                logger.error('[PlayerPanel] as_shadowListItemS error: %s', e)
        return None

    def as_extendedSettingS(self, container, vehicleID):
        if self._isDAAPIInited():
            try:
                return self.flashObject.extendedSetting(container, vehicleID)
            except Exception as e:
                logger.error('[PlayerPanel] as_extendedSettingS error: %s', e)
        return None

    def as_getPPListItemS(self, vehicleID):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_getPPListItem(vehicleID)
            except Exception as e:
                logger.error('[PlayerPanel] as_getPPListItemS error: %s', e)
        return None

    def as_getPlayersPanelS(self):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_getPlayersPanel()
            except Exception as e:
                logger.error('[PlayerPanel] as_getPlayersPanelS error: %s', e)
        return None

    def as_vehicleIconColorS(self, vehicleID, color):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_vehicleIconColor(vehicleID, color)
            except Exception as e:
                logger.error('[PlayerPanel] as_vehicleIconColorS error: %s', e)
        return None

    def as_setTabOverlayS(self, allies, enemies):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_setTabOverlay(allies, enemies)
            except Exception as e:
                logger.error('[PlayerPanel] as_setTabOverlayS error: %s', e)
        return None

    def as_clearTabOverlayS(self):
        if self._isDAAPIInited():
            try:
                return self.flashObject.as_clearTabOverlay()
            except Exception as e:
                logger.error('[PlayerPanel] as_clearTabOverlayS error: %s', e)
        return None


class Events(object):

    def __init__(self):
        self.impl = False
        self.viewLoad = False
        self.componentUI = None
        self.onUIReady = Event.Event()
        self.updateMode = Event.Event()
        self._currentPanelState = -1
        self._patchesApplied = False

        self._applyPatches()

        self.configPP = {
            'type': TYPE_PP,
            'child': 'vehicleTF',
            'holder': 'vehicleIcon',
            'textKey': '',
            'left': {
                'x': 0,
                'y': 0,
                'align': 'left',
                'height': 24,
                'width': 100,
                'hideInStates': [],
                'stateOffsets': {}
            },
            'right': {
                'x': 0,
                'y': 0,
                'align': 'right',
                'height': 24,
                'width': 100,
                'hideInStates': [],
                'stateOffsets': {}
            },
            'shadow': {
                'distance': 0,
                'angle': 90,
                'color': '#000000',
                'alpha': 100,
                'size': 2,
                'strength': 200
            }
        }

        self.configTAB = {
            'type': TYPE_TAB,
            'textKey': '',
            'left': {
                'x': 5,
                'y': 2,
                'align': 'left',
                'height': 20,
                'width': 80
            },
            'right': {
                'x': -85,
                'y': 2,
                'align': 'right',
                'height': 20,
                'width': 80
            },
            'shadow': {
                'distance': 0,
                'angle': 90,
                'color': '#000000',
                'alpha': 100,
                'size': 2,
                'strength': 200
            }
        }

    def _applyPatches(self):
        if self._patchesApplied:
            return

        try:
            originalHandleNextMode = PlayersPanel._handleNextMode
            originalSetPanelModeS = PlayersPanelMeta.as_setPanelModeS
            originalPPSetPanelModeS = PlayersPanel.as_setPanelModeS
            originalTrySetPanelModeByMouse = PlayersPanel.tryToSetPanelModeByMouse
            originalPanelMetaTrySetPanelModeByMouse = PlayersPanelMeta.tryToSetPanelModeByMouse
            originalUpdateVehiclesInfo = BattleStatisticsDataController.updateVehiclesInfo
            originalUpdateVehiclesStats = BattleStatisticsDataController.updateVehiclesStats
            originalSetInitialMode = PlayersPanel.setInitialMode
            originalSetLargeMode = PlayersPanel.setLargeMode

            def patchedSetInitialMode(ppSelf):
                result = originalSetInitialMode(ppSelf)
                self._onPanelModeChanged(ppSelf)
                return result

            def patchedSetLargeMode(ppSelf):
                result = originalSetLargeMode(ppSelf)
                self._onPanelModeChanged(ppSelf)
                return result

            def patchedHandleNextMode(ppSelf, value):
                result = originalHandleNextMode(ppSelf, value)
                self._onPanelModeChanged(ppSelf)
                return result

            def patchedSetPanelModeS(ppSelf, value):
                result = originalSetPanelModeS(ppSelf, value)
                self._onPanelModeChanged(ppSelf)
                return result

            def patchedPPSetPanelModeS(ppSelf, value):
                result = originalPPSetPanelModeS(ppSelf, value)
                self._onPanelModeChanged(ppSelf)
                return result

            def patchedTrySetPanelModeByMouse(ppSelf, value):
                result = originalTrySetPanelModeByMouse(ppSelf, value)
                self._onPanelModeChanged(ppSelf)
                return result

            def patchedPanelMetaTrySetPanelModeByMouse(ppSelf, value):
                result = originalPanelMetaTrySetPanelModeByMouse(ppSelf, value)
                self._onPanelModeChanged(ppSelf)
                return result

            def patchedUpdateVehiclesInfo(ctrlSelf, updated, arenaDP):
                originalUpdateVehiclesInfo(ctrlSelf, updated, arenaDP)
                self._onVehiclesUpdated()

            def patchedUpdateVehiclesStats(ctrlSelf, updated, arenaDP):
                originalUpdateVehiclesStats(ctrlSelf, updated, arenaDP)
                self._onVehiclesUpdated()

            PlayersPanel.setInitialMode = patchedSetInitialMode
            PlayersPanel.setLargeMode = patchedSetLargeMode
            PlayersPanel._handleNextMode = patchedHandleNextMode
            PlayersPanelMeta.as_setPanelModeS = patchedSetPanelModeS
            PlayersPanel.as_setPanelModeS = patchedPPSetPanelModeS
            PlayersPanel.tryToSetPanelModeByMouse = patchedTrySetPanelModeByMouse
            PlayersPanelMeta.tryToSetPanelModeByMouse = patchedPanelMetaTrySetPanelModeByMouse
            BattleStatisticsDataController.updateVehiclesInfo = patchedUpdateVehiclesInfo
            BattleStatisticsDataController.updateVehiclesStats = patchedUpdateVehiclesStats

            if hasattr(PlayersPanel, '_PlayersPanel__handleShowExtendedInfo'):
                originalHandleShowExtendedInfo = PlayersPanel._PlayersPanel__handleShowExtendedInfo

                def patchedHandleShowExtendedInfo(ppSelf, value):
                    result = originalHandleShowExtendedInfo(ppSelf, value)
                    self._onPanelModeChanged(ppSelf)
                    return result

                PlayersPanel._PlayersPanel__handleShowExtendedInfo = patchedHandleShowExtendedInfo

            if hasattr(PlayersPanel, 'setOverrideExInfo'):
                originalSetOverrideExInfo = PlayersPanel.setOverrideExInfo

                def patchedSetOverrideExInfo(ppSelf, value):
                    result = originalSetOverrideExInfo(ppSelf, value)
                    self._onPanelModeChanged(ppSelf)
                    return result

                PlayersPanel.setOverrideExInfo = patchedSetOverrideExInfo

            self._patchesApplied = True
            logger.debug('[PlayerPanel] Patches applied')

        except Exception as e:
            logger.error('[PlayerPanel] Failed to apply patches: %s', e)

    def _onPanelModeChanged(self, ppSelf=None):
        if not self.impl:
            return

        try:
            state = -1
            if ppSelf and hasattr(ppSelf, '_state'):
                state = ppSelf._state
            elif ppSelf and hasattr(ppSelf, 'state'):
                state = ppSelf.state

            if state >= 0 and state != self._currentPanelState:
                self._currentPanelState = state
                if self.componentUI:
                    self.componentUI.as_setPanelStateS(state)

            self.updateMode()
        except Exception as e:
            logger.error('[PlayerPanel] _onPanelModeChanged error: %s', e)

    def _onVehiclesUpdated(self):
        if self.impl:
            self.updateMode()

    def _populate(self, baseSelf):
        self.viewLoad = True
        self.componentUI = baseSelf
        logger.debug('[PlayerPanel] Populated')
        BigWorld.callback(0.1, lambda: self.onUIReady(self, 'playerPanel', baseSelf))

    def _dispose(self, baseSelf):
        self.impl = False
        self.viewLoad = False
        self.componentUI = None
        self._currentPanelState = -1
        logger.debug('[PlayerPanel] Disposed')

    def _deepUpdate(self, target, source):
        changed = False
        for key in target:
            if key in source:
                value = source[key]
                if isinstance(value, dict) and isinstance(target[key], dict):
                    changed = self._deepUpdate(target[key], value) or changed
                elif value is not None:
                    if isinstance(value, unicode):
                        value = value.encode('utf-8')
                    if target[key] != value:
                        target[key] = value
                        changed = True
        return changed

    def setStatsData(self, vehicleID, data):
        if not self.componentUI:
            return None
        try:
            return self.componentUI.as_setStatsDataS(vehicleID, data)
        except Exception as e:
            logger.error('[PlayerPanel] setStatsData error: %s', e)
        return None

    def clearCache(self):
        if self.componentUI:
            try:
                return self.componentUI.as_clearCacheS()
            except Exception as e:
                logger.error('[PlayerPanel] clearCache error: %s', e)
        return None

    def create(self, container, config=None, containerType=TYPE_PP):
        if not container:
            return None

        if not self.componentUI:
            logger.debug('[PlayerPanel] create: componentUI is None')
            return None

        try:
            if containerType == TYPE_TAB:
                baseConfig = copy.deepcopy(self.configTAB)
            else:
                baseConfig = copy.deepcopy(self.configPP)

            if config:
                self._deepUpdate(baseConfig, config)

            return self.componentUI.as_createS(container, baseConfig)
        except Exception as e:
            logger.error('[PlayerPanel] create error: %s', e)
        return None

    def createPP(self, container, config=None):
        return self.create(container, config, TYPE_PP)

    def createTAB(self, container, config=None):
        return self.create(container, config, TYPE_TAB)

    def update(self, container, data):
        if not container or not data:
            return None

        if not self.componentUI:
            return None

        try:
            if 'text' in data:
                data['text'] = data['text'].replace('$IMELanguageBar', '$FieldFont')

            return self.componentUI.as_updateS(container, data)
        except Exception as e:
            logger.error('[PlayerPanel] update error: %s', e)
        return None

    def delete(self, container):
        if not container:
            return None

        if self.componentUI:
            try:
                return self.componentUI.as_deleteS(container)
            except Exception as e:
                logger.error('[PlayerPanel] delete error: %s', e)
        return None

    def hasOwnProperty(self, container):
        if self.componentUI:
            try:
                return self.componentUI.as_hasOwnPropertyS(container)
            except Exception as e:
                logger.error('[PlayerPanel] hasOwnProperty error: %s', e)
        return False

    def updatePosition(self, container, vehicleID):
        if self.componentUI:
            try:
                return self.componentUI.as_updatePositionS(container, vehicleID)
            except Exception as e:
                logger.error('[PlayerPanel] updatePosition error: %s', e)
        return None

    def updateAllPositions(self):
        if self.componentUI:
            try:
                return self.componentUI.as_updateAllPositionsS()
            except Exception as e:
                logger.error('[PlayerPanel] updateAllPositions error: %s', e)
        return None

    def shadowListItem(self, shadow):
        if self.componentUI:
            try:
                return self.componentUI.as_shadowListItemS(shadow)
            except Exception as e:
                logger.error('[PlayerPanel] shadowListItem error: %s', e)
        return None

    def vehicleIconColor(self, vehicleID, color):
        if not vehicleID or not color:
            return None

        if self.componentUI:
            try:
                return self.componentUI.as_vehicleIconColorS(vehicleID, color)
            except Exception as e:
                logger.error('[PlayerPanel] vehicleIconColor error: %s', e)
        return None

    def extendedSetting(self, container, vehicleID):
        if self.componentUI:
            try:
                return self.componentUI.as_extendedSettingS(container, vehicleID)
            except Exception as e:
                logger.error('[PlayerPanel] extendedSetting error: %s', e)
        return None

    def getPPListItem(self, vehicleID):
        if self.componentUI:
            try:
                return self.componentUI.as_getPPListItemS(vehicleID)
            except Exception as e:
                logger.error('[PlayerPanel] getPPListItem error: %s', e)
        return None

    def getPlayersPanel(self):
        if self.componentUI:
            try:
                return self.componentUI.as_getPlayersPanelS()
            except Exception as e:
                logger.error('[PlayerPanel] getPlayersPanel error: %s', e)
        return None

    def setTabOverlay(self, allies, enemies):
        if self.componentUI:
            try:
                return self.componentUI.as_setTabOverlayS(allies, enemies)
            except Exception as e:
                logger.error('[PlayerPanel] setTabOverlay error: %s', e)
        return None

    def clearTabOverlay(self):
        if self.componentUI:
            try:
                return self.componentUI.as_clearTabOverlayS()
            except Exception as e:
                logger.error('[PlayerPanel] clearTabOverlay error: %s', e)
        return None

    def onComponentRegistered(self, event):
        try:
            if event.alias != BATTLE_VIEW_ALIASES.PLAYERS_PANEL:
                return
            self.impl = True
            ServicesLocator.appLoader.getDefBattleApp().loadView(
                SFViewLoadParams(WN8_PLAYER_PANEL_ALIAS, WN8_PLAYER_PANEL_ALIAS), {}
            )
            logger.debug('[PlayerPanel] View loaded')
        except Exception as e:
            logger.error('[PlayerPanel] onComponentRegistered error: %s', e)


g_events = None

if g_entitiesFactories.getSettings(WN8_PLAYER_PANEL_ALIAS) is None:
    g_events = Events()
    try:
        g_entitiesFactories.addSettings(ViewSettings(
            WN8_PLAYER_PANEL_ALIAS,
            View,
            'playerPanel.swf',
            WindowLayer.WINDOW,
            None,
            ScopeTemplates.GLOBAL_SCOPE
        ))
    except Exception as e:
        logger.debug('[PlayerPanel] ViewSettings already registered: %s', e)

    try:
        g_entitiesFactories.addSettings(ComponentSettings(
            AS3_FLASH_COMPONENT_NAME,
            PlayerPanelMeta,
            ScopeTemplates.DEFAULT_SCOPE
        ))
    except Exception as e:
        logger.debug('[PlayerPanel] ComponentSettings already registered: %s', e)

    try:
        g_eventBus.addListener(
            events.ComponentEvent.COMPONENT_REGISTERED,
            g_events.onComponentRegistered,
            scope=EVENT_BUS_SCOPE.GLOBAL
        )
        logger.debug('[PlayerPanel] Initialized')
    except Exception as e:
        logger.error('[PlayerPanel] EventBus listener failed: %s', e)
