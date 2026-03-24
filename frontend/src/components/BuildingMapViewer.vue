<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

const props = defineProps({
  lat: { type: Number, required: true },
  lon: { type: Number, required: true },
  targetPolygon: { type: Array, default: null },
  nearbyBuildings: { type: Array, required: true },
  numStories: { type: Number, required: true },
})

const mapContainer = ref()
let map = null

const FLOOR_HEIGHT_M = 3.4

function initMap() {
  if (!mapContainer.value) return

  map = new maplibregl.Map({
    container: mapContainer.value,
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '&copy; OpenStreetMap contributors',
        },
      },
      layers: [
        {
          id: 'osm-tiles',
          type: 'raster',
          source: 'osm',
          minzoom: 0,
          maxzoom: 19,
        },
      ],
    },
    center: [props.lon, props.lat],
    zoom: 17,
    pitch: 45,
    bearing: -17,
  })

  map.addControl(new maplibregl.NavigationControl())

  map.on('load', () => {
    addBuildingLayers()
  })
}

function addBuildingLayers() {
  if (!map) return

  // Nearby buildings (flat, muted)
  if (props.nearbyBuildings.length > 0) {
    const nearbyFeatures = props.nearbyBuildings.map((b) => ({
      type: 'Feature',
      properties: {
        height: (b.levels || 1) * FLOOR_HEIGHT_M,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [b.polygon.map((coord) => [coord[1], coord[0]])],
      },
    }))

    map.addSource('nearby-buildings', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: nearbyFeatures },
    })

    map.addLayer({
      id: 'nearby-buildings-3d',
      type: 'fill-extrusion',
      source: 'nearby-buildings',
      paint: {
        'fill-extrusion-color': '#c4cdd5',
        'fill-extrusion-height': ['get', 'height'],
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': 0.5,
      },
    })
  }

  // Target building (extruded, highlighted)
  if (props.targetPolygon) {
    const targetHeight = props.numStories * FLOOR_HEIGHT_M

    map.addSource('target-building', {
      type: 'geojson',
      data: {
        type: 'Feature',
        properties: { height: targetHeight },
        geometry: {
          type: 'Polygon',
          coordinates: [props.targetPolygon.map((coord) => [coord[1], coord[0]])],
        },
      },
    })

    map.addLayer({
      id: 'target-building-3d',
      type: 'fill-extrusion',
      source: 'target-building',
      paint: {
        'fill-extrusion-color': '#3b82f6',
        'fill-extrusion-height': targetHeight,
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': 0.8,
      },
    })

    // Outline for clarity
    map.addLayer({
      id: 'target-building-outline',
      type: 'line',
      source: 'target-building',
      paint: {
        'line-color': '#1e40af',
        'line-width': 2,
      },
    })
  }
}

onMounted(() => {
  initMap()
})

onUnmounted(() => {
  map?.remove()
})

// Re-render when data changes
watch(
  () => [props.targetPolygon, props.nearbyBuildings],
  () => {
    if (map?.loaded()) {
      // Remove old layers/sources and re-add
      for (const id of ['target-building-outline', 'target-building-3d', 'nearby-buildings-3d']) {
        if (map.getLayer(id)) map.removeLayer(id)
      }
      for (const id of ['target-building', 'nearby-buildings']) {
        if (map.getSource(id)) map.removeSource(id)
      }
      addBuildingLayers()

      // Fly to new location
      map.flyTo({ center: [props.lon, props.lat], zoom: 17, pitch: 45 })
    }
  },
)
</script>

<template>
  <div class="map-viewer">
    <div ref="mapContainer" class="map-viewer__map" />
  </div>
</template>

<style scoped>
.map-viewer {
  border: 1px solid #e2e6ea;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 1.5rem;
}

.map-viewer__map {
  width: 100%;
  height: 400px;
}
</style>
