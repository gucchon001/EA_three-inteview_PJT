from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/healthz", include_in_schema=False)
@router.get("/health", include_in_schema=False)
def healthz() -> JSONResponse:
    return JSONResponse(
        {"status": "ok"},
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        },
    )
