# coding: utf-8
import asyncio

from fastapi import APIRouter, Path, Query, Depends, HTTPException
from pydantic import Field, StrictFloat, StrictInt, StrictStr
from typing import Optional, Union
from typing_extensions import Annotated

from docling_serving.api.models.response import JobResponse, ConversionStatus, JobSummary
from docling_serving.api.parser import create_summary_from_job
from docling_serving.workers.work_queue import PQueue, create_queue, JobStatus, Job

router = APIRouter()


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
