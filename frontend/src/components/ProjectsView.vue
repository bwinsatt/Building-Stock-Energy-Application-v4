<script setup>
import { ref, onMounted } from 'vue'
import { PButton, PTypography, PTextInput } from '@partnerdevops/partner-components'
import { useProjects } from '../composables/useProjects'
import ProjectDetail from './ProjectDetail.vue'
import SavedAssessmentView from './SavedAssessmentView.vue'

const { projects, loading, error, fetchProjects, createProject, deleteProject } = useProjects()

const selectedProjectId = ref(null)
const viewingAssessment = ref(null)

function onViewAssessment(building, assessment) {
  viewingAssessment.value = { building, assessment }
}

function onBackFromAssessment() {
  viewingAssessment.value = null
}
const showCreateInput = ref(false)
const newProjectName = ref('')
const creating = ref(false)

function selectProject(id) {
  selectedProjectId.value = id
}

function goBack() {
  selectedProjectId.value = null
  fetchProjects()
}

async function handleCreate() {
  if (creating.value) return
  const name = newProjectName.value.trim()
  if (!name) return
  creating.value = true
  try {
    await createProject(name)
    newProjectName.value = ''
    showCreateInput.value = false
  } finally {
    creating.value = false
  }
}

async function handleDelete(id, event) {
  event.stopPropagation()
  if (!confirm('Delete this project? This action cannot be undone.')) return
  await deleteProject(id)
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function handleKeydown(event) {
  if (event.key === 'Enter') handleCreate()
  if (event.key === 'Escape') {
    showCreateInput.value = false
    newProjectName.value = ''
  }
}

onMounted(() => {
  fetchProjects()
})
</script>

<template>
  <!-- Saved assessment view -->
  <SavedAssessmentView
    v-if="viewingAssessment"
    :building="viewingAssessment.building"
    :assessment="viewingAssessment.assessment"
    @back="onBackFromAssessment"
  />

  <!-- Detail view -->
  <ProjectDetail
    v-else-if="selectedProjectId !== null"
    :project-id="selectedProjectId"
    @back="goBack"
    @view-assessment="onViewAssessment"
  />

  <!-- List view -->
  <div v-else class="projects-view">
    <!-- Toolbar -->
    <div class="projects-toolbar">
      <PTypography variant="h4" class="projects-title">Projects</PTypography>
      <PButton
        v-if="!showCreateInput"
        variant="primary"
        size="medium"
        icon="add"
        @click="showCreateInput = true"
      >
        New Project
      </PButton>
    </div>

    <!-- Inline create form -->
    <div v-if="showCreateInput" class="create-form">
      <PTextInput
        v-model="newProjectName"
        placeholder="Project name"
        :disabled="creating"
        class="create-input"
        @keydown="handleKeydown"
      />
      <PButton
        variant="primary"
        size="medium"
        :disabled="creating || !newProjectName.trim()"
        @click="handleCreate"
      >
        {{ creating ? 'Creating...' : 'Create' }}
      </PButton>
      <PButton
        variant="neutral"
        appearance="outlined"
        size="medium"
        :disabled="creating"
        @click="showCreateInput = false; newProjectName = ''"
      >
        Cancel
      </PButton>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="state-box">
      <PTypography variant="body2" class="state-text">Loading projects...</PTypography>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-box">
      <PTypography variant="body2" class="error-text">{{ error }}</PTypography>
    </div>

    <!-- Empty state -->
    <div v-else-if="projects.length === 0 && !showCreateInput" class="empty-box">
      <PTypography variant="body1" class="empty-text">No projects yet.</PTypography>
      <PTypography variant="body2" class="empty-subtext">Create a project to start saving energy audit results.</PTypography>
    </div>

    <!-- Project cards -->
    <div v-else class="project-list">
      <div
        v-for="project in projects"
        :key="project.id"
        class="project-card"
        @click="selectProject(project.id)"
      >
        <div class="project-card__body">
          <PTypography variant="body1" class="project-name">{{ project.name }}</PTypography>
          <PTypography variant="body2" class="project-meta">
            Created {{ formatDate(project.created_at) }}
            <template v-if="project.buildings && project.buildings.length > 0">
              &middot; {{ project.buildings.length }} building{{ project.buildings.length === 1 ? '' : 's' }}
            </template>
          </PTypography>
        </div>
        <PButton
          variant="error"
          appearance="text"
          size="small"
          icon="close"
          icon-button
          title="Delete project"
          @click="handleDelete(project.id, $event)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.projects-view {
  font-family: 'Roboto', system-ui, -apple-system, sans-serif;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* Toolbar */
.projects-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.projects-title {
  color: var(--partner-text, #333e47);
  margin: 0;
}

/* Create form */
.create-form {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.create-input {
  flex: 1;
  max-width: 24rem;
}

/* State boxes */
.state-box,
.empty-box {
  background: var(--partner-background-white, #ffffff);
  border: 1px solid var(--partner-border-default, #a6adb4);
  border-radius: var(--partner-radius-md, 4px);
  padding: 3rem 1.5rem;
  text-align: center;
}

.state-text {
  color: var(--partner-gray-6, #6f7881);
}

.error-box {
  background: #fef2f2;
  border: 1px solid var(--partner-error-main, #B71C1C);
  border-radius: var(--partner-radius-md, 4px);
  padding: 1rem 1.25rem;
}

.error-text {
  color: var(--partner-error-main, #B71C1C);
}

.empty-text {
  color: var(--partner-gray-6, #6f7881);
  margin-bottom: 0.25rem;
}

.empty-subtext {
  color: var(--partner-gray-5, #a6adb4);
}

/* Project list */
.project-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.project-card {
  background: var(--partner-background-white, #ffffff);
  border: 1px solid var(--partner-border-default, #a6adb4);
  border-radius: var(--partner-radius-md, 4px);
  padding: 0.875rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.project-card:hover {
  border-color: var(--partner-primary-main, #005199);
  box-shadow: var(--partner-shadow-sm, 0px 1px 4px rgba(0,0,0,0.16));
}

.project-card__body {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.project-name {
  font-weight: 500;
  color: var(--partner-text, #333e47);
}

.project-meta {
  color: var(--partner-gray-5, #a6adb4);
}
</style>
