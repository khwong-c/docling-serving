from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get(
    "/v1/clear/converters",
    tags=["clear"],
    summary="Clear Converters",
    response_model_by_alias=True,
)
async def clear_converters_v1_clear_converters_get() -> str:
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get(
    "/v1/clear/results",
    tags=["clear"],
    summary="Clear Results",
    response_model_by_alias=True,
)
async def clear_results_v1_clear_results_get(
        older_then: float = 3600,
) -> str:
    raise HTTPException(status_code=501, detail="Not implemented")
