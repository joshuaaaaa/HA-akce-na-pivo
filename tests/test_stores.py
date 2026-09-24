"""Pobočky z OpenStreetMap – záložní dotaz, když Overpass nestihne dotaz podle území státu."""

import asyncio

import pytest

pytest.importorskip("aiohttp")

from custom_components.akce_na_pivo import stores  # noqa: E402


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self._payload, self._error = payload, error

    async def __aenter__(self):
        if self._error:
            raise self._error
        return self

    async def __aexit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    async def json(self, content_type=None):
        return self._payload


class FakeSession:
    """Dotaz s area(...) vždy vyprší, dotaz jen podle okruhu uspěje."""

    def __init__(self):
        self.queries = []

    def post(self, url, data, headers, timeout):
        self.queries.append((url, data["data"]))
        if "area(" in data["data"]:
            return FakeResponse(error=asyncio.TimeoutError())
        return FakeResponse(
            {
                "elements": [
                    {
                        "type": "node",
                        "id": 1,
                        "lat": 50.09,
                        "lon": 14.45,
                        "tags": {"shop": "supermarket", "brand": "Lidl"},
                    },
                    # Německo (uvnitř hrubého obdélníku ČR, ale addr:country=DE)
                    {
                        "type": "node",
                        "id": 2,
                        "lat": 50.9,
                        "lon": 14.8,
                        "tags": {"shop": "supermarket", "brand": "Lidl", "addr:country": "DE"},
                    },
                    # Vídeň – mimo obdélník ČR
                    {
                        "type": "node",
                        "id": 3,
                        "lat": 48.2,
                        "lon": 16.37,
                        "tags": {"shop": "supermarket", "brand": "Billa"},
                    },
                ]
            }
        )


async def test_fallback_when_area_query_times_out():
    session = FakeSession()
    result = await stores.fetch_stores(session, 50.08, 14.42, 15, "CZ")
    assert [s["osm_id"] for s in result] == ["node/1"]
    area_queries = [q for _, q in session.queries if "area(" in q]
    assert len(area_queries) == len(stores.OVERPASS_URLS)  # všechny servery zkusily přesný dotaz
    assert "area(" not in session.queries[-1][1]


async def test_error_message_is_readable():
    class Broken(FakeSession):
        def post(self, url, data, headers, timeout):
            return FakeResponse(error=asyncio.TimeoutError())

    with pytest.raises(RuntimeError, match="časový limit vypršel"):
        await stores.fetch_stores(Broken(), 50.08, 14.42, 15, "CZ")
