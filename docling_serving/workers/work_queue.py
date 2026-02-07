import logging
from abc import abstractmethod
import datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel

from ..api.models.request import ConvertRequest
from ..api.models.response import ConvertResponse

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


