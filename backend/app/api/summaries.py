from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api import crud
from app.auth import get_current_user
from app.models.pydantic import (
    CurrentUserSchema,
    SummaryPayloadSchema,
    SummaryResponseSchema,
    SummaryUpdatePayloadSchema,
)

router = APIRouter()


@router.post("/", response_model=SummaryResponseSchema, status_code=201)
async def create_summary(
    payload: SummaryPayloadSchema,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Create a new text summary.

    **Requires authentication.**
    """
    summary_id = await crud.create_summary(payload)
    summary = await crud.get_summary(summary_id)
    return SummaryResponseSchema(
        id=summary.id,
        url=str(summary.url),
        summary=summary.summary,
    )


@router.get("/{id}/", response_model=SummaryResponseSchema)
async def read_summary(
    id: int,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Get a summary by ID.

    **Requires authentication.**
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
async def read_all_summaries(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Get all summaries.

    **Requires authentication.**
    """
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
async def update_summary(
    id: int,
    payload: SummaryUpdatePayloadSchema,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Update a summary.

    **Requires authentication.**
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
async def delete_summary(
    id: int,
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
):
    """
    Delete a summary.

    **Requires authentication.**
    """
    deleted = await crud.delete_summary(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"id": id, "deleted": True}