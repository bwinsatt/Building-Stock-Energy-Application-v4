import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function useProjects() {
  const projects = ref([])
  const currentProject = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchProjects() {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(`${API_BASE}/projects`)
      projects.value = await resp.json()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchProject(id) {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(`${API_BASE}/projects/${id}`)
      if (!resp.ok) throw new Error('Project not found')
      currentProject.value = await resp.json()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createProject(name) {
    const resp = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    const project = await resp.json()
    await fetchProjects()
    return project
  }

  async function deleteProject(id) {
    await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' })
    projects.value = projects.value.filter(p => p.id !== id)
    if (currentProject.value?.id === id) {
      currentProject.value = null
    }
  }

  async function createBuilding(
    projectId, address,
    buildingInput,
    utilityData,
    lookupData,
  ) {
    const resp = await fetch(`${API_BASE}/projects/${projectId}/buildings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        address,
        building_input: buildingInput,
        utility_data: utilityData,
        lookup_data: lookupData,
      }),
    })
    if (!resp.ok) throw new Error('Failed to create building')
    return await resp.json()
  }

  async function fetchBuilding(projectId, buildingId) {
    const resp = await fetch(`${API_BASE}/projects/${projectId}/buildings/${buildingId}`)
    if (!resp.ok) throw new Error('Building not found')
    return await resp.json()
  }

  async function saveAssessment(
    projectId, buildingId,
    result, calibrated,
  ) {
    const resp = await fetch(
      `${API_BASE}/projects/${projectId}/buildings/${buildingId}/assessments`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ result, calibrated }),
      },
    )
    if (!resp.ok) throw new Error('Failed to save assessment')
    return await resp.json()
  }

  return {
    projects, currentProject, loading, error,
    fetchProjects, fetchProject, createProject,
    deleteProject, createBuilding, fetchBuilding, saveAssessment,
  }
}
