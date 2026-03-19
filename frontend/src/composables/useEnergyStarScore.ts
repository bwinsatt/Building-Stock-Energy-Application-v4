import { ref } from 'vue'
import type { BuildingInput, BaselineResult, EnergyStarResponse } from '../types/assessment'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'

export function useEnergyStarScore() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const result = ref<EnergyStarResponse | null>(null)

  async function fetchScore(
    building: BuildingInput,
    baseline: BaselineResult,
    address?: string | null,
  ) {
    loading.value = true
    error.value = null
    result.value = null
    try {
      const response = await fetch(`${API_BASE}/energy-star/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ building, baseline, address: address ?? null }),
      })
      if (!response.ok) {
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || `Server error: ${response.status}`)
      }
      result.value = await response.json()
    } catch (e) {
      error.value = (e as Error).message
    } finally {
      loading.value = false
    }
  }

  function reset() {
    result.value = null
    error.value = null
  }

  return { loading, error, result, fetchScore, reset }
}
