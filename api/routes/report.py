"""Report API routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/")
async def list_reports():
    return {"reports": []}


@router.get("/{report_id}")
async def get_report(report_id: str):
    return {"report_id": report_id, "status": "not_implemented"}
