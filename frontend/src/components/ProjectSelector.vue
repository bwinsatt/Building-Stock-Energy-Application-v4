<script setup>
import { ref, computed, onMounted } from 'vue'
import { PSelect, PTextInput, PButton, PLabel } from '@partnerdevops/partner-components'
import { useProjects } from '../composables/useProjects'

const emit = defineEmits(['update:projectId'])

const { projects, fetchProjects, createProject } = useProjects()
const selectedId = ref(null)
const creatingNew = ref(false)
const newName = ref('')

onMounted(() => {
  fetchProjects()
})

const selectItems = computed(() => {
  const items = [
    { label: "None (don't save)", modelValue: '' },
    ...projects.value.map(p => ({ label: p.name, modelValue: String(p.id) })),
    { label: '+ New Project...', modelValue: '__new__' },
  ]
  return items
})

const selectedLabel = computed(() => {
  if (creatingNew.value) return '+ New Project...'
  if (!selectedId.value) return "None (don't save)"
  const project = projects.value.find(p => p.id === selectedId.value)
  return project?.name ?? "None (don't save)"
})

function onApply(items) {
  const val = items[0]?.modelValue ?? ''
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
    <PLabel>Save to Project</PLabel>
    <div class="project-selector__row">
      <PSelect
        :items="selectItems"
        :model-value="selectedLabel"
        placeholder="Select a project"
        size="small"
        @apply="onApply"
      />
      <div v-if="creatingNew" class="project-selector__new">
        <PTextInput
          v-model="newName"
          placeholder="Project name"
          size="small"
          @keyup.enter="onCreateProject"
        />
        <PButton
          variant="primary"
          appearance="contained"
          size="small"
          :disabled="!newName.trim()"
          @click="onCreateProject"
        >
          Create
        </PButton>
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
.project-selector__row {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  flex-wrap: wrap;
}
.project-selector__new {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
</style>
