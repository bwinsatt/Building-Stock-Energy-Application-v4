<script setup>
import { computed, ref } from 'vue'
import { PTypography } from '@partnerdevops/partner-components'
import BaselineSummary from './BaselineSummary.vue'
import MeasuresTable from './MeasuresTable.vue'
import AssumptionsPanel from './AssumptionsPanel.vue'
import EnergyStarScore from './EnergyStarScore.vue'
import BuildingMapViewer from './BuildingMapViewer.vue'
import { useMeasureSelections } from '../composables/useMeasureSelections'

const props = defineProps({
  building: { type: Object, required: true },
  assessment: { type: Object, required: true },
})

const emit = defineEmits(['back'])

const buildingResult = computed(() => {
  return props.assessment.result ?? null
})

const buildingInput = computed(() => {
  return props.building.building_input
})

const sqft = computed(() => buildingInput.value?.sqft ?? 0)

const baseline = computed(() => buildingResult.value?.baseline ?? null)
const measures = computed(() => buildingResult.value?.measures ?? [])
const inputSummary = computed(() => buildingResult.value?.input_summary ?? null)
const calibrated = computed(() => props.assessment.calibrated)

// Map data from lookup_data stored on the building
const lookupData = computed(() => props.building.lookup_data)

const buildingIdRef = computed(() => props.building.id ?? null)
const projectIdRef = computed(() => props.building.project_id ?? null)
const addressRef = computed(() => props.building.address ?? null)

const {
  selectedUpgradeIds,
  disabledByPackage,
  projectedEui,
  projectedEspm,
  projectedLoading,
  projectedError,
  toggleMeasure,
  loadSelections,
  reconcileSelections,
  calculateProjectedScore,
} = useMeasureSelections(measures, baseline, buildingInput, buildingIdRef, addressRef, projectIdRef)

const replaceMessage = ref(null)
let replaceTimer = null

function handleToggleMeasure(upgradeId) {
  const res = toggleMeasure(upgradeId)
  if (res?.action === 'replace' && res.replaced) {
    const names = res.replaced
      .map(id => measures.value.find(m => m.upgrade_id === id)?.name)
      .filter(Boolean)
    replaceMessage.value = `Replaced ${names.join(', ')} with package`
    if (replaceTimer) clearTimeout(replaceTimer)
    replaceTimer = setTimeout(() => { replaceMessage.value = null }, 4000)
  } else {
    replaceMessage.value = null
  }
}

// Load selections on mount
loadSelections().then(() => reconcileSelections())
</script>

<template>
  <div class="saved-assessment">
    <button class="back-btn" @click="emit('back')">&larr; Back to Project</button>

    <div class="saved-assessment__header">
      <PTypography variant="h4">{{ building.address }}</PTypography>
      <span class="saved-assessment__date">
        Assessment from {{ new Date(assessment.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) }}
      </span>
    </div>

    <!-- Map -->
    <BuildingMapViewer
      v-if="lookupData?.target_building_polygon"
      :lat="lookupData.lat"
      :lon="lookupData.lon"
      :target-polygon="lookupData.target_building_polygon"
      :nearby-buildings="lookupData.nearby_buildings"
      :num-stories="Number(buildingInput?.num_stories ?? 1)"
    />

    <!-- Results -->
    <template v-if="buildingResult && baseline">
      <AssumptionsPanel v-if="inputSummary" :summary="inputSummary" />
      <BaselineSummary :baseline="baseline" :sqft="sqft" :calibrated="calibrated" />
      <EnergyStarScore
        :building="buildingInput"
        :baseline="baseline"
        :address="building.address"
        :selected-count="selectedUpgradeIds.size"
        :projected-eui="projectedEui"
        :projected-espm="projectedEspm"
        :projected-loading="projectedLoading"
        :projected-error="projectedError"
        @calculate-projected="calculateProjectedScore"
      />
      <div class="section-separator" aria-hidden="true" />
      <MeasuresTable
        :measures="measures"
        :sqft="sqft"
        :selected-upgrade-ids="selectedUpgradeIds"
        :disabled-by-package="disabledByPackage"
        :replace-message="replaceMessage"
        @toggle-measure="handleToggleMeasure"
      />
    </template>

    <div v-else class="empty-state">
      <p>Assessment data could not be loaded.</p>
    </div>
  </div>
</template>

<style scoped>
.saved-assessment {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.back-btn {
  align-self: flex-start;
  background: transparent;
  border: none;
  color: #005199;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  padding: 0;
}
.back-btn:hover { opacity: 0.75; }
.saved-assessment__header {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.saved-assessment__date {
  font-size: 0.8125rem;
  color: #64748b;
}
.section-separator {
  height: 1px;
  background: #e2e8f0;
  margin: 0.25rem 0;
}
.empty-state {
  text-align: center;
  padding: 2rem;
  color: #94a3b8;
}
</style>
