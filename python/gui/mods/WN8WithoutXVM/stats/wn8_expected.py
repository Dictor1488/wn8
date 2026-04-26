import BigWorld
from wg_async import wg_async, AsyncReturn

from ..utils import logger, fetch_data_with_retry
from .disk_cache import DiskCache


WN8_EXP_URLS = (
    "https://static.modxvm.com/wn8-data-exp/json/wn8exp.json",
    "https://wotnumbers.com/wn8/wn8.json",
)


_CACHE_LIFETIME = 7 * 24 * 3600
_CACHE_VERSION = 1
_CACHE_KEY = 'table'


class WN8ExpectedValues(object):

    def __init__(self):
        self._table = {}
        self._is_loaded = False
        self._is_loading = False
        self._waiters = []
        self._cache = DiskCache('wn8_expected.dat',
                                version=_CACHE_VERSION,
                                lifetime=_CACHE_LIFETIME)
        self._cache.load()

    @property
    def is_loaded(self):
        return self._is_loaded

    def get(self, tank_id):
        return self._table.get(int(tank_id))

    def load(self, callback=None):

        if self._is_loaded:
            if callback:
                BigWorld.callback(0.0, lambda: callback(True))
            return

        if callback:
            self._waiters.append(callback)

        if self._is_loading:
            return

        self._is_loading = True

        try:
            if self._load_from_cache():
                self._notify(True)
                return
        except Exception:
            logger.exception('[WN8Expected] cache load failed')

        self._fetch_from_network()

    def _load_from_cache(self):
        cached = self._cache.get(_CACHE_KEY)
        if not cached:
            return False
        if not isinstance(cached, dict):
            return False

        self._table = cached
        self._is_loaded = True
        logger.debug('[WN8Expected] loaded %d tanks from disk cache', len(self._table))
        return True

    @wg_async
    def _fetch_from_network(self):
        for url in WN8_EXP_URLS:
            try:
                logger.debug('[WN8Expected] fetching %s', url)
                data = yield fetch_data_with_retry(url, retries=2, delay=3, timeout=20.0)
                if not data:
                    continue
                table = self._build_table(data)
                if not table:
                    logger.error('[WN8Expected] empty/invalid table from %s', url)
                    continue

                self._table = table
                self._is_loaded = True
                self._cache.set(_CACHE_KEY, table)
                logger.debug('[WN8Expected] loaded %d tanks from network', len(self._table))
                self._notify(True)
                raise AsyncReturn(None)
            except AsyncReturn:
                raise
            except Exception:
                logger.exception('[WN8Expected] fetch failed for %s', url)

        logger.error('[WN8Expected] all sources failed; WN8 will report 0')
        self._notify(False)
        raise AsyncReturn(None)

    def _build_table(self, raw):
        if not raw:
            return {}
        items = raw.get('data') if isinstance(raw, dict) else raw
        if not items:
            return {}
        table = {}
        for item in items:
            try:
                tid = int(item.get('IDNum'))
            except (TypeError, ValueError):
                continue
            table[tid] = {
                'expDamage': float(item.get('expDamage', 0) or 0),
                'expFrag': float(item.get('expFrag', 0) or 0),
                'expSpot': float(item.get('expSpot', 0) or 0),
                'expDef': float(item.get('expDef', 0) or 0),
                'expWinRate': float(item.get('expWinRate', 0) or 0),
            }
        return table

    def _notify(self, ok):
        self._is_loading = False
        waiters = self._waiters
        self._waiters = []
        for cb in waiters:
            try:
                BigWorld.callback(0.0, lambda c=cb, value=ok: c(value))
            except Exception:
                logger.exception('[WN8Expected] notify error')

    def fini(self):
        try:
            self._cache.flush()
        finally:
            self._cache.fini()


g_wn8_expected = WN8ExpectedValues()
