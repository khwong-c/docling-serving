import asyncio
import datetime
import uuid
from traceback import TracebackException

from docling_serving.api.models.request import ConvertRequest
from docling_serving.api.models.response import ConvertResponse
from docling_serving.settings import docling_serve_settings
from docling_serving.workers.convert import convert
from docling_serving.workers.work_queue import PQueue, Job, JobStatus, logger


class LocalQueue(PQueue):
    CHECK_INTERVAL = 30
    COMPLETED_STATE = {JobStatus.COMPLETED, JobStatus.FAILED}

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

            if j.status not in self.COMPLETED_STATE:
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

    async def clear_completed(self, older_than: int):
        for job_id, job in self.job_set.items():
            if job.status not in self.COMPLETED_STATE:
                continue
            completed_for = datetime.datetime.now(datetime.UTC) - job.complete_time
            expired = completed_for.total_seconds() > older_than
            if expired:
                self.job_set.pop(job_id)

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
