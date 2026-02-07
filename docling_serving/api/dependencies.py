from functools import lru_cache

from ..settings import docling_serve_settings, AsyncEngine
from ..workers.work_queue import PQueue
from ..workers.work_queue_local import LocalQueue
from ..workers.work_queue_rq import RQQueue


@lru_cache
def create_queue() -> PQueue:
    if docling_serve_settings.async_engine == AsyncEngine.LOCAL:
        return LocalQueue()
    elif docling_serve_settings.async_engine == AsyncEngine.RQ:
        return RQQueue()
    else:
        raise ValueError(f"Unsupported async engine: {docling_serve_settings.async_engine}")
