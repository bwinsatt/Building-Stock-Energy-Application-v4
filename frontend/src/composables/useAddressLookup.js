import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'

export function useAddressLookup() {
  const loading = ref(false)
  const error = ref(null)
  const lookupResult = ref(null)

  async function lookup(address) {
    loading.value = true
    error.value = null
    lookupResult.value = null
    try {
      const response = await fetch(
        `${API_BASE}/lookup?address=${encodeURIComponent(address)}`,
      )
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Address not found. Please check and try again.')
        }
        const detail = await response.json().catch(() => null)
        throw new Error(detail?.detail || `Server error: ${response.status}`)
      }
      lookupResult.value = await response.json()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  function reset() {
    lookupResult.value = null
    error.value = null
  }

  return { loading, error, lookupResult, lookup, reset }
}
