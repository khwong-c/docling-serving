import logging
import uuid
from abc import abstractmethod
from enum import Enum
from functools import lru_cache
from typing import Protocol
import asyncio

from pydantic import BaseModel

from docling_serving.api.models.request import ConvertRequest
from docling_serving.api.models.response import ConvertResponse
from docling_serving.workers.convert import convert

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.QUEUED
    request: ConvertRequest
    result: ConvertResponse | None = None


class PQueue(Protocol):
    @abstractmethod
    async def get_jobs(self) -> list[Job]:
        raise NotImplementedError

    @abstractmethod
    async def get_job(self, job_id: str) -> Job | None:
        raise NotImplementedError

    @abstractmethod
    async def enqueue_job(self, req: ConvertRequest) -> Job | None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self):
        raise NotImplementedError


class LocalQueue(PQueue):
    def __init__(self):
        self.q: asyncio.Queue[Job] = asyncio.Queue()
        self.job_set: dict[str, Job] = {}
        self.job_lock = asyncio.Lock()

    async def get_jobs(self) -> list[Job]:
        async with self.job_lock:
            return list(self.job_set.values())

    async def get_job(self, job_id: str) -> Job | None:
        async with self.job_lock:
            return self.job_set.get(job_id)

    async def enqueue_job(self, req: ConvertRequest) -> Job | None:
        new_job = Job(
            id=str(uuid.uuid4()),
            request=req,
        )
        async with self.job_lock:
            self.job_set[new_job.id] = new_job
        await self.q.put(new_job)
        return new_job

    async def shutdown(self):
        self.q.shutdown(immediate=False)
        await self.q.join()

    async def start_worker(self):
        while True:
            try:
                job = await self.q.get()
            except asyncio.QueueShutDown:
                break
            except BaseException as e:
                logger.error(str(e))
                self.q.task_done()
                continue
            async with self.job_lock:
                job = self.job_set.get(job.id)
                job.status = JobStatus.PROCESSING
            result = await asyncio.wait_for(
                asyncio.to_thread(convert, job.request),
                timeout=10,
            )
            async with self.job_lock:
                job = self.job_set.get(job.id)
                if job is not None:
                    job.result = ConvertResponse(
                        id=job.id,
                        **result.dict(),
                    )
                    job.status = JobStatus.COMPLETED
            self.q.task_done()


@lru_cache
def create_queue() -> PQueue:
    return LocalQueue()
