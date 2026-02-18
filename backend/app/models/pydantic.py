from pydantic import AnyHttpUrl, BaseModel


class SummaryPayloadSchema(BaseModel):
    url: AnyHttpUrl


class SummaryResponseSchema(BaseModel):
    id: int
    url: str
    summary: str | None = None


class SummaryUpdatePayloadSchema(BaseModel):
    url: AnyHttpUrl
    summary: str | None = None
