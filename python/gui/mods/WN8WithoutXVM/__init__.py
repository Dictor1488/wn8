from .utils import logger
from .stats import initialize_stats, finalize_stats
from .views import PatchBattlePlayer, PanelView, PatchBattleLoading

__all__ = [
    'initialize',
    'finalize'
]

g_patch_battle_player = None
g_patch_battle_loading = None
g_panel_view = None
g_battle_provider = None


def initialize():
    global g_patch_battle_player, g_patch_battle_loading
    global g_panel_view, g_battle_provider
    try:
        initialize_stats()

        from .stats import g_stats_manager

        if g_patch_battle_player is None:
            g_patch_battle_player = PatchBattlePlayer(g_stats_manager)
            g_patch_battle_player.apply_patches()
            logger.debug('[WN8WithoutXVM] PatchBattlePlayer created and applied')

        if g_patch_battle_loading is None:
            g_patch_battle_loading = PatchBattleLoading(g_stats_manager)
            g_patch_battle_loading.apply_patches()
            logger.debug('[WN8WithoutXVM] PatchBattleLoading created and applied')

        if g_panel_view is None:
            g_panel_view = PanelView(g_stats_manager)
            logger.debug('[WN8WithoutXVM] PanelView created')

        if g_battle_provider is None:
            from .battle_provider import BattleProvider
            g_battle_provider = BattleProvider(g_stats_manager, g_panel_view)
            logger.debug('[WN8WithoutXVM] BattleProvider initialized')

        logger.debug('[WN8WithoutXVM] All components initialized successfully')

    except Exception:
        logger.exception('[WN8WithoutXVM] Initialization failed')
        finalize()


def finalize():
    global g_patch_battle_player, g_patch_battle_loading
    global g_panel_view, g_battle_provider
    try:
        if g_battle_provider:
            g_battle_provider.fini()
            g_battle_provider = None
            logger.debug('[WN8WithoutXVM] BattleProvider finalized')

        if g_panel_view:
            g_panel_view.destroy()
            g_panel_view = None
            logger.debug('[WN8WithoutXVM] PanelView finalized')

        if g_patch_battle_loading:
            g_patch_battle_loading.remove_patches()
            g_patch_battle_loading = None
            logger.debug('[WN8WithoutXVM] PatchBattleLoading finalized')

        if g_patch_battle_player:
            g_patch_battle_player.remove_patches()
            g_patch_battle_player = None
            logger.debug('[WN8WithoutXVM] PatchBattlePlayer finalized')

        finalize_stats()

        logger.debug('[WN8WithoutXVM] All components finalized successfully')

    except Exception:
        logger.exception('[WN8WithoutXVM] Finalization failed')
