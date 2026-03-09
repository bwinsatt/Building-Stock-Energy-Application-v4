# Address Lookup & Auto-Populate Design

## Goal

Minimize manual form inputs by auto-populating building characteristics from a street address. Uses free data sources (OSM, Nominatim) combined with model-based imputation trained on ComStock/ResStock data. Prevents garbage-in/garbage-out by showing confidence levels and keeping all fields editable.

## Architecture

### Address Lookup Pipeline

```
Address input
  -> Nominatim geocode -> lat/lon + parsed address (zipcode, state)
  -> Overpass API (100m radius) -> all nearby building polygons + OSM tags
  -> Match correct building (metadata match -> point-in-polygon -> nearest boundary)
  -> Extract: footprint polygon, building:levels, building type tag, height
  -> Compute: sqft from UTM-projected polygon area x num_stories
  -> Zipcode from address -> climate_zone, state (existing lookup)
  -> Imputation model predicts remaining fields with confidence scores
  -> Return all fields + polygon coords + nearby building polygons
```

### Data Tier Classification

| Tier | Fields | Source | Confidence |
|------|--------|--------|------------|
| A - Direct from public data | zipcode, num_stories, sqft, building_type | Nominatim + Overpass + geometry calc | High (when available) |
| B - Model-imputed | heating_fuel, dhw_fuel, wall_construction, window_type, window_to_wall_ratio, lighting_type, hvac_system_type | XGBoost classifiers on ComStock/ResStock | Medium (with probability scores) |
| C - Manual only | operating_hours | User input | N/A |

### Critical Rule

**Building type is NEVER guessed by the imputation model.** It is only populated from explicit OSM `building` tags. If the tag is `yes` (generic) or missing, the field stays blank for user selection. Building type drives ComStock vs ResStock dataset selection — getting it wrong cascades errors through the entire pipeline.

## Backend

### New Service: `backend/app/services/address_lookup.py`

Ported from existing `OSM_footprint_search.py` in the AutoBEM project (`/Users/brandonwinsatt/Documents/AutoBEM_python_project/`).

**Geocoding (Nominatim):**
- Input: street address string
- Output: lat, lon, parsed address components (zipcode, city, state)
- Library: `geopy.geocoders.Nominatim`

**Footprint Search (Overpass API):**
- Query all `way["building"]` within 100m radius of lat/lon
- Parse OSM JSON response into Shapely polygons with metadata tags
- Match correct building:
  1. Address metadata match (`addr:housenumber`)
  2. Point-in-polygon containment
  3. Nearest boundary fallback

**Data Extraction:**
- `num_stories`: from `building:levels` tag, or estimated from `height` tag / 3.4m
- `sqft`: polygon area projected to UTM (via pyproj) x num_stories, converted m2 -> sqft
- `building_type`: mapped from OSM `building` tag (see mapping table below), left blank if `yes` or unmapped
- `zipcode`: from geocoded address string

**Coordinate Projection:**
- Reuse `latlon_to_cartesian()` from AutoBEM — UTM projection based on first coordinate
- Used for accurate area calculation and for the frontend 3D viewer

### New Endpoint: `GET /lookup?address=...`

**Response schema:**
```json
{
  "address": "210 N Wells St, Chicago, IL 60606",
  "lat": 41.886,
  "lon": -87.634,
  "zipcode": "60606",
  "building_fields": {
    "building_type": {"value": "Office", "source": "osm", "confidence": 1.0},
    "sqft": {"value": 45000, "source": "computed", "confidence": 0.8},
    "num_stories": {"value": 3, "source": "osm", "confidence": 1.0},
    "year_built": {"value": null, "source": null, "confidence": null},
    "heating_fuel": {"value": "NaturalGas", "source": "imputed", "confidence": 0.87},
    "wall_construction": {"value": "Mass", "source": "imputed", "confidence": 0.72},
    "window_type": {"value": "Double, Clear, Metal", "source": "imputed", "confidence": 0.65},
    "lighting_type": {"value": "LED", "source": "imputed", "confidence": 0.58}
  },
  "target_building_polygon": [[lat, lon], ...],
  "nearby_buildings": [
    {"polygon": [[lat, lon], ...], "levels": 2},
    ...
  ]
}
```

**Source values:** `"osm"` (direct from tag), `"computed"` (derived from geometry), `"imputed"` (model prediction), `null` (not available)

### OSM Building Type Mapping

| OSM `building` tag | BuildingInput `building_type` |
|---|---|
| `office` | Office |
| `commercial`, `retail`, `supermarket` | Mercantile |
| `apartments`, `residential` (large) | Multi-Family |
| `school`, `university`, `college` | Education |
| `hospital`, `clinic` | Healthcare |
| `hotel` | Lodging |
| `church`, `cathedral`, `mosque`, `synagogue` | Religious Worship |
| `warehouse`, `industrial` | Warehouse and Storage |
| `restaurant`, `fast_food` | Food Service |
| `public`, `civic`, `government` | Public Order and Safety |
| `theatre`, `stadium`, `community_centre` | Public Assembly |
| `yes` (generic) | **Leave blank** |

### Imputation Models

**Training:**
- Source: raw ComStock/ResStock datasets (same data used to train EUI models)
- One XGBoost classifier per target field (7 models total)
- Input features: `building_type`, `climate_zone`, `year_built`, `sqft`, `num_stories`, `state`
- Output: predicted class + probability score for confidence display
- Handles missing inputs gracefully (year_built may be null)

**Target fields (one model each):**
1. `heating_fuel`
2. `dhw_fuel`
3. `hvac_system_type`
4. `wall_construction`
5. `window_type`
6. `window_to_wall_ratio`
7. `lighting_type`

**Storage:** saved as `.pkl` files in `XGB_Models/Imputation/` directory

**Runtime:** loaded at startup alongside existing models, runs as part of `/lookup` response

## Frontend

### Address Input Component

- Address text input bar positioned above the existing BuildingForm
- "Look up" button triggers `GET /lookup?address=...`
- Loading spinner while Overpass query runs (2-5 seconds typical)
- Error states: address not found, building not found, network error

### Map Viewer Component (MapLibre GL JS)

- `vue-maplibre-gl` for Vue 3 integration
- Compact container (~400px height) positioned next to or above the form
- Free vector tile base layer (OpenStreetMap via MapTiler free tier or Stadia Maps)

**On successful lookup:**
- Center map on building lat/lon, zoom ~17-18
- Street map base layer with roads, labels, context
- Nearby building footprints rendered as flat, muted polygons
- Target building extruded in accent color: `num_stories x 3.4m` height
- Camera pitched ~45 degrees for 3D perspective
- User can orbit, zoom, and rotate the view

### Form Auto-Population

- Fields populated from lookup receive visual indicators:
  - **"from public records"** badge — data directly from OSM (building_type, num_stories)
  - **"estimated"** badge with confidence % — model-imputed fields
  - No badge — manually entered or not available
- All auto-filled fields remain fully editable
- Editing an auto-filled field clears its badge (user has taken ownership)
- Fields that couldn't be determined stay blank for manual entry

### Edge Cases

- **Address not found**: show error message, form remains in manual mode
- **Footprint not found**: populate what's available (zipcode, etc.), no map extrusion shown
- **Multiple candidate buildings**: highlight candidates on map, user clicks to select
- **OSM building tag is generic (`yes`)**: building_type left blank, user must select

## Dependencies (new)

### Backend
- `geopy` — Nominatim geocoding (already in AutoBEM)
- `shapely` — polygon geometry (already in AutoBEM)
- `pyproj` — UTM coordinate projection (already in AutoBEM)
- `requests` — Overpass API calls

### Frontend
- `maplibre-gl` — map rendering and 3D extrusion
- `vue-maplibre-gl` — Vue 3 bindings (or direct MapLibre usage)

## Reference Code

The core footprint search logic exists in:
- `/Users/brandonwinsatt/Documents/AutoBEM_python_project/OSM_footprint_search.py` — geocoding, Overpass query, polygon parsing, building matching, story extraction
- `/Users/brandonwinsatt/Documents/AutoBEM_python_project/OSM_footprint_search.py:latlon_to_cartesian()` — UTM projection for area calculation
