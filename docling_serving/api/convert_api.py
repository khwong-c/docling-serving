import asyncio

from fastapi import APIRouter, HTTPException, Depends
from docling_serving.api.models.request import ConvertRequest
from docling_serving.api.models.response import ConvertResponse, JobSummary, JobResponse
from .parser import create_summary_from_job
from ..workers.convert import convert
from ..workers.work_queue import create_queue, PQueue, Job, JobStatus

router = APIRouter()


@router.post(
    "/v1/convert",
    tags=["convert"],
    summary="Convert Document",
    response_model_by_alias=True,
)
async def convert_handler(
        req: ConvertRequest,
        queue: PQueue = Depends(create_queue),
) -> JobResponse:
    j = await queue.enqueue_job(req)
    work_id = j.id
    while (j := await queue.get_job(work_id, cleanup=True)).status not in (JobStatus.COMPLETED, JobStatus.FAILED):
        await asyncio.sleep(1.0)
    return JobResponse(
        **create_summary_from_job(j).model_dump(),
        create_time=j.create_time,
        complete_time=j.complete_time,
        duration=(j.complete_time - j.create_time).total_seconds() if j.complete_time else 0.0,
        result=j.result,
    )


@router.post(
    "/v1/convert/async",
    tags=["convert"],
    summary="Convert Document in Async manner",
    response_model_by_alias=True,
)
async def convert_async_handler(
        req: ConvertRequest,
        queue: PQueue = Depends(create_queue),
) -> JobSummary:
    j = await queue.enqueue_job(req)
    return create_summary_from_job(j)
