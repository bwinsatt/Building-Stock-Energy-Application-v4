export interface Project {
  id: number
  name: string
  created_at: string
  updated_at: string
  buildings?: Building[]
}

export interface Building {
  id: number
  project_id: number
  address: string
  building_input: Record<string, unknown>
  utility_data: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface Assessment {
  id: number
  building_id: number
  result: Record<string, unknown>
  calibrated: boolean
  created_at: string
}
