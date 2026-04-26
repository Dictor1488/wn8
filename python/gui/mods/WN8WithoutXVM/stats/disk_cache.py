import cPickle
import functools
import os
import time
import zlib

import BigWorld

from ..utils import logger, cancelCallbackSafe


def _resolve_cache_dir():

    try:
        prefs_path = BigWorld.wg_getPreferencesFilePath()
    except AttributeError:
        try:
            prefs_path = BigWorld.getPreferencesFilePath()
        except Exception:
            prefs_path = ''
    base = os.path.dirname(prefs_path) if prefs_path else ''
    return os.path.normpath(os.path.join(base, 'mods', 'wn8withoutxvm'))


CACHE_DIR = _resolve_cache_dir()


class DiskCache(object):


    SAVE_DELAY = 1.0

    def __init__(self, filename, version=1, lifetime=3600):
        self._path = os.path.join(CACHE_DIR, filename)
        self._version = int(version)
        self._lifetime = int(lifetime)
        self._data = {}
        self._save_rev = 0
        self._save_cb = None
        self._loaded = False


    def load(self):
        if self._loaded:
            return True
        self._loaded = True

        if not os.path.isdir(CACHE_DIR):
            try:
                os.makedirs(CACHE_DIR)
            except OSError as e:
                logger.error('[DiskCache:%s] mkdir failed: %s', self._path, e)
                return False

        if not os.path.isfile(self._path):
            return False

        try:
            with open(self._path, 'rb') as fh:
                payload, version = cPickle.loads(zlib.decompress(fh.read()))
            if version != self._version:
                logger.debug('[DiskCache:%s] version mismatch (%s != %s) - dropping',
                             self._path, version, self._version)
                self._data = {}
                return False
            self._data = payload.get('data', {}) if isinstance(payload, dict) else {}
            logger.debug('[DiskCache:%s] loaded %d entries', self._path, len(self._data))
            return True
        except Exception:
            logger.exception('[DiskCache:%s] load failed', self._path)
            self._data = {}
            return False

    def save(self):

        self._save_rev += 1
        rev = self._save_rev
        cancelCallbackSafe(self._save_cb)
        self._save_cb = BigWorld.callback(self.SAVE_DELAY, functools.partial(self._do_save, rev))

    def _do_save(self, rev):
        self._save_cb = None
        if rev != self._save_rev:
            return
        try:
            if not os.path.isdir(CACHE_DIR):
                os.makedirs(CACHE_DIR)
            payload = {'data': self._data}
            blob = zlib.compress(
                cPickle.dumps((payload, self._version), cPickle.HIGHEST_PROTOCOL),
                1
            )
            with open(self._path, 'wb') as fh:
                fh.write(blob)
            logger.debug('[DiskCache:%s] saved %d entries', self._path, len(self._data))
        except Exception:
            logger.exception('[DiskCache:%s] save failed', self._path)

    def flush(self):

        if self._save_cb is None:
            return
        cancelCallbackSafe(self._save_cb)
        self._save_cb = None
        self._do_save(self._save_rev)

    def fini(self):
        cancelCallbackSafe(self._save_cb)
        self._save_cb = None


    def get(self, key):
        entry = self._data.get(key)
        if entry is None:
            return None
        if self._lifetime > 0 and (time.time() - entry.get('ts', 0)) > self._lifetime:
            return None
        return entry.get('payload')

    def set(self, key, payload):
        self._data[key] = {'payload': payload, 'ts': time.time()}
        self.save()

    def has(self, key):
        return self.get(key) is not None

    def discard(self, key):
        if key in self._data:
            del self._data[key]
            self.save()

    def clear(self):
        if not self._data:
            return
        self._data = {}
        self.save()

    def __len__(self):
        return len(self._data)
