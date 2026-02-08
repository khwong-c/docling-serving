import asyncio

from fastapi import APIRouter, Path, Query, Depends, HTTPException
from pydantic import Field, StrictStr, BaseModel
from typing import Optional
from typing_extensions import Annotated

from .models.response import JobResponse, JobSummary
from .parser import create_summary_from_job
from .dependencies import create_queue
from ..workers.work_queue import PQueue, JobStatus

router = APIRouter()


class ClearCompletedResponse(BaseModel):
    msg: str = "Completed jobs cleared successfully"


@router.get(
    "/v1/status/poll/{task_id}",
    tags=["tasks"],
    summary="Task Status Poll",
    response_model_by_alias=True,
)
async def poll_status_handler(
        task_id: StrictStr = Path(..., description=""),
        wait: Annotated[Optional[int], Field(
            description="Number of seconds to wait for a completed status.")
        ] = Query(0,
                  description="Number of seconds to wait for a completed status.",
                  alias="wait"),
        queue: PQueue = Depends(create_queue),
) -> JobSummary:
    job = None
    for i in range(wait + 1):
        job = await queue.get_job(task_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            return create_summary_from_job(job)
        await asyncio.sleep(1)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return create_summary_from_job(job)


@router.get(
    "/v1/result/{job_id}",
    tags=["tasks"],
    summary="Job Result",
    response_model_by_alias=True,
)
async def fetch_result_handler(
        job_id: str,
        queue: PQueue = Depends(create_queue),
) -> JobResponse:
    job = await queue.get_job(job_id, cleanup=True)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(
        **create_summary_from_job(job).model_dump(),
        result=job.result,
        exception=job.exception,
        create_time=job.create_time,
        complete_time=job.complete_time,
        duration=(job.complete_time - job.create_time).total_seconds() if job.complete_time else 0.0,
    )


@router.get(
    "/v1/jobs",
    tags=["tasks"],
    summary="Job List",
    response_model_by_alias=True,
)
async def job_list_handler(
        queue: PQueue = Depends(create_queue),
) -> list[JobSummary]:
    jobs = await queue.get_jobs()
    return [create_summary_from_job(job) for job in jobs]


@router.delete(
    "/v1/completed",
    tags=["tasks"],
    summary="Clear Completed Jobs",
    response_model_by_alias=True,
)
async def clear_completed(
        older_than: Annotated[Optional[int], Field(
            description="Number of seconds considered as expired to be cleared.")
        ] = Query(3600,
                  description="Number of seconds considered as expired to be cleared.",
                  alias="older_than"),
        queue: PQueue = Depends(create_queue),
) -> ClearCompletedResponse:
    await queue.clear_completed(older_than)
    return ClearCompletedResponse()
