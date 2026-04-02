<script setup>
import { ref, onMounted } from 'vue'
import { PButton, PTypography, PIcon, PBadge } from '@partnerdevops/partner-components'
import { useProjects } from '../composables/useProjects'

const props = defineProps({
  projectId: { type: Number, required: true },
})
const emit = defineEmits(['back', 'view-assessment'])

const { currentProject, loading, error, fetchProject } = useProjects()

const expandedBuildingId = ref(null)

function toggleBuilding(building) {
  expandedBuildingId.value = expandedBuildingId.value === building.id ? null : building.id
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

onMounted(() => {
  fetchProject(props.projectId)
})
</script>

<template>
  <div class="project-detail">
    <!-- Header -->
    <div class="detail-header">
      <PButton
        variant="primary"
        appearance="text"
        size="small"
        class="back-btn"
        @click="emit('back')"
      >
        <PIcon name="arrow-left" size="small" />
        Back to Projects
      </PButton>
      <PTypography variant="h4" class="detail-title">{{ currentProject?.name ?? 'Loading...' }}</PTypography>
      <span v-if="currentProject" class="detail-meta">
        Created {{ formatDate(currentProject.created_at) }}
      </span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="state-box">
      <p class="state-text">Loading project...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-box">
      <p class="error-text">{{ error }}</p>
    </div>

    <!-- Content -->
    <template v-else-if="currentProject">
      <div class="section-label">Buildings</div>

      <!-- Empty state -->
      <div
        v-if="!currentProject.buildings || currentProject.buildings.length === 0"
        class="empty-box"
      >
        <p class="empty-text">No buildings yet.</p>
        <p class="empty-subtext">Buildings added during an energy audit will appear here.</p>
      </div>

      <!-- Building list -->
      <div v-else class="building-list">
        <div
          v-for="building in currentProject.buildings"
          :key="building.id"
          class="building-card"
        >
          <button
            class="building-row"
            @click="toggleBuilding(building)"
          >
            <div class="building-info">
              <span class="building-address">{{ building.address }}</span>
              <span class="building-date">Added {{ formatDate(building.created_at) }}</span>
            </div>
            <PIcon
              :name="expandedBuildingId === building.id ? 'chevron-down' : 'chevron-right'"
              size="small"
              class="chevron-icon"
            />
          </button>

          <!-- Expanded: assessment history -->
          <div v-if="expandedBuildingId === building.id" class="assessment-section">
            <template v-if="building.assessments && building.assessments.length > 0">
              <div
                v-for="assessment in building.assessments"
                :key="assessment.id"
                class="assessment-row"
                @click="emit('view-assessment', building, assessment)"
              >
                <div class="assessment-row__info">
                  <span class="assessment-row__date">{{ formatDate(assessment.created_at) }}</span>
                  <PBadge v-if="assessment.calibrated" variant="success" appearance="standard">Calibrated</PBadge>
                  <span v-if="assessment.result?.baseline" class="assessment-row__eui">
                    {{ assessment.result.baseline?.total_eui_kbtu_sf?.toFixed(1) }} kBtu/sf
                  </span>
                </div>
                <PIcon name="chevron-right" size="small" class="arrow-icon" />
              </div>
            </template>
            <p v-else class="assessment-empty">No assessments saved for this building yet.</p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.project-detail {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* Header */
.detail-header {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.back-btn {
  align-self: flex-start;
  margin-bottom: 0.5rem;
}

.detail-title {
  color: var(--partner-gray-7);
  margin: 0;
}

.detail-meta {
  font-size: 0.75rem;
  color: var(--partner-gray-6);
}

/* Section label */
.section-label {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--partner-gray-6);
}

/* State boxes */
.state-box,
.empty-box {
  background: var(--partner-background-white);
  border: 1px solid var(--partner-border-light);
  border-radius: var(--partner-radius-lg);
  padding: 2.5rem 1.5rem;
  text-align: center;
}

.state-text {
  font-size: 0.875rem;
  color: var(--partner-gray-5);
}

.error-box {
  background: var(--partner-red-1);
  border: 1px solid var(--partner-red-3);
  border-radius: var(--partner-radius-lg);
  padding: 1rem 1.25rem;
}

.error-text {
  font-size: 0.875rem;
  color: var(--partner-error-main);
}

.empty-text {
  font-size: 0.9375rem;
  color: var(--partner-gray-6);
  margin-bottom: 0.25rem;
}

.empty-subtext {
  font-size: 0.8125rem;
  color: var(--partner-gray-5);
}

/* Building list */
.building-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.building-card {
  background: var(--partner-background-white);
  border: 1px solid var(--partner-border-light);
  border-radius: var(--partner-radius-lg);
  overflow: hidden;
}

.building-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0.875rem 1rem;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}

.building-row:hover {
  background: var(--partner-gray-1);
}

.building-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.building-address {
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--partner-gray-7);
}

.building-date {
  font-size: 0.75rem;
  color: var(--partner-gray-5);
}

.chevron-icon {
  color: var(--partner-gray-5);
}

/* Assessment section */
.assessment-section {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--partner-border-light);
  background: var(--partner-gray-1);
}

.assessment-empty {
  font-size: 0.8125rem;
  color: var(--partner-gray-5);
  text-align: center;
  padding: 0.5rem 0;
}

.assessment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  border-radius: var(--partner-radius-md);
  transition: background 0.1s;
}
.assessment-row:hover { background: var(--partner-gray-2); }
.assessment-row__info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.assessment-row__date {
  font-size: 0.8125rem;
  color: var(--partner-gray-7);
  font-weight: 500;
}
.assessment-row__eui {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--partner-gray-6);
}
.arrow-icon {
  color: var(--partner-gray-5);
}
</style>
