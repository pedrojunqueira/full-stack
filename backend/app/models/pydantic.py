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


class CurrentUserSchema(BaseModel):
    """Current authenticated user from Azure AD token."""
    email: str
    azure_oid: str
    name: str | None = None