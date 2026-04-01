"""
Address autocomplete with swappable providers.

Current: Photon (Komoot) — free, no API key.
Future: Google Places API can be added as another provider.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AddressSuggestion:
    display: str
    lat: float
    lon: float
    zipcode: str | None = None


class AutocompleteProvider(Protocol):
    async def suggest(self, query: str, limit: int = 5) -> list[AddressSuggestion]: ...


class PhotonProvider:
    """Komoot Photon geocoder — free, OSM-based, no API key required."""

    BASE_URL = "https://photon.komoot.io/api"

    async def suggest(self, query: str, limit: int = 5) -> list[AddressSuggestion]:
        if not query or len(query) < 3:
            return []

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                headers={"User-Agent": "BuildingStockEnergyEstimation/1.0"},
            ) as client:
                resp = await client.get(
                    self.BASE_URL,
                    params={
                        "q": query,
                        "limit": limit * 3,
                        "lang": "en",
                        "lat": 39.8,
                        "lon": -98.6,
                    },
                )
            if resp.status_code != 200:
                logger.warning("Photon API error: %d", resp.status_code)
                return []

            return self._parse_response(resp.json(), limit)
        except httpx.TimeoutException:
            logger.warning("Photon request timed out")
            return []
        except httpx.HTTPError:
            logger.exception("Photon request failed")
            return []

    def _parse_response(self, data: dict, limit: int = 5) -> list[AddressSuggestion]:
        us_results = []
        other_results = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue

            display = self._format_display(props)
            if not display:
                continue

            suggestion = AddressSuggestion(
                display=display,
                lat=coords[1],
                lon=coords[0],
                zipcode=props.get("postcode"),
            )

            if props.get("countrycode", "").upper() == "US":
                us_results.append(suggestion)
            else:
                other_results.append(suggestion)

        return (us_results + other_results)[:limit]

    @staticmethod
    def _format_display(props: dict) -> str:
        parts = []
        housenumber = props.get("housenumber")
        street = props.get("street")
        if housenumber and street:
            parts.append(f"{housenumber} {street}")
        elif street:
            parts.append(street)
        elif props.get("name"):
            parts.append(props["name"])
        else:
            return ""

        city = props.get("city")
        if city:
            parts.append(city)

        state = props.get("state")
        postcode = props.get("postcode")
        if state and postcode:
            parts.append(f"{state} {postcode}")
        elif state:
            parts.append(state)

        return ", ".join(parts)
