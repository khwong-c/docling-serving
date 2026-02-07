# coding: utf-8

from fastapi import APIRouter, Path, Query, Depends, HTTPException
from pydantic import Field, StrictFloat, StrictInt, StrictStr
from typing import Optional, Union
from typing_extensions import Annotated

from docling_serve.datamodel.responses import TaskStatusResponse
from docling_serving.api.models.response import JobResponse, ConversionStatus, JobSummary
from docling_serving.workers.work_queue import PQueue, create_queue, JobStatus

router = APIRouter()


@router.get(
    "/v1/status/poll/{task_id}",
    tags=["tasks"],
    response_model=TaskStatusResponse,
    summary="Task Status Poll",
    response_model_by_alias=True,
)
async def task_status_poll_v1_status_poll_task_id_get(
        task_id: StrictStr = Path(..., description=""),
        wait: Annotated[Optional[Union[StrictFloat, StrictInt]], Field(
            description="Number of seconds to wait for a completed status.")
        ] = Query(0.0,
                  description="Number of seconds to wait for a completed status.",
                  alias="wait"),
) -> TaskStatusResponse:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get(
    "/v1/result/{job_id}",
    tags=["tasks"],
    summary="Task Result",
    response_model_by_alias=True,
)
async def task_result_v1_result_task_id_get(
        job_id: str,
        queue: PQueue = Depends(create_queue),
) -> JobResponse:
    job = await queue.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    status_map = {
        JobStatus.QUEUED: ConversionStatus.PENDING,
        JobStatus.PROCESSING: ConversionStatus.STARTED,
        JobStatus.COMPLETED: ConversionStatus.SUCCESS,
        JobStatus.FAILED: ConversionStatus.FAILURE,
    }
    return JobResponse(
        id=job.id,
        status=status_map[job.status],
        result=job.result,
    )


@router.get(
    "/v1/jobs",
    tags=["tasks"],
    summary="Task List",
    response_model_by_alias=True,
)
async def task_jobs_list(
        queue: PQueue = Depends(create_queue),
) -> list[JobSummary]:
    jobs = await queue.get_jobs()
    status_map = {
        JobStatus.QUEUED: ConversionStatus.PENDING,
        JobStatus.PROCESSING: ConversionStatus.STARTED,
        JobStatus.COMPLETED: ConversionStatus.SUCCESS,
        JobStatus.FAILED: ConversionStatus.FAILURE,
    }
    return [
        JobSummary(
            id=job.id,
            status=status_map[job.status],
        )
        for job in jobs
    ]
