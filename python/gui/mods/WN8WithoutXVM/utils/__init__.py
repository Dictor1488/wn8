import json
import logging
import os
import types
import BigWorld
from wg_async import wg_async, AsyncReturn, await_callback

__all__ = [
    'logger',
    'fetch_data_with_retry',
    'cancelCallbackSafe',
    'override',
    'restore_overrides',
    'get_wn8_color',
    'get_winrate_color',
    'get_battles_color',
    'get_format_battles'
]


def cancelCallbackSafe(cbid):

    if cbid is None:
        return False
    try:
        BigWorld.cancelCallback(cbid)
        return True
    except (AttributeError, ValueError, TypeError):
        return False


logger = logging.getLogger('WN8WithoutXVM')
logger.setLevel(logging.DEBUG if os.path.isfile('.debug_mods') else logging.ERROR)


_overrides = []


def override(holder, name, wrapper=None, setter=None):

    if wrapper is None:
        return lambda w, s=None: override(holder, name, w, s)
    target = getattr(holder, name)
    _overrides.append((holder, name, target))
    wrapped = lambda *a, **kw: wrapper(target, *a, **kw)
    if not isinstance(holder, types.ModuleType) and isinstance(target, types.FunctionType):
        setattr(holder, name, staticmethod(wrapped))
    elif isinstance(target, property):
        prop_getter = lambda *a, **kw: wrapper(target.fget, *a, **kw)
        prop_setter = (lambda *a, **kw: setter(target.fset, *a, **kw)) if setter else target.fset
        setattr(holder, name, property(prop_getter, prop_setter, target.fdel))
    else:
        setattr(holder, name, wrapped)


def restore_overrides():
    while _overrides:
        holder, name, original = _overrides.pop()
        try:
            setattr(holder, name, original)
        except Exception:
            pass


def get_wn8_color(wn8):
    if wn8 <= 0:
        return "#FFFFFF"
    elif wn8 < 600:
        return "#FE0E00"
    elif wn8 < 1100:
        return "#FE7903"
    elif wn8 < 1750:
        return "#F8F400"
    elif wn8 < 2750:
        return "#60FF00"
    elif wn8 < 3750:
        return "#02C9B3"
    else:
        return "#D042F3"


def get_winrate_color(winrate):
    if winrate <= 0:
        return "#FFFFFF"
    if winrate < 46.5:
        return "#FE0E00"
    elif winrate < 49.5:
        return "#FE7903"
    elif winrate < 53.0:
        return "#F8F400"
    elif winrate < 58.5:
        return "#60FF00"
    elif winrate < 64.0:
        return "#02C9B3"
    else:
        return "#D042F3"


def get_battles_color(battles):
    if battles <= 0:
        return "#FFFFFF"
    if battles < 1000:
        return "#FE7903"
    elif battles < 10000:
        return "#F8F400"
    elif battles < 50000:
        return "#60FF00"
    elif battles < 100000:
        return "#02C9B3"
    else:
        return "#D042F3"


def get_format_battles(b):
    if not b:
        return ''
    if b >= 1000000:
        return '%.1fM' % (b / 1000000.0)
    if b >= 1000:
        return '%.1fk' % (b / 1000.0)
    return str(b)

def _internal_fetch(url, headers, timeout, method, postData, callback):
    return BigWorld.fetchURL(
        url,
        callback,
        headers,
        timeout,
        method,
        postData
    )


@wg_async
def fetch_data_with_retry(url, retries=2, delay=5, headers=None, method='GET', postData='', timeout=30.0):
    if headers is None:
        headers = [
            ('Content-Type', 'application/json'),
            ('User-Agent', 'WoT-Stats-Client/1.0')
        ]

    lastError = None

    for attempt in range(1, retries + 1):
        try:
            logger.debug('[Fetch] Attempt %s/%s for URL: %s', attempt, retries, url)

            response = yield await_callback(_internal_fetch)(
                url,
                headers,
                timeout,
                method,
                postData
            )

            if not response:
                lastError = "Empty response object"
                logger.error('[Fetch] Empty response on attempt %s/%s', attempt, retries)

                if attempt < retries:
                    logger.debug('[Fetch] Retrying in %s seconds...', delay)
                    yield _async_sleep(delay)
                    continue

            if hasattr(response, 'body'):
                responseBody = response.body
            elif hasattr(response, 'read'):
                responseBody = response.read()
            else:
                responseBody = str(response)

            if not responseBody:
                lastError = "Empty response body"
                logger.error('[Fetch] Empty response body on attempt %s/%s', attempt, retries)

                if attempt < retries:
                    logger.debug('[Fetch] Retrying in %s seconds...', delay)
                    yield _async_sleep(delay)
                    continue

            try:
                data = json.loads(responseBody)
                logger.debug('[Fetch] Successfully fetched and parsed data on attempt %s/%s',
                             attempt, retries)
                raise AsyncReturn(data)

            except (ValueError, TypeError) as e:
                lastError = "JSON decode error: {}".format(e)
                logger.error('[Fetch] JSON decoding error: %s', e)

                if attempt < retries:
                    logger.debug('[Fetch] Retrying in %s seconds...', delay)
                    yield _async_sleep(delay)
                    continue

        except AsyncReturn:
            raise

        except Exception as e:
            lastError = str(e)
            logger.error('[Fetch] Unexpected error on attempt %s/%s: %s', attempt, retries, e)

            if attempt < retries:
                logger.debug('[Fetch] Retrying in %s seconds...', delay)
                yield _async_sleep(delay)

    logger.error('[Fetch] Failed after %s attempts. Last error: %s', retries, lastError or 'Unknown')
    raise AsyncReturn(None)


@wg_async
def _async_sleep(seconds):
    def dummyCallback():
        pass

    yield await_callback(BigWorld.callback)(seconds, dummyCallback)
