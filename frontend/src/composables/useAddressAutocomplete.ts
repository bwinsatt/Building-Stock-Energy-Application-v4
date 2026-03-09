import { ref, watch, type Ref } from 'vue'
import type { AddressSuggestion } from '../types/lookup'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'

export function useAddressAutocomplete(query: Ref<string>, debounceMs = 300) {
  const suggestions = ref<AddressSuggestion[]>([])
  const loading = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null
  let abortController: AbortController | null = null

  async function fetchSuggestions(q: string) {
    if (q.length < 3) {
      suggestions.value = []
      return
    }

    // Cancel any in-flight request
    if (abortController) {
      abortController.abort()
    }
    abortController = new AbortController()

    loading.value = true
    try {
      const resp = await fetch(
        `${API_BASE}/autocomplete?q=${encodeURIComponent(q)}`,
        { signal: abortController.signal },
      )
      if (resp.ok) {
        suggestions.value = await resp.json()
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        suggestions.value = []
      }
    } finally {
      loading.value = false
    }
  }

  watch(query, (val) => {
    if (timer) clearTimeout(timer)
    if (val.length < 3) {
      suggestions.value = []
      return
    }
    timer = setTimeout(() => fetchSuggestions(val), debounceMs)
  })

  function clear() {
    suggestions.value = []
  }

  return { suggestions, loading, clear }
}
