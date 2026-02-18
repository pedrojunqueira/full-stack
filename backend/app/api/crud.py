from app.models.pydantic import SummaryPayloadSchema
from app.models.tortoise import TextSummary


async def create_summary(payload: SummaryPayloadSchema) -> int:
    """Create a new summary and return its ID."""
    summary = await TextSummary.create(url=str(payload.url))
    return summary.id


async def get_summary(id: int) -> TextSummary | None:
    """Get a summary by ID."""
    return await TextSummary.filter(id=id).first()


async def get_all_summaries() -> list[TextSummary]:
    """Get all summaries."""
    return await TextSummary.all()


async def update_summary(
    id: int, url: str, summary: str | None = None
) -> TextSummary | None:
    """Update a summary and return the updated object."""
    summary_obj = await TextSummary.filter(id=id).first()
    if summary_obj:
        summary_obj.url = url
        if summary is not None:
            summary_obj.summary = summary
        await summary_obj.save()
    return summary_obj


async def delete_summary(id: int) -> bool:
    """Delete a summary. Returns True if deleted."""
    deleted_count = await TextSummary.filter(id=id).delete()
    return deleted_count > 0