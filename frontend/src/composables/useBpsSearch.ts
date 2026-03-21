import { ref } from 'vue'
import type { BpsSearchResult } from '../types/bps'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'

export function useBpsSearch() {
  const loading = ref(false)
  const result = ref<BpsSearchResult | null>(null)
  const error = ref<string | null>(null)
  const searched = ref(false)

  async function search(
    address: string,
    city?: string | null,
    state?: string | null,
    zipcode?: string | null,
  ): Promise<void> {
    loading.value = true
    error.value = null
    result.value = null
    searched.value = true

    const params = new URLSearchParams({ address })
    if (city) params.set('city', city)
    if (state) params.set('state', state)
    if (zipcode) params.set('zipcode', zipcode)

    try {
      const resp = await fetch(`${API_BASE}/bps/search?${params}`)
      if (resp.status === 404) {
        result.value = null
        return
      }
      if (!resp.ok) {
        throw new Error('Search failed')
      }
      result.value = await resp.json()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Search failed'
    } finally {
      loading.value = false
    }
  }

  function clear() {
    loading.value = false
    result.value = null
    error.value = null
    searched.value = false
  }

  return { loading, result, error, searched, search, clear }
}
