from WN8WithoutXVM.utils import logger
from WN8WithoutXVM import initialize, finalize

__version__ = '0.0.1'
__author__ = 'Under_Pressure'
__copyright__ = 'Copyright 2026, Under_Pressure'
__mod_name__ = 'WN8WithoutXVM'


def init():
    logger.debug('START LOADING: v%s', __version__)
    try:
        initialize()
        logger.debug('LOADED SUCCESSFULLY: v%s', __version__)
    except Exception as e:
        logger.error('LOADING FAILED: %s', e)
        import traceback
        logger.error('Traceback: %s', traceback.format_exc())


def fini():
    logger.debug('SHUTTING DOWN: v%s', __version__)
    try:
        finalize()
        logger.debug('SHUTDOWN COMPLETE: v%s', __version__)
    except Exception as e:
        logger.error('SHUTDOWN FAILED: %s', e)
