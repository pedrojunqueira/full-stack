import pytest


# ============== CREATE ==============

@pytest.mark.asyncio
async def test_create_summary(client):
    """Test creating a new summary."""
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    assert response.status_code == 201
    assert response.json()["url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_create_summary_invalid_json(client):
    """Test that missing URL returns 422."""
    response = await client.post(
        "/summaries/",
        json={},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_summary_invalid_url(client):
    """Test that invalid URL returns 422."""
    response = await client.post(
        "/summaries/",
        json={"url": "not-a-valid-url"},
    )
    assert response.status_code == 422


# ============== READ ==============

@pytest.mark.asyncio
async def test_read_summary(client):
    """Test reading a single summary."""
    # Create a summary first
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    summary_id = response.json()["id"]

    # Read it back
    response = await client.get(f"/summaries/{summary_id}/")
    assert response.status_code == 200
    assert response.json()["id"] == summary_id
    assert response.json()["url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_read_summary_not_found(client):
    """Test that non-existent ID returns 404."""
    response = await client.get("/summaries/99999/")
    assert response.status_code == 404
    assert response.json()["detail"] == "Summary not found"


@pytest.mark.asyncio
async def test_read_all_summaries(client):
    """Test reading all summaries."""
    # Create some summaries
    await client.post("/summaries/", json={"url": "https://example1.com"})
    await client.post("/summaries/", json={"url": "https://example2.com"})

    response = await client.get("/summaries/")
    assert response.status_code == 200
    assert len(response.json()) >= 2


# ============== UPDATE ==============

@pytest.mark.asyncio
async def test_update_summary(client):
    """Test updating a summary."""
    # Create
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    summary_id = response.json()["id"]

    # Update
    response = await client.put(
        f"/summaries/{summary_id}/",
        json={"url": "https://updated.com", "summary": "Updated summary text"},
    )
    assert response.status_code == 200
    assert response.json()["url"] == "https://updated.com/"
    assert response.json()["summary"] == "Updated summary text"


@pytest.mark.asyncio
async def test_update_summary_not_found(client):
    """Test updating non-existent summary returns 404."""
    response = await client.put(
        "/summaries/99999/",
        json={"url": "https://example.com", "summary": "test"},
    )
    assert response.status_code == 404


# ============== DELETE ==============

@pytest.mark.asyncio
async def test_delete_summary(client):
    """Test deleting a summary."""
    # Create
    response = await client.post(
        "/summaries/",
        json={"url": "https://example.com"},
    )
    summary_id = response.json()["id"]

    # Delete
    response = await client.delete(f"/summaries/{summary_id}/")
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    # Verify deleted
    response = await client.get(f"/summaries/{summary_id}/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_summary_not_found(client):
    """Test deleting non-existent summary returns 404."""
    response = await client.delete("/summaries/99999/")
    assert response.status_code == 404

