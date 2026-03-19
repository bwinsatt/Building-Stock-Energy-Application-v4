import { ref } from 'vue'
import type { Project } from '../types/projects'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function useProjects() {
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchProjects() {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(`${API_BASE}/projects`)
      projects.value = await resp.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchProject(id: number) {
    loading.value = true
    error.value = null
    try {
      const resp = await fetch(`${API_BASE}/projects/${id}`)
      if (!resp.ok) throw new Error('Project not found')
      currentProject.value = await resp.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createProject(name: string) {
    const resp = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    const project = await resp.json()
    projects.value.push(project)
    return project
  }

  async function deleteProject(id: number) {
    await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' })
    projects.value = projects.value.filter(p => p.id !== id)
    if (currentProject.value?.id === id) {
      currentProject.value = null
    }
  }

  async function createBuilding(
    projectId: number, address: string,
    buildingInput: Record<string, unknown>,
    utilityData?: Record<string, unknown>,
    lookupData?: Record<string, unknown>,
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

  async function fetchBuilding(projectId: number, buildingId: number) {
    const resp = await fetch(`${API_BASE}/projects/${projectId}/buildings/${buildingId}`)
    if (!resp.ok) throw new Error('Building not found')
    return await resp.json()
  }

  async function saveAssessment(
    projectId: number, buildingId: number,
    result: Record<string, unknown>, calibrated: boolean,
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
