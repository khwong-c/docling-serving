import asyncio
import datetime
import signal

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
