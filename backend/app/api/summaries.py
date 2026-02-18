from fastapi import APIRouter, HTTPException

from app.api import crud
from app.models.pydantic import (
    SummaryPayloadSchema,
    SummaryResponseSchema,
    SummaryUpdatePayloadSchema,
)

router = APIRouter()


@router.post("/", response_model=SummaryResponseSchema, status_code=201)
async def create_summary(payload: SummaryPayloadSchema):
    """
    Create a new text summary.

    - **url**: The URL to summarize (must be valid HTTP/HTTPS URL)
    """
    summary_id = await crud.create_summary(payload)
    summary = await crud.get_summary(summary_id)
    return SummaryResponseSchema(
        id=summary.id,
        url=str(summary.url),
        summary=summary.summary,
    )

@router.get("/{id}/", response_model=SummaryResponseSchema)
async def read_summary(id: int):
    """
    Get a summary by ID.

    - **id**: The unique identifier of the summary
    """
    summary = await crud.get_summary(id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return SummaryResponseSchema(
        id=summary.id,
        url=str(summary.url),
        summary=summary.summary,
    )


@router.get("/", response_model=list[SummaryResponseSchema])
async def read_all_summaries():
    """Get all summaries."""
    summaries = await crud.get_all_summaries()
    return [
        SummaryResponseSchema(
            id=s.id,
            url=str(s.url),
            summary=s.summary,
        )
        for s in summaries
    ]


@router.put("/{id}/", response_model=SummaryResponseSchema)
async def update_summary(id: int, payload: SummaryUpdatePayloadSchema):
    """
    Update a summary.

    - **id**: The unique identifier of the summary
    - **url**: New URL value
    - **summary**: New summary text (optional)
    """
    summary = await crud.update_summary(id, str(payload.url), payload.summary)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return SummaryResponseSchema(
        id=summary.id,
        url=str(summary.url),
        summary=summary.summary,
    )


@router.delete("/{id}/")
async def delete_summary(id: int):
    """
    Delete a summary.

    - **id**: The unique identifier of the summary to delete
    """
    deleted = await crud.delete_summary(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"id": id, "deleted": True}