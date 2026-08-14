from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
def readiness() -> dict[str, str]:
    return {"status": "ready"}
