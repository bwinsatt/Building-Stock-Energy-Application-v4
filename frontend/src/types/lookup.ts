export interface FieldResult {
  value: string | number | null
  source: 'osm' | 'computed' | 'imputed' | 'nyc_opendata' | null
  confidence: number | null
}

export interface LookupResponse {
  address: string
  lat: number
  lon: number
  zipcode: string | null
  building_fields: Record<string, FieldResult>
  target_building_polygon: number[][] | null
  nearby_buildings: Array<{
    polygon: number[][]
    levels: number | null
  }>
}

export interface AddressSuggestion {
  display: string
  lat: number
  lon: number
  zipcode: string | null
}
