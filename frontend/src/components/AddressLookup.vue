<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { PTextInput, PButton } from '@partnerdevops/partner-components'
import type { AddressSuggestion } from '../types/lookup'
import { useAddressAutocomplete } from '../composables/useAddressAutocomplete'

defineProps<{
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  lookup: [address: string]
}>()

const address = ref('')
const showDropdown = ref(false)
const activeIndex = ref(-1)

const { suggestions, loading: autocompleteLoading } = useAddressAutocomplete(address)

const hasSuggestions = computed(() => suggestions.value.length > 0 && showDropdown.value)

// Reset active index when suggestions change
watch(suggestions, () => { activeIndex.value = -1 })

function selectSuggestion(suggestion: AddressSuggestion) {
  address.value = suggestion.display
  showDropdown.value = false
  suggestions.value = []
  emit('lookup', suggestion.display)
}

function onInput() {
  showDropdown.value = true
}

function onLookup() {
  if (address.value.trim()) {
    showDropdown.value = false
    emit('lookup', address.value.trim())
  }
}

function onBlur() {
  // Delay to allow click on suggestion to register
  setTimeout(() => { showDropdown.value = false }, 200)
}

function onFocus() {
  if (suggestions.value.length > 0) {
    showDropdown.value = true
  }
}

function onKeydown(e: KeyboardEvent) {
  if (!hasSuggestions.value) return

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, suggestions.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (e.key === 'Enter' && activeIndex.value >= 0) {
    e.preventDefault()
    const selected = suggestions.value[activeIndex.value]
    if (selected) selectSuggestion(selected)
  } else if (e.key === 'Escape') {
    showDropdown.value = false
  }
}
</script>

<template>
  <div class="address-lookup">
    <div class="address-lookup__header">
      <p class="address-lookup__label">Building Address</p>
      <p class="address-lookup__desc">Enter an address to auto-populate building details</p>
    </div>
    <form class="address-lookup__form" @submit.prevent="onLookup">
      <div class="address-lookup__input-wrap">
        <PTextInput
          v-model="address"
          placeholder="e.g. 210 N Wells St, Chicago, IL 60606"
          size="medium"
          :disabled="loading"
          @input="onInput"
          @blur="onBlur"
          @focus="onFocus"
          @keydown="onKeydown"
        />
        <ul v-if="hasSuggestions" class="address-lookup__suggestions">
          <li
            v-for="(s, i) in suggestions"
            :key="i"
            class="address-lookup__suggestion"
            :class="{ 'address-lookup__suggestion--active': i === activeIndex }"
            @mousedown.prevent="selectSuggestion(s)"
          >
            {{ s.display }}
          </li>
        </ul>
        <div v-if="autocompleteLoading && address.length >= 3" class="address-lookup__loading">
          Searching...
        </div>
      </div>
      <PButton
        type="submit"
        variant="secondary"
        size="medium"
        :disabled="loading || !address.trim()"
      >
        {{ loading ? 'Looking up...' : 'Look Up' }}
      </PButton>
    </form>
    <p v-if="error" class="address-lookup__error">{{ error }}</p>
  </div>
</template>

<style scoped>
.address-lookup {
  background-color: var(--app-surface-raised);
  border: 1px solid #e2e6ea;
  border-radius: 6px;
  padding: 1.5rem 2rem;
  margin-bottom: 1.5rem;
}

.address-lookup__header {
  margin-bottom: 1rem;
}

.address-lookup__label {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  color: var(--app-header-bg);
  margin: 0;
}

.address-lookup__desc {
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: #6b7a8a;
  letter-spacing: 0.01em;
  margin: 0.25rem 0 0;
}

.address-lookup__form {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.address-lookup__input-wrap {
  flex: 1;
  position: relative;
}

.address-lookup__suggestions {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 50;
  margin: 0;
  padding: 0;
  list-style: none;
  background: var(--app-surface-raised, #fff);
  border: 1px solid #e2e6ea;
  border-top: none;
  border-radius: 0 0 4px 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  max-height: 220px;
  overflow-y: auto;
}

.address-lookup__suggestion {
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
  color: var(--partner-text-primary, #333e47);
  cursor: pointer;
  border-bottom: 1px solid #f0f2f4;
}

.address-lookup__suggestion:last-child {
  border-bottom: none;
}

.address-lookup__suggestion:hover,
.address-lookup__suggestion--active {
  background-color: var(--partner-surface-hovered, #f4f6f8);
}

.address-lookup__loading {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  color: #6b7a8a;
  background: var(--app-surface-raised, #fff);
  border: 1px solid #e2e6ea;
  border-top: none;
  border-radius: 0 0 4px 4px;
}

.address-lookup__error {
  color: var(--partner-error-main, #dc2626);
  font-size: 0.8125rem;
  margin: 0.5rem 0 0;
}
</style>
