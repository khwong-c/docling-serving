import logging
import uuid
from abc import abstractmethod
import datetime
from enum import Enum
from functools import lru_cache
from traceback import TracebackException
from typing import Protocol
import asyncio
import signal

from redis import Redis
from rq import Queue
from rq.job import Job as RQJob, JobStatus as RQJobStatus
from rq.results import Result as RQResult
from pydantic import BaseModel

from .worker_rq_patch import PatchedSimpleWorker
from ..api.models.request import ConvertRequest
from ..api.models.response import ConvertResponse
from ..settings import docling_serve_settings, AsyncEngine
from .convert import convert, convert_with_exception

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.QUEUED
    request: ConvertRequest | None = None
    result: ConvertResponse | None = None
    exception: str | None = None
    create_time: datetime.datetime | None = None
    complete_time: datetime.datetime | None = None


class PQueue(Protocol):
    @abstractmethod
    async def get_jobs(self) -> list[Job]:
        raise NotImplementedError

    @abstractmethod
    async def get_job(self, job_id: str, cleanup: bool = False) -> Job | None:
        raise NotImplementedError

    @abstractmethod
    async def enqueue_job(self, req: ConvertRequest) -> Job | None:
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self):
        raise NotImplementedError

    @abstractmethod
    async def start_worker(self):
        raise NotImplementedError


class LocalQueue(PQueue):
    CHECK_INTERVAL = 30

    def __init__(self):
        self.q: asyncio.Queue[Job] = asyncio.Queue()
        self.job_set: dict[str, Job] = {}
        self.job_lock = asyncio.Lock()

        job_settings = docling_serve_settings.job_settings
        self.clean_after_retrieve = job_settings.clean_after_retrieve
        self.clean_after_interval = job_settings.clean_after_interval
        self.force_clean_after_interval = job_settings.force_clean_after_interval

    async def get_jobs(self) -> list[Job]:
        async with self.job_lock:
            return list(self.job_set.values())

    async def get_job(self, job_id: str, cleanup: bool = False) -> Job | None:
        async with self.job_lock:
            j = self.job_set.get(job_id)
            if j is None:
                return None

            if j.status not in {JobStatus.COMPLETED, JobStatus.FAILED}:
                return j

            if not cleanup:
                return j

            completed_for = datetime.datetime.now(datetime.UTC) - j.complete_time
            expired = completed_for.total_seconds() > self.clean_after_interval
            if self.clean_after_retrieve or expired:
                self.job_set.pop(job_id)

            return j

    async def enqueue_job(self, req: ConvertRequest) -> Job | None:
        if req is None:
            raise ValueError("Request cannot be None")
        new_job = Job(
            id=str(uuid.uuid4()),
            request=req,
            create_time=datetime.datetime.now(datetime.UTC),
        )
        async with self.job_lock:
            self.job_set[new_job.id] = new_job
        await self.q.put(new_job)
        return new_job

    async def shutdown(self):
        self.q.shutdown(immediate=True)
        await self.q.join()

    async def cleanup_routine(self):
        while True:
            await asyncio.sleep(self.CHECK_INTERVAL)
            jobs = await self.get_jobs()
            finished_job = [
                job for job in jobs
                if job.status in {JobStatus.COMPLETED, JobStatus.FAILED}
            ]
            cur_time = datetime.datetime.now(datetime.UTC)
            expired_jobs = [
                job for job in finished_job
                if (cur_time - job.complete_time).total_seconds() > self.force_clean_after_interval
            ]
            async with self.job_lock:
                for job in expired_jobs:
                    self.job_set.pop(job.id)

    async def start_worker(self):
        clean_task = asyncio.create_task(self.cleanup_routine())
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
            result = await asyncio.to_thread(convert, job.request)
            async with self.job_lock:
                job = self.job_set.get(job.id)
                if job is not None:
                    job.complete_time = datetime.datetime.now(datetime.UTC)
                    if isinstance(result, BaseException):
                        job.status = JobStatus.FAILED
                        job.exception = "\n".join(TracebackException.from_exception(result).format())
                    else:
                        job.result = ConvertResponse(
                            id=job.id,
                            **result.dict(),
                        )
                        job.status = JobStatus.COMPLETED
            self.q.task_done()
        clean_task.cancel()


class RQQueue(PQueue):
    CHECK_INTERVAL = 30

    STATUS_MAP: dict[RQJobStatus, JobStatus] = {
        RQJobStatus.CREATED: JobStatus.QUEUED,
        RQJobStatus.QUEUED: JobStatus.QUEUED,
        RQJobStatus.SCHEDULED: JobStatus.QUEUED,
        RQJobStatus.DEFERRED: JobStatus.QUEUED,
        RQJobStatus.FINISHED: JobStatus.COMPLETED,
        RQJobStatus.STARTED: JobStatus.PROCESSING,
        RQJobStatus.FAILED: JobStatus.FAILED,
        RQJobStatus.STOPPED: JobStatus.FAILED,
        RQJobStatus.CANCELED: JobStatus.FAILED,
    }

    def __init__(self):
        super().__init__()
        job_settings = docling_serve_settings.job_settings
        self.clean_after_retrieve = job_settings.clean_after_retrieve
        self.clean_after_interval = job_settings.clean_after_interval
        self.force_clean_after_interval = job_settings.force_clean_after_interval

        settings = docling_serve_settings.rq_settings
        self.redis = Redis(
            host=settings.host,
            port=settings.port,
            db=settings.db,
            password=settings.password,
        )
        self.q = Queue(settings.queue_name, connection=self.redis)
        self.worker = PatchedSimpleWorker(queues=[self.q])
        self.done = asyncio.Event()
        self.worker_task: asyncio.Task | None = None

    async def get_jobs(self) -> list[Job]:
        all_ids = self.q.get_job_ids() + self.q.deferred_job_registry.get_job_ids(cleanup=False) + \
                  self.q.started_job_registry.get_job_ids(cleanup=False) + \
                  self.q.finished_job_registry.get_job_ids(cleanup=False) + \
                  self.q.canceled_job_registry.get_job_ids(cleanup=False) + \
                  self.q.failed_job_registry.get_job_ids(cleanup=False)

        return [
            Job(
                id=job_id,
                status=self.STATUS_MAP[RQJob(job_id, connection=self.redis).get_status(True)],
            )
            for job_id in all_ids
        ]

    async def get_job(self, job_id: str, cleanup: bool = False) -> Job | None:
        j = self.q.fetch_job(job_id)
        if j is None:
            return None
        job = Job(
            id=j.id,
            status=(status := self.STATUS_MAP[j.get_status(False)]),
            request=j.args[0],
            result=ConvertResponse(
                id=j.id,
                **return_result.dict(),
            ) if (return_result := j.return_value(False)) is not None else None,
            exception=j.latest_result().exc_string if status == JobStatus.FAILED else None,
            create_time=j.created_at,
            complete_time=j.ended_at,
        )

        if job.status not in {JobStatus.COMPLETED, JobStatus.FAILED}:
            return job

        if not cleanup:
            return job
        completed_for = datetime.datetime.now(datetime.UTC) - (
            job.complete_time if job.complete_time is not None else job.create_time
        )
        expired = completed_for.total_seconds() > self.clean_after_interval
        if self.clean_after_retrieve or expired:
            self.q.remove(job.id)
            RQResult.delete_all(j)
            j.delete()

        return job

    async def enqueue_job(self, req: ConvertRequest) -> Job | None:
        if req is None:
            raise ValueError("Request cannot be None")
        new_job = self.q.create_job(
            convert_with_exception, args=(req,),
            result_ttl=self.force_clean_after_interval,
            failure_ttl=self.force_clean_after_interval,
        )
        self.q.enqueue_job(new_job)
        return Job(
            id=new_job.id,
            status=JobStatus.QUEUED,
            request=req,
            create_time=new_job.created_at,
        )

    async def shutdown(self):
        if self.worker_task is None:
            return
        self.worker.request_stop(signal.SIGINT, None)
        self.worker.teardown()
        self.worker_task.cancel()
        await asyncio.wait(
            [self.worker_task],
            return_when=asyncio.FIRST_EXCEPTION,
        )

    async def start_worker(self):
        self.worker_task = asyncio.create_task(
            asyncio.to_thread(self.worker.work)
        )


@lru_cache
def create_queue() -> PQueue:
    if docling_serve_settings.async_engine == AsyncEngine.LOCAL:
        return LocalQueue()
    elif docling_serve_settings.async_engine == AsyncEngine.RQ:
        return RQQueue()
    else:
        raise ValueError(f"Unsupported async engine: {docling_serve_settings.async_engine}")
