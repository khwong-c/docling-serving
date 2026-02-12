import asyncio
import contextvars
import datetime
import functools
import signal
from asyncio import events
from concurrent.futures.thread import ThreadPoolExecutor

from redis import Redis
from rq import Queue, SimpleWorker
from rq.job import JobStatus as RQJobStatus, Job as RQJob
from rq.results import Result as RQResult
from rq.timeouts import TimerDeathPenalty
from rq.utils import now
from rq.worker import BaseWorker

from docling_serving.api.models.request import ConvertRequest
from docling_serving.api.models.response import ConvertResponse
from docling_serving.settings import docling_serve_settings
from docling_serving.workers.convert import convert_with_exception
from docling_serving.workers.work_queue import PQueue, JobStatus, Job


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

    COMPLETED_STATE = {JobStatus.COMPLETED, JobStatus.FAILED}

    def __init__(self):
        super().__init__()
        self.num_of_workers = docling_serve_settings.concurrent_workers

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
        self.executor = ThreadPoolExecutor()
        self.workers = [
            PatchedSimpleWorker(queues=[self.q])
            for _ in range(self.num_of_workers)
        ]
        self.done = asyncio.Event()
        self.worker_tasks: list[asyncio.Task] = []

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

        if job.status not in self.COMPLETED_STATE:
            return job

        if not cleanup:
            return job
        completed_for = datetime.datetime.now(datetime.UTC) - (
                job.complete_time or job.create_time
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

    async def clear_completed(self, older_than: int):
        all_ids = self.q.finished_job_registry.get_job_ids(cleanup=False) + \
                  self.q.canceled_job_registry.get_job_ids(cleanup=False) + \
                  self.q.failed_job_registry.get_job_ids(cleanup=False)
        for job_id in all_ids:
            job = self.q.fetch_job(job_id)
            if job is None:
                continue

            if self.STATUS_MAP[job.get_status(False)] not in self.COMPLETED_STATE:
                continue

            completed_for = datetime.datetime.now(datetime.UTC) - (
                    job.ended_at or job.started_at or job.created_at
            )
            expired = completed_for.total_seconds() > older_than
            if self.clean_after_retrieve or expired:
                self.q.remove(job.id)
                RQResult.delete_all(job)
                job.delete()

    async def shutdown(self):
        if len(self.worker_tasks) == 0:
            return
        for task, worker in zip(self.worker_tasks, self.workers):
            worker.request_stop(signal.SIGINT, None)
            worker.teardown()
            task.cancel()
        await asyncio.gather(
            *self.worker_tasks,
            return_exceptions=True,
        )
        self.executor.shutdown(wait=True)

    async def start_worker(self):
        async def to_thread(func, *args, **kwargs):
            loop = events.get_running_loop()
            ctx = contextvars.copy_context()
            func_call = functools.partial(ctx.run, func, *args, **kwargs)
            return await loop.run_in_executor(self.executor, func_call)

        self.worker_tasks = [
            asyncio.create_task(
                to_thread(worker.work)
            )
            for worker in self.workers
        ]


class PatchedSimpleWorker(SimpleWorker):
    def _install_signal_handlers(self):
        return

    def request_stop(self, signum, frame):
        try:
            self._shutdown_requested_date = now()
            self.handle_warm_shutdown_request()
            self._shutdown()
        except BaseException:
            pass


BaseWorker.death_penalty_class = TimerDeathPenalty
