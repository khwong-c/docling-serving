from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get(
    "/health",
    tags=["health"],
    summary="Health",
    response_model_by_alias=True,
)
async def health_health_get(
) -> str:
    return "ok"


@router.get(
    "/version",
    tags=["health"],
    summary="Version Info",
    response_model_by_alias=True,
)
async def version_info_version_get(
) -> dict:
    raise HTTPException(status_code=501, detail="Not implemented")
