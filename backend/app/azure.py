"""
Azure AD authentication scheme configuration.
"""

from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer

from app.config import get_settings

settings = get_settings()

# Only configure if Azure AD is enabled
if settings.is_auth_enabled:
    azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
        app_client_id=settings.app_client_id,
        tenant_id=settings.tenant_id,
        scopes={
            f"api://{settings.app_client_id}/{settings.scope_description}": settings.scope_description,
        },
        allow_guest_users=True,
    )
else:
    # For local development without Azure AD
    azure_scheme = None