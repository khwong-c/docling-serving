from fastapi import APIRouter, HTTPException, Depends
from docling_serving.api.models.request import ConvertRequest
from docling_serving.api.models.response import ConvertResponse
from ..workers.convert import convert
from ..workers.work_queue import create_queue, PQueue, Job

router = APIRouter()


@router.post(
    "/v1/convert",
    tags=["convert"],
    # response_model=ConvertDocumentResponse | PresignedUrlConvertDocumentResponse,
    # responses={
    #     200: {
    #         "content": {"application/zip": {}},
    #     }
    # },
    response_model_by_alias=True,
)
async def process_url_v1_convert_source_post(
        req: ConvertRequest,
) -> ConvertResponse:
    return convert(req)


@router.post(
    "/v1/convert/async",
    tags=["convert"],
    # response_model=TaskStatusResponse,
    summary="Process Url Async",
    response_model_by_alias=True,
)
async def process_url_async_v1_convert_source_async_post(
        req: ConvertRequest,
        queue: PQueue = Depends(create_queue),
) -> Job:
    j = await queue.enqueue_job(req)
    return j
