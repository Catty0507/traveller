import asyncio
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable


class TTLCache:
    """内存 TTL + LRU 缓存。

    同一 key 并发未命中时只放行一个协程执行工厂函数(防惊群),
    不同 key 之间互不阻塞。
    """

    def __init__(self, maxsize: int = 500, ttl: float = 300.0):
        self._maxsize = maxsize
        self._ttl = ttl
        self._data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._key_locks: dict[Any, asyncio.Lock] = {}

    def _get_valid(self, key: Any) -> Any:
        item = self._data.get(key)
        if item is None:
            return None
        ts, value = item
        if time.monotonic() - ts > self._ttl:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def _set(self, key: Any, value: Any) -> None:
        self._data[key] = (time.monotonic(), value)
        self._data.move_to_end(key)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    async def get_or_set(self, key: Any, factory: Callable[[], Awaitable[Any]]) -> Any:
        value = self._get_valid(key)
        if value is not None:
            return value

        lock = self._key_locks.setdefault(key, asyncio.Lock())
        async with lock:
            value = self._get_valid(key)  # 双重检查:可能已被前一个协程填充
            if value is not None:
                return value
            value = await factory()
            self._set(key, value)
        self._key_locks.pop(key, None)
        return value
