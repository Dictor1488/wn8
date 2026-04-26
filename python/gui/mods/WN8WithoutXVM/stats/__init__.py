from ..utils import logger
from .stats_api import StatsAPI
from .stats_manager import StatsManager
from .wn8_expected import g_wn8_expected

__all__ = [
    'initialize_stats',
    'finalize_stats',
    'g_stats_manager',
    'g_stats_api'
]

g_stats_api = None
g_stats_manager = None


def initialize_stats():
    global g_stats_api, g_stats_manager
    try:
        if g_stats_api is None:
            g_stats_api = StatsAPI()
            logger.debug('[StatsAPI] Initialized')

        if g_stats_manager is None:
            g_stats_manager = StatsManager(g_stats_api)
            logger.debug('[StatsManager] Initialized')

        logger.debug('[WN8WithoutXVM] Stats components initialized successfully')

    except Exception:
        logger.exception('[WN8WithoutXVM] Stats initialization failed')


def finalize_stats():
    global g_stats_api, g_stats_manager
    try:
        if g_stats_manager:
            g_stats_manager.clear_update_callbacks()
            g_stats_manager.clear_cache()
            g_stats_manager = None
            logger.debug('[StatsManager] Finalized')

        if g_stats_api:
            g_stats_api.fini()
            g_stats_api = None
            logger.debug('[StatsAPI] Finalized')

        try:
            g_wn8_expected.fini()
        except Exception:
            logger.exception('[WN8Expected] fini failed')

        logger.debug('[WN8WithoutXVM] Stats components finalized successfully')

    except Exception:
        logger.exception('[WN8WithoutXVM] Stats finalization failed')
