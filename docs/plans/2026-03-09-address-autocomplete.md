# Address Autocomplete Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add type-ahead address suggestions using Photon (Komoot), with a provider abstraction so Google Places can be swapped in later.

**Architecture:** Backend `/autocomplete` endpoint proxies to Photon's API, returning normalized suggestions. A `GeocoderProvider` protocol makes the provider swappable. Frontend debounces input and renders a dropdown of suggestions. Selecting a suggestion populates the address field and triggers the existing lookup flow.

**Tech Stack:** Python (httpx for async HTTP), Vue 3 Composition API, TypeScript

---

### Task 1: Backend — Autocomplete Provider Abstraction + Photon Implementation

**Files:**
- Create: `backend/app/services/autocomplete.py`
- Test: `backend/tests/test_autocomplete.py`

**Step 1: Write the failing tests**

```python
# backend/tests/test_autocomplete.py
import pytest
from unittest.mock import patch, AsyncMock
from app.services.autocomplete import PhotonProvider, AddressSuggestion


@pytest.mark.asyncio
async def test_photon_provider_returns_suggestions():
    mock_response = AsyncMock()
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
    mock_response = AsyncMock()
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
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_autocomplete.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.autocomplete'`

**Step 3: Write the implementation**

```python
# backend/app/services/autocomplete.py
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
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self.BASE_URL,
                    params={"q": query, "limit": limit, "lang": "en"},
                )
            if resp.status_code != 200:
                logger.warning("Photon API error: %d", resp.status_code)
                return []

            return self._parse_response(resp.json())
        except httpx.HTTPError:
            logger.exception("Photon request failed")
            return []

    def _parse_response(self, data: dict) -> list[AddressSuggestion]:
        results = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue

            display = self._format_display(props)
            if not display:
                continue

            results.append(
                AddressSuggestion(
                    display=display,
                    lat=coords[1],
                    lon=coords[0],
                    zipcode=props.get("postcode"),
                )
            )
        return results

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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_autocomplete.py -v`
Expected: All 3 PASS

**Step 5: Commit**

```bash
git add backend/app/services/autocomplete.py backend/tests/test_autocomplete.py
git commit -m "feat: add autocomplete provider abstraction with Photon implementation"
```

---

### Task 2: Backend — Add `/autocomplete` API Endpoint

**Files:**
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_autocomplete.py` (append)

**Step 1: Write the failing test**

Append to `backend/tests/test_autocomplete.py`:

```python
from fastapi.testclient import TestClient


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
```

Note: `app_client` fixture should already exist in conftest.py or needs a minimal one — check if there's a `TestClient` fixture.

**Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_autocomplete.py::test_autocomplete_endpoint -v`
Expected: FAIL — 404 (endpoint doesn't exist yet)

**Step 3: Add the endpoint to routes.py**

Add to `backend/app/api/routes.py`:

```python
from app.services.autocomplete import PhotonProvider, AddressSuggestion

# Module-level provider instance — swap this to change providers
autocomplete_provider = PhotonProvider()


@router.get("/autocomplete")
async def autocomplete(q: str = "") -> list[dict]:
    if len(q) < 3:
        return []
    suggestions = await autocomplete_provider.suggest(q, limit=5)
    return [
        {
            "display": s.display,
            "lat": s.lat,
            "lon": s.lon,
            "zipcode": s.zipcode,
        }
        for s in suggestions
    ]
```

Also ensure `conftest.py` has an `app_client` fixture. Check existing fixtures — if not present, add:

```python
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def app_client():
    with TestClient(app) as client:
        yield client
```

**Step 4: Install httpx**

Run: `cd backend && pip install httpx` and add `httpx` to `requirements.txt`

**Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_autocomplete.py -v`
Expected: All 5 PASS

**Step 6: Commit**

```bash
git add backend/app/api/routes.py backend/tests/test_autocomplete.py backend/requirements.txt
git commit -m "feat: add /autocomplete endpoint proxying to Photon"
```

---

### Task 3: Frontend — Address Autocomplete Composable

**Files:**
- Create: `frontend/src/composables/useAddressAutocomplete.ts`
- Modify: `frontend/src/types/lookup.ts` (add suggestion type)

**Step 1: Add the suggestion type**

Append to `frontend/src/types/lookup.ts`:

```typescript
export interface AddressSuggestion {
  display: string
  lat: number
  lon: number
  zipcode: string | null
}
```

**Step 2: Create the composable**

```typescript
// frontend/src/composables/useAddressAutocomplete.ts
import { ref, watch, type Ref } from 'vue'
import type { AddressSuggestion } from '../types/lookup'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function useAddressAutocomplete(query: Ref<string>, debounceMs = 300) {
  const suggestions = ref<AddressSuggestion[]>([])
  const loading = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null
  let abortController: AbortController | null = null

  async function fetchSuggestions(q: string) {
    if (q.length < 3) {
      suggestions.value = []
      return
    }

    // Cancel any in-flight request
    if (abortController) {
      abortController.abort()
    }
    abortController = new AbortController()

    loading.value = true
    try {
      const resp = await fetch(
        `${API_BASE}/autocomplete?q=${encodeURIComponent(q)}`,
        { signal: abortController.signal },
      )
      if (resp.ok) {
        suggestions.value = await resp.json()
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        suggestions.value = []
      }
    } finally {
      loading.value = false
    }
  }

  watch(query, (val) => {
    if (timer) clearTimeout(timer)
    if (val.length < 3) {
      suggestions.value = []
      return
    }
    timer = setTimeout(() => fetchSuggestions(val), debounceMs)
  })

  function clear() {
    suggestions.value = []
  }

  return { suggestions, loading, clear }
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd frontend && npm run type-check`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/types/lookup.ts frontend/src/composables/useAddressAutocomplete.ts
git commit -m "feat: add useAddressAutocomplete composable with debounce and abort"
```

---

### Task 4: Frontend — Update AddressLookup.vue with Autocomplete Dropdown

**Files:**
- Modify: `frontend/src/components/AddressLookup.vue`

**Step 1: Update the component**

Replace `AddressLookup.vue` with the autocomplete-enabled version:

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { PTextInput, PButton } from '@partnerdevops/partner-components'
import type { AddressSuggestion } from '../types/lookup'
import { useAddressAutocomplete } from '../composables/useAddressAutocomplete'

defineProps<{
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  lookup: [address: string]
}>()

const address = ref('')
const showDropdown = ref(false)

const { suggestions, loading: autocompleteLoading } = useAddressAutocomplete(address)

const hasSuggestions = computed(() => suggestions.value.length > 0 && showDropdown.value)

function selectSuggestion(suggestion: AddressSuggestion) {
  address.value = suggestion.display
  showDropdown.value = false
  suggestions.value = []
  emit('lookup', suggestion.display)
}

function onInput() {
  showDropdown.value = true
}

function onLookup() {
  if (address.value.trim()) {
    showDropdown.value = false
    emit('lookup', address.value.trim())
  }
}

function onBlur() {
  // Delay to allow click on suggestion to register
  setTimeout(() => { showDropdown.value = false }, 200)
}

function onFocus() {
  if (suggestions.value.length > 0) {
    showDropdown.value = true
  }
}
</script>

<template>
  <div class="address-lookup">
    <div class="address-lookup__header">
      <p class="address-lookup__label">Building Address</p>
      <p class="address-lookup__desc">Enter an address to auto-populate building details</p>
    </div>
    <form class="address-lookup__form" @submit.prevent="onLookup">
      <div class="address-lookup__input-wrap">
        <PTextInput
          v-model="address"
          placeholder="e.g. 210 N Wells St, Chicago, IL 60606"
          size="medium"
          :disabled="loading"
          @input="onInput"
          @blur="onBlur"
          @focus="onFocus"
        />
        <ul v-if="hasSuggestions" class="address-lookup__suggestions">
          <li
            v-for="(s, i) in suggestions"
            :key="i"
            class="address-lookup__suggestion"
            @mousedown.prevent="selectSuggestion(s)"
          >
            {{ s.display }}
          </li>
        </ul>
        <div v-if="autocompleteLoading && address.length >= 3" class="address-lookup__loading">
          Searching...
        </div>
      </div>
      <PButton
        type="submit"
        variant="secondary"
        size="medium"
        :disabled="loading || !address.trim()"
      >
        {{ loading ? 'Looking up...' : 'Look Up' }}
      </PButton>
    </form>
    <p v-if="error" class="address-lookup__error">{{ error }}</p>
  </div>
</template>

<style scoped>
.address-lookup {
  background-color: var(--app-surface-raised);
  border: 1px solid #e2e6ea;
  border-radius: 6px;
  padding: 1.5rem 2rem;
  margin-bottom: 1.5rem;
}

.address-lookup__header {
  margin-bottom: 1rem;
}

.address-lookup__label {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  color: var(--app-header-bg);
  margin: 0;
}

.address-lookup__desc {
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  color: #6b7a8a;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0.25rem 0 0;
}

.address-lookup__form {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.address-lookup__input-wrap {
  flex: 1;
  position: relative;
}

.address-lookup__suggestions {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 50;
  margin: 0;
  padding: 0;
  list-style: none;
  background: var(--app-surface-raised, #fff);
  border: 1px solid #e2e6ea;
  border-top: none;
  border-radius: 0 0 4px 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  max-height: 220px;
  overflow-y: auto;
}

.address-lookup__suggestion {
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
  color: var(--partner-text-primary, #333e47);
  cursor: pointer;
  border-bottom: 1px solid #f0f2f4;
}

.address-lookup__suggestion:last-child {
  border-bottom: none;
}

.address-lookup__suggestion:hover {
  background-color: var(--partner-surface-hovered, #f4f6f8);
}

.address-lookup__loading {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  color: #6b7a8a;
  background: var(--app-surface-raised, #fff);
  border: 1px solid #e2e6ea;
  border-top: none;
  border-radius: 0 0 4px 4px;
}

.address-lookup__error {
  color: var(--partner-error-main, #dc2626);
  font-size: 0.8125rem;
  margin: 0.5rem 0 0;
}
</style>
```

Key changes from original:
- `@input` triggers `showDropdown = true`
- `@blur` hides dropdown after 200ms delay (allows click to register)
- `@focus` re-shows dropdown if suggestions exist
- `mousedown.prevent` on suggestions prevents blur from firing before click
- Selecting a suggestion auto-triggers the existing `lookup` emit
- `align-items: flex-start` on form so button aligns to top when dropdown appears

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npm run type-check`
Expected: No errors

**Step 3: Run dev server and manually test**

Run: `cd frontend && npm run dev`
Test: Type "210 N Wells" — should see dropdown suggestions appear after ~300ms

**Step 4: Commit**

```bash
git add frontend/src/components/AddressLookup.vue
git commit -m "feat: add autocomplete dropdown to address lookup"
```

---

### Task 5: Keyboard Navigation for Dropdown

**Files:**
- Modify: `frontend/src/components/AddressLookup.vue`

**Step 1: Add keyboard nav to the component script**

Add to the `<script setup>` section:

```typescript
const activeIndex = ref(-1)

// Reset active index when suggestions change
watch(suggestions, () => { activeIndex.value = -1 })

function onKeydown(e: KeyboardEvent) {
  if (!hasSuggestions.value) return

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, suggestions.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (e.key === 'Enter' && activeIndex.value >= 0) {
    e.preventDefault()
    selectSuggestion(suggestions.value[activeIndex.value])
  } else if (e.key === 'Escape') {
    showDropdown.value = false
  }
}
```

**Step 2: Wire up the template**

Add `@keydown="onKeydown"` to the `PTextInput`.

Add `:class="{ 'address-lookup__suggestion--active': i === activeIndex }"` to each `<li>`.

Add CSS:

```css
.address-lookup__suggestion--active {
  background-color: var(--partner-surface-hovered, #f4f6f8);
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd frontend && npm run type-check`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/components/AddressLookup.vue
git commit -m "feat: add keyboard navigation to autocomplete dropdown"
```

---

### Task 6: Integration Smoke Test

**Files:**
- Test: `backend/tests/test_autocomplete.py` (append)

**Step 1: Add an e2e-style test (live Photon, skip in CI)**

```python
@pytest.mark.skipif(
    not pytest.importorskip("httpx"),
    reason="httpx not installed"
)
@pytest.mark.asyncio
async def test_photon_live_integration():
    """Live integration test — hits real Photon API. Run manually."""
    provider = PhotonProvider()
    results = await provider.suggest("Empire State Building, New York")
    assert len(results) > 0
    assert any("New York" in r.display for r in results)
```

Mark with `@pytest.mark.e2e` or `--run-e2e` flag to skip in normal CI runs.

**Step 2: Run it**

Run: `cd backend && pytest tests/test_autocomplete.py::test_photon_live_integration -v`
Expected: PASS (requires network)

**Step 3: Commit**

```bash
git add backend/tests/test_autocomplete.py
git commit -m "test: add live Photon integration smoke test"
```

---

## Future: Swapping to Google Places

To swap providers later, create a `GooglePlacesProvider` implementing the same `AutocompleteProvider` protocol:

```python
class GooglePlacesProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def suggest(self, query: str, limit: int = 5) -> list[AddressSuggestion]:
        # Call Google Places Autocomplete API
        ...
```

Then change one line in `routes.py`:

```python
# autocomplete_provider = PhotonProvider()
autocomplete_provider = GooglePlacesProvider(api_key=os.environ["GOOGLE_PLACES_KEY"])
```

No frontend changes needed.
