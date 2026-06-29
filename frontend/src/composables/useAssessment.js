import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export function useAssessment() {
  const loading = ref(false)
  const error = ref(null)
  const result = ref(null)
  const exporting = ref(false)

  async function assess(input) {
    loading.value = true
    error.value = null
    result.value = null
    try {
      const response = await fetch(`${API_BASE}/assess`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ buildings: [input] }),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || `Server error: ${response.status}`)
      }
      const data = await response.json()
      result.value = data.results[0] ?? null
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function exportCarbonPerformance(building, assessmentResult, selectedUpgradeIds, espmPropertyType) {
    exporting.value = true
    error.value = null
    try {
      const response = await fetch(`${API_BASE}/export/carbon-performance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          building,
          result: assessmentResult,
          selected_upgrade_ids: selectedUpgradeIds,
          espm_property_type: espmPropertyType ?? null,
        }),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || `Server error: ${response.status}`)
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `CarbonPerformance_${building.zipcode}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      error.value = e.message
    } finally {
      exporting.value = false
    }
  }

  function reset() {
    result.value = null
    error.value = null
  }

  return { loading, error, result, assess, reset, exporting, exportCarbonPerformance }
}
