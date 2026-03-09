export interface BuildingInput {
  building_type: string
  sqft: number
  num_stories: number
  zipcode: string
  year_built: number
  heating_fuel?: string
  dhw_fuel?: string
  hvac_system_type?: string
  wall_construction?: string
  window_type?: string
  window_to_wall_ratio?: string
  lighting_type?: string
  operating_hours?: number
  hvac_heating_efficiency?: string
  hvac_cooling_efficiency?: string
  water_heater_efficiency?: string
  insulation_wall?: string
  infiltration?: string
}

export interface FuelBreakdown {
  electricity: number
  natural_gas: number
  fuel_oil: number
  propane: number
  district_heating: number
}

export interface BaselineResult {
  total_eui_kbtu_sf: number
  eui_by_fuel: FuelBreakdown
  emissions_kg_co2e_per_sf?: number
}

export interface CostEstimate {
  installed_cost_per_sf: number
  installed_cost_total: number
  cost_range: { low: number; high: number }
  useful_life_years?: number
  regional_factor: number
  confidence: string
}

export interface MeasureResult {
  upgrade_id: number
  name: string
  category: string
  applicable: boolean
  post_upgrade_eui_kbtu_sf?: number
  savings_kbtu_sf?: number
  savings_pct?: number
  cost?: CostEstimate
  utility_bill_savings_per_sf?: number
  simple_payback_years?: number
  emissions_reduction_pct?: number
}

export interface ImputedField {
  value: string
  label: string
  source: 'model' | 'default' | 'user' | 'derived'
  confidence: number | null
}

export interface InputSummary {
  climate_zone: string
  cluster_name: string
  state: string
  vintage_bucket: string
  imputed_fields: string[]
  imputed_details: Record<string, ImputedField>
}

export interface BuildingResult {
  building_index: number
  baseline: BaselineResult
  measures: MeasureResult[]
  input_summary: InputSummary
}

export interface AssessmentResponse {
  results: BuildingResult[]
}
