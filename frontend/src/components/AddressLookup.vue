<script setup>
import { ref, computed, watch } from 'vue'
import { PTextInput, PButton } from '@partnerdevops/partner-components'
import { useAddressAutocomplete } from '../composables/useAddressAutocomplete'

defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: null },
})

const emit = defineEmits(['lookup'])

const address = ref('')
const showDropdown = ref(false)
const activeIndex = ref(-1)

const { suggestions, loading: autocompleteLoading } = useAddressAutocomplete(address)

const hasSuggestions = computed(() => suggestions.value.length > 0 && showDropdown.value)

// Reset active index when suggestions change
watch(suggestions, () => { activeIndex.value = -1 })

function selectSuggestion(suggestion) {
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

function onKeydown(e) {
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
  border: 1px solid var(--partner-gray-2);
  border-radius: var(--partner-radius-lg);
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
  color: var(--partner-gray-7);
  margin: 0;
}

.address-lookup__desc {
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: var(--partner-text-secondary);
  letter-spacing: 0.01em;
  margin: 0.25rem 0 0;
}

.address-lookup__form {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
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
  background: var(--partner-background-white);
  border: 1px solid var(--partner-gray-2);
  border-top: none;
  border-radius: 0 0 var(--partner-radius-md) var(--partner-radius-md);
  box-shadow: var(--partner-shadow-lg);
  max-height: 220px;
  overflow-y: auto;
}

.address-lookup__suggestion {
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
  color: var(--partner-text-primary);
  cursor: pointer;
  border-bottom: 1px solid var(--partner-gray-1);
}

.address-lookup__suggestion:last-child {
  border-bottom: none;
}

.address-lookup__suggestion:hover,
.address-lookup__suggestion--active {
  background-color: var(--partner-fill-hovered);
}

.address-lookup__loading {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  color: var(--partner-text-secondary);
  background: var(--partner-background-white);
  border: 1px solid var(--partner-gray-2);
  border-top: none;
  border-radius: 0 0 var(--partner-radius-md) var(--partner-radius-md);
}

.address-lookup__error {
  color: var(--partner-error-main);
  font-size: 0.8125rem;
  margin: 0.5rem 0 0;
}
</style>
