export interface BpsSearchResult {
  ordinance_name: string
  reporting_year: number | null
  property_name: string | null
  matched_address: string | null
  match_confidence: number | null
  site_eui_kbtu_sf: number | null
  electricity_kwh: number | null
  natural_gas_therms: number | null
  fuel_oil_gallons: number | null
  energy_star_score: number | null
  has_per_fuel_data: boolean
}
