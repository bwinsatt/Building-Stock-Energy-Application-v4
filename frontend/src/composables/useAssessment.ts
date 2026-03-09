import { ref } from 'vue'
import type { BuildingInput, BuildingResult, AssessmentResponse } from '../types/assessment'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'

export function useAssessment() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const result = ref<BuildingResult | null>(null)

  async function assess(input: BuildingInput) {
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
      const data: AssessmentResponse = await response.json()
      result.value = data.results[0] ?? null
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

  return { loading, error, result, assess, reset }
}
