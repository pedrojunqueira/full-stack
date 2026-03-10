"""
Authentication and authorization using fastapi-azure-auth.
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security

from app.azure import azure_scheme
from app.models.pydantic import CurrentUserSchema

logger = logging.getLogger(__name__)


class AzureUserClaims:
    """
    Parsed Azure user claims from JWT token.

    Common claims:
    - preferred_username: User's email/UPN
    - oid: Object ID (unique user identifier in Azure AD)
    - name: Display name
    - roles: App roles assigned to user
    """

    def __init__(self, claims: dict):
        self.email = (
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("upn")
        )
        self.azure_oid = claims.get("oid")
        self.name = claims.get("name")
        self.roles = claims.get("roles", [])

    def is_valid(self) -> bool:
        """Check if required claims are present."""
        return bool(self.email and self.azure_oid)


async def get_azure_user(
    azure_user: Annotated[object, Security(azure_scheme)],
) -> object:
    """
    Get the raw Azure user from the validated token.

    This is a separate dependency to allow easy mocking in tests.
    The azure_scheme automatically:
    - Validates the JWT signature
    - Checks token expiration
    - Verifies the audience and issuer
    """
    return azure_user


def parse_azure_claims(azure_user: object) -> AzureUserClaims:
    """Parse Azure user claims from the token."""
    if azure_user is None:
        raise HTTPException(
            status_code=500,
            detail="Authentication scheme not configured"
        )
    return AzureUserClaims(azure_user.claims)


async def get_current_user(
    azure_user: Annotated[object, Depends(get_azure_user)],
) -> CurrentUserSchema:
    """
    Get current authenticated user from Azure token.

    Returns a simplified user object with:
    - email: User's email address
    - azure_oid: Unique Azure AD identifier
    - name: Display name
    """
    claims = parse_azure_claims(azure_user)

    if not claims.is_valid():
        raise HTTPException(
            status_code=401,
            detail="Invalid token: missing required claims (email or oid)"
        )

    logger.info(f"User authenticated: {claims.email}")

    return CurrentUserSchema(
        email=claims.email,
        azure_oid=claims.azure_oid,
        name=claims.name,
    )