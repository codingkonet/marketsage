import time

_store: dict = {}


def cache_get(key: str):
    entry = _store.get(key)
    if entry and time.time() < entry[1]:
        return entry[0]
    _store.pop(key, None)
    return None


def cache_set(key: str, value, ttl: int = 900) -> None:
    _store[key] = (value, time.time() + ttl)
