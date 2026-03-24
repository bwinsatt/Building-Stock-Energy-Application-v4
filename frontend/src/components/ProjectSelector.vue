<script setup>
import { ref, onMounted } from 'vue'
import { useProjects } from '../composables/useProjects'

const emit = defineEmits(['update:projectId'])

const { projects, fetchProjects, createProject } = useProjects()
const selectedId = ref(null)
const creatingNew = ref(false)
const newName = ref('')

onMounted(() => {
  fetchProjects()
})

function onSelect(event) {
  const val = event.target.value
  if (val === '__new__') {
    creatingNew.value = true
    selectedId.value = null
    emit('update:projectId', null)
  } else if (val) {
    selectedId.value = Number(val)
    creatingNew.value = false
    emit('update:projectId', selectedId.value)
  } else {
    selectedId.value = null
    creatingNew.value = false
    emit('update:projectId', null)
  }
}

async function onCreateProject() {
  if (!newName.value.trim()) return
  const project = await createProject(newName.value.trim())
  selectedId.value = project.id
  creatingNew.value = false
  newName.value = ''
  emit('update:projectId', project.id)
}
</script>

<template>
  <div class="project-selector">
    <label class="project-selector__label">Save to Project</label>
    <div class="project-selector__row">
      <select
        class="project-selector__select"
        :value="creatingNew ? '__new__' : (selectedId ?? '')"
        @change="onSelect"
      >
        <option value="">None (don't save)</option>
        <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        <option value="__new__">+ New Project...</option>
      </select>
      <div v-if="creatingNew" class="project-selector__new">
        <input
          v-model="newName"
          class="project-selector__input"
          placeholder="Project name"
          @keyup.enter="onCreateProject"
        />
        <button class="project-selector__create-btn" @click="onCreateProject" :disabled="!newName.trim()">
          Create
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.project-selector {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}
.project-selector__label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--partner-text-secondary, #5f6d79);
}
.project-selector__row {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  flex-wrap: wrap;
}
.project-selector__select {
  height: 2rem;
  border-radius: 2px;
  border: 1px solid var(--partner-border-default, #c4cdd5);
  background-color: transparent;
  padding: 0 2rem 0 0.75rem;
  font-family: inherit;
  font-size: 0.875rem;
  color: var(--partner-text-primary, #333e47);
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%235f6d79' d='M2.5 4.5L6 8l3.5-3.5'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.625rem center;
  background-size: 12px;
  cursor: pointer;
  min-width: 12rem;
}
.project-selector__select:focus {
  border-color: var(--partner-border-active, var(--app-accent));
  outline: none;
  box-shadow: 0 0 0 1px var(--partner-border-active, var(--app-accent));
}
.project-selector__new {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.project-selector__input {
  height: 2rem;
  border-radius: 2px;
  border: 1px solid var(--partner-border-default, #c4cdd5);
  padding: 0 0.75rem;
  font-family: inherit;
  font-size: 0.875rem;
  color: var(--partner-text-primary, #333e47);
  min-width: 10rem;
}
.project-selector__input:focus {
  border-color: var(--partner-border-active, var(--app-accent));
  outline: none;
  box-shadow: 0 0 0 1px var(--partner-border-active, var(--app-accent));
}
.project-selector__create-btn {
  height: 2rem;
  padding: 0 0.75rem;
  border-radius: 2px;
  border: none;
  background: var(--app-accent, #005199);
  color: #fff;
  font-family: inherit;
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}
.project-selector__create-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.project-selector__create-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
