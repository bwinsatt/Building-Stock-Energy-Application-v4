export const BUILDING_TYPES = [
  'Education', 'Food Sales', 'Food Service', 'Healthcare',
  'Lodging', 'Mercantile', 'Mixed Use', 'Multi-Family', 'Office',
  'Public Assembly', 'Public Order and Safety', 'Religious Worship',
  'Service', 'Warehouse and Storage',
]

export const HEATING_FUELS = [
  { value: 'NaturalGas', label: 'Natural Gas' },
  { value: 'Electricity', label: 'Electricity' },
  { value: 'FuelOil', label: 'Fuel Oil' },
  { value: 'Propane', label: 'Propane' },
  { value: 'DistrictHeating', label: 'District Heating' },
]

export const DHW_FUELS = [
  { value: 'NaturalGas', label: 'Natural Gas' },
  { value: 'Electricity', label: 'Electricity' },
  { value: 'FuelOil', label: 'Fuel Oil' },
  { value: 'Propane', label: 'Propane' },
]

// ---------------------------------------------------------------------------
// HVAC two-tier category system
// ---------------------------------------------------------------------------

export interface HvacVariant {
  value: string
  label: string
  dataset?: 'comstock' | 'resstock'
}

export interface HvacCategory {
  key: string
  label: string
  defaultVariant: string
  datasets: ('comstock' | 'resstock')[]
  variants: HvacVariant[]
}

export const HVAC_CATEGORIES: HvacCategory[] = [
  {
    key: 'packaged_rooftop',
    label: 'Packaged Rooftop (DX)',
    defaultVariant: 'PSZ-AC with gas coil',
    datasets: ['comstock'],
    variants: [
      { value: 'PSZ-AC with gas coil', label: 'Gas Heating Coil' },
      { value: 'PSZ-AC with gas boiler', label: 'Gas Boiler' },
      { value: 'PSZ-AC with electric coil', label: 'Electric Heating Coil' },
      { value: 'PSZ-AC with district hot water', label: 'District Hot Water' },
    ],
  },
  {
    key: 'packaged_heat_pump',
    label: 'Packaged Heat Pump',
    defaultVariant: 'PSZ-HP',
    datasets: ['comstock'],
    variants: [
      { value: 'PSZ-HP', label: 'PSZ-HP' },
    ],
  },
  {
    key: 'through_wall',
    label: 'Through-Wall / PTAC',
    defaultVariant: 'PTAC with gas coil',
    datasets: ['comstock'],
    variants: [
      { value: 'PTAC with gas coil', label: 'Gas Heating Coil' },
      { value: 'PTAC with gas boiler', label: 'Gas Boiler' },
      { value: 'PTAC with electric coil', label: 'Electric Heating Coil' },
    ],
  },
  {
    key: 'through_wall_heat_pump',
    label: 'Through-Wall Heat Pump',
    defaultVariant: 'PTHP',
    datasets: ['comstock'],
    variants: [
      { value: 'PTHP', label: 'PTHP' },
    ],
  },
  {
    key: 'central_chiller_boiler',
    label: 'Central Boiler + Chiller',
    defaultVariant: 'VAV chiller with gas boiler reheat',
    datasets: ['comstock', 'resstock'],
    variants: [
      { value: 'VAV chiller with gas boiler reheat', label: 'VAV - Water-Cooled Chiller, Gas Boiler', dataset: 'comstock' },
      { value: 'VAV chiller with PFP boxes', label: 'VAV - Water-Cooled Chiller, Electric Reheat', dataset: 'comstock' },
      { value: 'VAV chiller with district hot water reheat', label: 'VAV - Water-Cooled Chiller, District Hot Water', dataset: 'comstock' },
      { value: 'VAV air-cooled chiller with gas boiler reheat', label: 'VAV - Air-Cooled Chiller, Gas Boiler', dataset: 'comstock' },
      { value: 'VAV air-cooled chiller with PFP boxes', label: 'VAV - Air-Cooled Chiller, Electric Reheat', dataset: 'comstock' },
      { value: 'VAV air-cooled chiller with district hot water reheat', label: 'VAV - Air-Cooled Chiller, District Hot Water', dataset: 'comstock' },
      { value: 'VAV district chilled water with district hot water reheat', label: 'VAV - District Chilled Water', dataset: 'comstock' },
      { value: 'Fan Coil Units', label: 'Fan Coil Units', dataset: 'resstock' },
      { value: 'Baseboards / Radiators', label: 'Baseboards / Radiators', dataset: 'resstock' },
    ],
  },
  {
    key: 'packaged_vav',
    label: 'Packaged VAV (Rooftop)',
    defaultVariant: 'PVAV with gas heat with electric reheat',
    datasets: ['comstock'],
    variants: [
      { value: 'PVAV with gas boiler reheat', label: 'PVAV - Gas Boiler Reheat' },
      { value: 'PVAV with gas heat with electric reheat', label: 'PVAV - Gas Heat, Electric Reheat' },
      { value: 'PVAV with PFP boxes', label: 'PVAV - Electric Reheat' },
      { value: 'PVAV with district hot water reheat', label: 'PVAV - District Hot Water' },
    ],
  },
  {
    key: 'doas_fan_coil',
    label: 'DOAS + Fan Coil',
    defaultVariant: 'DOAS with fan coil chiller with boiler',
    datasets: ['comstock'],
    variants: [
      { value: 'DOAS with fan coil chiller with boiler', label: 'Fan Coil - Chiller + Boiler' },
      { value: 'DOAS with fan coil air-cooled chiller with boiler', label: 'Fan Coil - Air-Cooled Chiller + Boiler' },
      { value: 'DOAS with fan coil chiller with baseboard electric', label: 'Fan Coil - Chiller + Electric Baseboard' },
      { value: 'DOAS with fan coil chiller with district hot water', label: 'Fan Coil - Chiller + District Hot Water' },
      { value: 'DOAS with fan coil district chilled water with baseboard electric', label: 'Fan Coil - District Chilled Water + Electric' },
      { value: 'DOAS with fan coil district chilled water with district hot water', label: 'Fan Coil - District Chilled Water + District Hot Water' },
      { value: 'DOAS with water source heat pumps cooling tower with boiler', label: 'Water Source Heat Pumps - Cooling Tower + Boiler' },
      { value: 'DOAS with water source heat pumps with ground source heat pump', label: 'Water Source Heat Pumps - Ground Source' },
    ],
  },
  {
    key: 'forced_air_furnace',
    label: 'Forced Air Furnace + AC',
    defaultVariant: 'Residential AC with residential forced air furnace',
    datasets: ['comstock', 'resstock'],
    variants: [
      { value: 'Residential AC with residential forced air furnace', label: 'Forced Air Furnace + AC', dataset: 'comstock' },
      { value: 'Ducted Heating', label: 'Forced Air Furnace + AC', dataset: 'resstock' },
    ],
  },
  {
    key: 'ducted_heat_pump',
    label: 'Ducted Heat Pump',
    defaultVariant: 'Ducted Heat Pump',
    datasets: ['resstock'],
    variants: [
      { value: 'Ducted Heat Pump', label: 'Ducted Heat Pump' },
    ],
  },
  {
    key: 'baseboard_wall_unit',
    label: 'Baseboard / Wall Unit',
    defaultVariant: 'Non-Ducted Heating',
    datasets: ['resstock'],
    variants: [
      { value: 'Non-Ducted Heating', label: 'Baseboard / Wall Unit' },
    ],
  },
  {
    key: 'mini_split_heat_pump',
    label: 'Mini-Split Heat Pump',
    defaultVariant: 'Non-Ducted Heat Pump',
    datasets: ['resstock'],
    variants: [
      { value: 'Non-Ducted Heat Pump', label: 'Mini-Split Heat Pump' },
    ],
  },
]

/** Get categories filtered by dataset, with variants filtered too */
export function getHvacCategoriesForDataset(buildingType: string): HvacCategory[] {
  const dataset = buildingType === 'Multi-Family' ? 'resstock' : 'comstock'
  return HVAC_CATEGORIES
    .filter(c => c.datasets.includes(dataset))
    .map(c => ({
      ...c,
      variants: c.variants.filter(v => !v.dataset || v.dataset === dataset),
      defaultVariant: c.variants.find(v => !v.dataset || v.dataset === dataset)?.value ?? c.defaultVariant,
    }))
}

/** Reverse-lookup: given any HVAC value (old code, variant string, or category key), return the category */
export function getHvacCategoryForValue(value: string): HvacCategory | undefined {
  // Check category keys first
  const byKey = HVAC_CATEGORIES.find(c => c.key === value)
  if (byKey) return byKey

  // Check variant values
  for (const cat of HVAC_CATEGORIES) {
    if (cat.variants.some(v => v.value === value)) return cat
    if (cat.defaultVariant === value) return cat
  }

  // Legacy old codes mapping
  const legacyMap: Record<string, string> = {
    'PSZ-AC': 'packaged_rooftop',
    'PSZ-HP': 'packaged_heat_pump',
    'PTAC': 'through_wall',
    'PTHP': 'through_wall_heat_pump',
    'VAV_chiller_boiler': 'central_chiller_boiler',
    'VAV_air_cooled_chiller_boiler': 'central_chiller_boiler',
    'PVAV_gas_boiler': 'packaged_vav',
    'PVAV_gas_heat': 'packaged_vav',
    'Residential_AC_gas_furnace': 'forced_air_furnace',
    'Residential_forced_air_furnace': 'forced_air_furnace',
    'Residential_AC_electric_baseboard': 'forced_air_furnace',
    // Old ResStock category keys
    'ducted_heating': 'forced_air_furnace',
    'non_ducted_heating': 'baseboard_wall_unit',
    'non_ducted_heat_pump': 'mini_split_heat_pump',
    'residential_furnace': 'forced_air_furnace',
  }
  const catKey = legacyMap[value]
  if (catKey) return HVAC_CATEGORIES.find(c => c.key === catKey)

  return undefined
}

/** @deprecated Use HVAC_CATEGORIES instead */
export const HVAC_SYSTEM_TYPES = [
  'PSZ-AC', 'PSZ-HP', 'PTAC', 'PTHP',
  'VAV_chiller_boiler', 'VAV_air_cooled_chiller_boiler',
  'PVAV_gas_boiler', 'PVAV_gas_heat',
  'Residential_AC_gas_furnace', 'Residential_forced_air_furnace',
  'Residential_AC_electric_baseboard',
]

export const WALL_CONSTRUCTIONS = [
  'Mass', 'Metal', 'SteelFrame', 'WoodFrame',
]

export const WINDOW_TYPES = [
  'Single, Clear, Metal', 'Single, Clear, Non-metal',
  'Double, Clear, Metal', 'Double, Clear, Non-metal',
  'Double, Low-E, Metal', 'Double, Low-E, Non-metal',
  'Triple, Low-E, Metal', 'Triple, Low-E, Non-metal',
]

export const WINDOW_TO_WALL_RATIOS = [
  '0-10%', '10-20%', '20-30%', '30-40%', '40-50%', '50%+',
]

// ResStock efficiency/envelope options (shown in Advanced Details)
export const HVAC_HEATING_EFFICIENCIES_RESSTOCK = [
  { value: 'Fuel Furnace, 80% AFUE', label: 'Gas Furnace - 80% AFUE' },
  { value: 'Fuel Furnace, 92.5% AFUE', label: 'Gas Furnace - 92.5% AFUE' },
  { value: 'Fuel Furnace, 96% AFUE', label: 'Gas Furnace - 96% AFUE' },
  { value: 'Fuel Boiler, 80% AFUE', label: 'Gas Boiler - 80% AFUE' },
  { value: 'Fuel Boiler, 90% AFUE', label: 'Gas Boiler - 90% AFUE' },
  { value: 'Fuel Wall Furnace, 68% AFUE', label: 'Wall Furnace - 68% AFUE' },
  { value: 'Electric Baseboard, 100% Efficiency', label: 'Electric Baseboard' },
  { value: 'Electric Boiler, 100% Efficiency', label: 'Electric Boiler' },
  { value: 'Electric Furnace, 100% Efficiency', label: 'Electric Furnace' },
  { value: 'Electric Wall Furnace, 100% Efficiency', label: 'Electric Wall Furnace' },
  { value: 'ASHP, SEER 13, 7.7 HSPF', label: 'Air Source Heat Pump - SEER 13' },
  { value: 'ASHP, SEER 15, 8.5 HSPF', label: 'Air Source Heat Pump - SEER 15' },
  { value: 'ASHP, SEER 15.05, 8.79 HSPF', label: 'Air Source Heat Pump - SEER 15 (High)' },
  { value: 'ASHP, SEER 16, 9.05 HSPF', label: 'Air Source Heat Pump - SEER 16' },
  { value: 'ASHP, SEER 17.16, 9.2 HSPF', label: 'Air Source Heat Pump - SEER 17' },
  { value: 'MSHP, SEER 14.5, 8.2 HSPF', label: 'Mini-Split Heat Pump - SEER 14.5' },
  { value: 'MSHP, SEER 29.3, 14 HSPF', label: 'Mini-Split Heat Pump - SEER 29.3' },
  { value: 'Shared Heating', label: 'Shared Heating System' },
]

export const HVAC_COOLING_EFFICIENCIES_RESSTOCK = [
  { value: 'AC, SEER 8', label: 'Central AC - SEER 8' },
  { value: 'AC, SEER 10', label: 'Central AC - SEER 10' },
  { value: 'AC, SEER 13', label: 'Central AC - SEER 13' },
  { value: 'AC, SEER 15', label: 'Central AC - SEER 15' },
  { value: 'Room AC, EER 8.5', label: 'Room AC - EER 8.5' },
  { value: 'Room AC, EER 10.7', label: 'Room AC - EER 10.7' },
  { value: 'Room AC, EER 12', label: 'Room AC - EER 12' },
  { value: 'Ducted Heat Pump', label: 'Ducted Heat Pump' },
  { value: 'Non-Ducted Heat Pump', label: 'Mini-Split Heat Pump' },
  { value: 'Shared Cooling', label: 'Shared Cooling System' },
  { value: 'None', label: 'No Cooling' },
]

export const WATER_HEATER_EFFICIENCIES_RESSTOCK = [
  { value: 'Natural Gas Standard', label: 'Natural Gas - Standard' },
  { value: 'Natural Gas Premium', label: 'Natural Gas - Premium' },
  { value: 'Natural Gas Tankless', label: 'Natural Gas - Tankless' },
  { value: 'Electric Standard', label: 'Electric - Standard' },
  { value: 'Electric Premium', label: 'Electric - Premium' },
  { value: 'Electric Tankless', label: 'Electric - Tankless' },
  { value: 'Electric Heat Pump, 50 gal', label: 'Electric Heat Pump - 50 gal' },
  { value: 'Electric Heat Pump, 66 gal', label: 'Electric Heat Pump - 66 gal' },
  { value: 'Electric Heat Pump, 80 gal', label: 'Electric Heat Pump - 80 gal' },
  { value: 'Fuel Oil Standard', label: 'Fuel Oil - Standard' },
  { value: 'Fuel Oil Premium', label: 'Fuel Oil - Premium' },
  { value: 'Propane Standard', label: 'Propane - Standard' },
  { value: 'Propane Premium', label: 'Propane - Premium' },
  { value: 'Propane Tankless', label: 'Propane - Tankless' },
  { value: 'Other Fuel', label: 'Other Fuel' },
]

export const WALL_INSULATIONS_RESSTOCK = [
  { value: 'Wood Stud, Uninsulated', label: 'Wood Stud - Uninsulated' },
  { value: 'Wood Stud, R-7', label: 'Wood Stud - R-7' },
  { value: 'Wood Stud, R-11', label: 'Wood Stud - R-11' },
  { value: 'Wood Stud, R-15', label: 'Wood Stud - R-15' },
  { value: 'Wood Stud, R-19', label: 'Wood Stud - R-19' },
  { value: 'CMU, 6-in Hollow, Uninsulated', label: 'CMU Block - Uninsulated' },
  { value: 'CMU, 6-in Hollow, R-7', label: 'CMU Block - R-7' },
  { value: 'CMU, 6-in Hollow, R-11', label: 'CMU Block - R-11' },
  { value: 'CMU, 6-in Hollow, R-15', label: 'CMU Block - R-15' },
  { value: 'CMU, 6-in Hollow, R-19', label: 'CMU Block - R-19' },
  { value: 'Brick, 12-in, 3-wythe, Uninsulated', label: 'Brick 3-Wythe - Uninsulated' },
  { value: 'Brick, 12-in, 3-wythe, R-7', label: 'Brick 3-Wythe - R-7' },
  { value: 'Brick, 12-in, 3-wythe, R-11', label: 'Brick 3-Wythe - R-11' },
  { value: 'Brick, 12-in, 3-wythe, R-15', label: 'Brick 3-Wythe - R-15' },
  { value: 'Brick, 12-in, 3-wythe, R-19', label: 'Brick 3-Wythe - R-19' },
]

export const INFILTRATION_RATES_RESSTOCK = [
  { value: '2 ACH50', label: '2 ACH50 (Very Tight)' },
  { value: '3 ACH50', label: '3 ACH50 (Tight)' },
  { value: '4 ACH50', label: '4 ACH50' },
  { value: '5 ACH50', label: '5 ACH50 (Average)' },
  { value: '7 ACH50', label: '7 ACH50' },
  { value: '8 ACH50', label: '8 ACH50' },
  { value: '10 ACH50', label: '10 ACH50 (Leaky)' },
  { value: '15 ACH50', label: '15 ACH50' },
  { value: '20 ACH50', label: '20 ACH50' },
  { value: '25 ACH50', label: '25 ACH50 (Very Leaky)' },
  { value: '30 ACH50', label: '30 ACH50' },
  { value: '40 ACH50', label: '40 ACH50' },
  { value: '50 ACH50', label: '50 ACH50 (Extremely Leaky)' },
]

export const LIGHTING_TYPES = [
  'T12', 'T8', 'T5', 'CFL', 'LED',
]
