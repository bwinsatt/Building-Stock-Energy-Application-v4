import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.autocomplete import PhotonProvider, AddressSuggestion


@pytest.mark.asyncio
async def test_photon_provider_returns_suggestions():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "features": [
            {
                "geometry": {"coordinates": [-87.6354, 41.8867]},
                "properties": {
                    "name": "Willis Tower",
                    "housenumber": "233",
                    "street": "S Wacker Dr",
                    "city": "Chicago",
                    "state": "Illinois",
                    "postcode": "60606",
                    "country": "United States",
                    "countrycode": "US",
                },
            }
        ]
    }

    provider = PhotonProvider()
    with patch("app.services.autocomplete.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        results = await provider.suggest("233 S Wacker")

    assert len(results) == 1
    assert results[0].display == "233 S Wacker Dr, Chicago, Illinois 60606"
    assert results[0].lat == 41.8867
    assert results[0].lon == -87.6354
    assert results[0].zipcode == "60606"


@pytest.mark.asyncio
async def test_photon_provider_empty_query():
    provider = PhotonProvider()
    results = await provider.suggest("")
    assert results == []


@pytest.mark.asyncio
async def test_photon_provider_handles_api_error():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {}

    provider = PhotonProvider()
    with patch("app.services.autocomplete.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        results = await provider.suggest("test")

    assert results == []


def test_autocomplete_endpoint(app_client):
    """Test the /autocomplete endpoint returns suggestions."""
    with patch("app.api.routes.autocomplete_provider.suggest", new_callable=AsyncMock) as mock:
        mock.return_value = [
            AddressSuggestion(
                display="233 S Wacker Dr, Chicago, Illinois 60606",
                lat=41.8867,
                lon=-87.6354,
                zipcode="60606",
            )
        ]
        resp = app_client.get("/autocomplete?q=233+S+Wacker")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["display"] == "233 S Wacker Dr, Chicago, Illinois 60606"
    assert data[0]["lat"] == 41.8867


def test_autocomplete_endpoint_short_query(app_client):
    """Queries under 3 chars return empty list without calling provider."""
    resp = app_client.get("/autocomplete?q=ab")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_photon_live_integration():
    """Live integration test — hits real Photon API. Run with --run-e2e."""
    provider = PhotonProvider()
    results = await provider.suggest("Empire State Building, New York")
    assert len(results) > 0
    assert any("New York" in r.display for r in results)
