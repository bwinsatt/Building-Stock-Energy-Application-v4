<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useProjects } from '../composables/useProjects'
import ProjectDetail from './ProjectDetail.vue'

const { projects, loading, error, fetchProjects, createProject, deleteProject } = useProjects()

const selectedProjectId = ref<number | null>(null)
const showCreateInput = ref(false)
const newProjectName = ref('')
const creating = ref(false)

function selectProject(id: number) {
  selectedProjectId.value = id
}

function goBack() {
  selectedProjectId.value = null
  fetchProjects()
}

async function handleCreate() {
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

async function handleDelete(id: number, event: MouseEvent) {
  event.stopPropagation()
  if (!confirm('Delete this project? This action cannot be undone.')) return
  await deleteProject(id)
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function handleKeydown(event: KeyboardEvent) {
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
  <!-- Detail view -->
  <ProjectDetail
    v-if="selectedProjectId !== null"
    :project-id="selectedProjectId"
    @back="goBack"
  />

  <!-- List view -->
  <div v-else class="projects-view">
    <!-- Toolbar -->
    <div class="projects-toolbar">
      <h2 class="projects-title">Projects</h2>
      <button
        v-if="!showCreateInput"
        class="btn-primary"
        @click="showCreateInput = true"
      >
        + New Project
      </button>
    </div>

    <!-- Inline create form -->
    <div v-if="showCreateInput" class="create-form">
      <input
        v-model="newProjectName"
        class="create-input"
        placeholder="Project name"
        autofocus
        :disabled="creating"
        @keydown="handleKeydown"
      />
      <button
        class="btn-primary"
        :disabled="creating || !newProjectName.trim()"
        @click="handleCreate"
      >
        {{ creating ? 'Creating...' : 'Create' }}
      </button>
      <button
        class="btn-ghost"
        :disabled="creating"
        @click="showCreateInput = false; newProjectName = ''"
      >
        Cancel
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="state-box">
      <p class="state-text">Loading projects...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-box">
      <p class="error-text">{{ error }}</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="projects.length === 0 && !showCreateInput" class="empty-box">
      <p class="empty-text">No projects yet.</p>
      <p class="empty-subtext">Create a project to start saving energy audit results.</p>
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
          <span class="project-name">{{ project.name }}</span>
          <span class="project-meta">
            Created {{ formatDate(project.created_at) }}
            <template v-if="project.buildings && project.buildings.length > 0">
              &middot; {{ project.buildings.length }} building{{ project.buildings.length === 1 ? '' : 's' }}
            </template>
          </span>
        </div>
        <button
          class="delete-btn"
          title="Delete project"
          @click="handleDelete(project.id, $event)"
        >
          &times;
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.projects-view {
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
  font-size: 1.25rem;
  font-weight: 600;
  color: #333e47;
  margin: 0;
}

/* Buttons */
.btn-primary {
  background: #005199;
  color: #ffffff;
  border: none;
  border-radius: 0.375rem;
  padding: 0.4375rem 0.875rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-primary:hover:not(:disabled) {
  background: #003f78;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-ghost {
  background: transparent;
  color: #6f7881;
  border: 1px solid #c4cdd5;
  border-radius: 0.375rem;
  padding: 0.4375rem 0.875rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-ghost:hover:not(:disabled) {
  color: #333e47;
  border-color: #6f7881;
}

.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
  border: 1px solid #c4cdd5;
  border-radius: 0.375rem;
  padding: 0.4375rem 0.75rem;
  font-size: 0.875rem;
  color: #333e47;
  outline: none;
  transition: border-color 0.15s;
}

.create-input:focus {
  border-color: #005199;
}

.create-input:disabled {
  background: #f8fafc;
}

/* State boxes */
.state-box,
.empty-box {
  background: var(--app-surface-raised, #ffffff);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 3rem 1.5rem;
  text-align: center;
}

.state-text {
  font-size: 0.875rem;
  color: #94a3b8;
}

.error-box {
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
}

.error-text {
  font-size: 0.875rem;
  color: #dc2626;
}

.empty-text {
  font-size: 0.9375rem;
  color: #64748b;
  margin-bottom: 0.25rem;
}

.empty-subtext {
  font-size: 0.8125rem;
  color: #94a3b8;
}

/* Project list */
.project-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.project-card {
  background: var(--app-surface-raised, #ffffff);
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 0.875rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.project-card:hover {
  border-color: #005199;
  box-shadow: 0 1px 4px rgba(0, 81, 153, 0.1);
}

.project-card__body {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.project-name {
  font-size: 0.9375rem;
  font-weight: 500;
  color: #333e47;
}

.project-meta {
  font-size: 0.75rem;
  color: #94a3b8;
}

.delete-btn {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.25rem 0.375rem;
  border-radius: 0.25rem;
  transition: color 0.15s, background 0.15s;
}

.delete-btn:hover {
  color: #dc2626;
  background: #fef2f2;
}
</style>
