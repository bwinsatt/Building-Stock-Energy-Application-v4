import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import type {
  MeasureResult,
  BaselineResult,
  BuildingInput,
  ProjectedEui,
  EnergyStarResponse,
} from '../types/assessment'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'

export function useMeasureSelections(
  measures: Ref<MeasureResult[]>,
  baseline: Ref<BaselineResult | null>,
  building: Ref<BuildingInput | null>,
  buildingId: Ref<number | null>,
  address: Ref<string | null>,
  projectId: Ref<number | null>,
) {
  function _selectionsUrl(suffix = '') {
    return `${API_BASE}/projects/${projectId.value}/buildings/${buildingId.value}/selections${suffix}`
  }

  const selectedUpgradeIds = ref<Set<number>>(new Set())
  const projectedEspm = ref<EnergyStarResponse | null>(null)
  const projectedLoading = ref(false)
  const projectedError = ref<string | null>(null)
  const initialized = ref(false)

  // --- Package constituent map (derived from measures data) ---
  const packageConstituentMap = computed<Map<number, number[]>>(() => {
    const map = new Map<number, number[]>()
    for (const m of measures.value) {
      if (m.constituent_upgrade_ids && m.constituent_upgrade_ids.length > 0) {
        map.set(m.upgrade_id, m.constituent_upgrade_ids)
      }
    }
    return map
  })

  // --- Disabled individual measure IDs (locked out by selected packages) ---
  const disabledByPackage = computed<Map<number, string>>(() => {
    const map = new Map<number, string>()
    for (const [pkgId, constituents] of packageConstituentMap.value) {
      if (selectedUpgradeIds.value.has(pkgId)) {
        const pkgName = measures.value.find(m => m.upgrade_id === pkgId)?.name ?? 'a package'
        for (const cid of constituents) {
          map.set(cid, pkgName)
        }
      }
    }
    return map
  })

  // --- Projected EUI (computed client-side) ---
  const projectedEui = computed<ProjectedEui | null>(() => {
    if (!baseline.value || selectedUpgradeIds.value.size === 0) return null

    const baseByFuel = baseline.value.eui_by_fuel

    let elec = baseByFuel.electricity
    let gas = baseByFuel.natural_gas
    let oil = baseByFuel.fuel_oil
    let propane = baseByFuel.propane
    let district = baseByFuel.district_heating

    for (const uid of selectedUpgradeIds.value) {
      const m = measures.value.find(m => m.upgrade_id === uid)
      if (!m?.savings_by_fuel) continue
      elec -= m.savings_by_fuel.electricity
      gas -= m.savings_by_fuel.natural_gas
      oil -= m.savings_by_fuel.fuel_oil
      propane -= m.savings_by_fuel.propane
      district -= m.savings_by_fuel.district_heating
    }

    // Floor at zero
    elec = Math.max(0, elec)
    gas = Math.max(0, gas)
    oil = Math.max(0, oil)
    propane = Math.max(0, propane)
    district = Math.max(0, district)

    const total = elec + gas + oil + propane + district
    const baseTotal = baseline.value.total_eui_kbtu_sf
    const reductionPct = baseTotal > 0 ? ((baseTotal - total) / baseTotal) * 100 : 0

    return {
      total_eui_kbtu_sf: total,
      eui_by_fuel: { electricity: elec, natural_gas: gas, fuel_oil: oil, propane, district_heating: district },
      reduction_pct: reductionPct,
    }
  })

  // --- Toggle measure selection ---
  function toggleMeasure(upgradeId: number): { action: 'selected' | 'deselected' | 'replace'; replaced?: number[] } | null {
    // Don't allow selecting disabled measures
    if (disabledByPackage.value.has(upgradeId)) return null

    const newSet = new Set(selectedUpgradeIds.value)

    if (newSet.has(upgradeId)) {
      // Deselect
      newSet.delete(upgradeId)
      selectedUpgradeIds.value = newSet
      // Clear projected score (selections changed)
      projectedEspm.value = null
      _saveSelections()
      // If deselecting empties the set, clear projected ESPM from DB too
      if (newSet.size === 0) {
        _clearProjectedEspm()
      }
      return { action: 'deselected' }
    }

    // Check if this is a package that conflicts with selected individuals
    const constituents = packageConstituentMap.value.get(upgradeId)
    if (constituents) {
      const overlapping = constituents.filter(cid => newSet.has(cid))
      if (overlapping.length > 0) {
        // Auto-replace: remove overlapping individuals, add package
        for (const cid of overlapping) {
          newSet.delete(cid)
        }
        newSet.add(upgradeId)
        selectedUpgradeIds.value = newSet
        projectedEspm.value = null
        _saveSelections()
        return { action: 'replace', replaced: overlapping }
      }
    }

    // Normal select
    newSet.add(upgradeId)
    selectedUpgradeIds.value = newSet
    projectedEspm.value = null
    _saveSelections()
    return { action: 'selected' }
  }

  // --- Persistence ---
  async function _saveSelections() {
    if (!buildingId.value || !projectId.value) return
    try {
      await fetch(
        _selectionsUrl(),
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            selected_upgrade_ids: Array.from(selectedUpgradeIds.value),
          }),
        },
      )
    } catch {
      // Optimistic update — selection already applied in UI.
      // On failure, we could revert, but for now just log.
      console.error('Failed to save selections')
    }
  }

  async function _clearProjectedEspm() {
    if (!buildingId.value || !projectId.value) return
    try {
      await fetch(
        _selectionsUrl('/projected-espm'),
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ projected_espm: null }),
        },
      )
    } catch {
      console.error('Failed to clear projected ESPM')
    }
  }

  async function loadSelections() {
    if (!buildingId.value || !projectId.value) return
    try {
      const resp = await fetch(
        _selectionsUrl(),
      )
      if (resp.ok) {
        const data = await resp.json()
        selectedUpgradeIds.value = new Set(data.selected_upgrade_ids ?? [])
        projectedEspm.value = data.projected_espm ?? null
        initialized.value = true
      }
    } catch {
      console.error('Failed to load selections')
    }
  }

  // --- Reconcile stale selections ---
  function reconcileSelections() {
    const validIds = new Set(
      measures.value.filter(m => m.applicable).map(m => m.upgrade_id)
    )
    const current = selectedUpgradeIds.value
    const reconciled = new Set<number>()
    let changed = false
    for (const id of current) {
      if (validIds.has(id)) {
        reconciled.add(id)
      } else {
        changed = true
      }
    }
    if (changed) {
      selectedUpgradeIds.value = reconciled
      _saveSelections()
    }
  }

  // --- Calculate projected ENERGY STAR score ---
  async function calculateProjectedScore() {
    if (!building.value || !projectedEui.value) return
    projectedLoading.value = true
    projectedError.value = null
    try {
      const resp = await fetch(`${API_BASE}/energy-star/projected-score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          building: building.value,
          projected_eui_by_fuel: projectedEui.value.eui_by_fuel,
          address: address.value,
        }),
      })
      if (!resp.ok) {
        const detail = await resp.json().catch(() => null)
        throw new Error(detail?.detail || `Server error: ${resp.status}`)
      }
      const espmResult = await resp.json()
      projectedEspm.value = espmResult
      // Save projected score to DB via dedicated endpoint
      if (buildingId.value && projectId.value) {
        await fetch(
          _selectionsUrl('/projected-espm'),
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ projected_espm: espmResult }),
          },
        )
      }
    } catch (e) {
      projectedError.value = (e as Error).message
    } finally {
      projectedLoading.value = false
    }
  }

  return {
    selectedUpgradeIds,
    packageConstituentMap,
    disabledByPackage,
    projectedEui,
    projectedEspm,
    projectedLoading,
    projectedError,
    toggleMeasure,
    loadSelections,
    reconcileSelections,
    calculateProjectedScore,
    initialized,
  }
}
