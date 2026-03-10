"""
Tests for authentication functionality.
"""

import pytest


@pytest.mark.asyncio
async def test_protected_endpoint_with_auth(client):
    """Test that authenticated requests succeed."""
    response = await client.get("/summaries/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_summary_with_auth(client):
    """Test creating a summary as authenticated user."""
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    assert response.status_code == 201
    assert response.json()["url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_ping_no_auth_required(client):
    """Test that health check doesn't require auth."""
    response = await client.get("/ping")
    assert response.status_code == 200
    assert response.json()["ping"] == "🏓"