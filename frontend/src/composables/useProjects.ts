import { ref } from 'vue'
import type { Project, Building, Assessment } from '../types/projects'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'

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
    } catch (e: unknown) {
      error.value = (e as Error).message
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
    } catch (e: unknown) {
      error.value = (e as Error).message
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
    const project: Project = await resp.json()
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
    projectId: number,
    address: string,
    buildingInput: Record<string, unknown>,
    utilityData?: Record<string, unknown>,
  ): Promise<Building> {
    const resp = await fetch(`${API_BASE}/projects/${projectId}/buildings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        address,
        building_input: buildingInput,
        utility_data: utilityData,
      }),
    })
    return await resp.json()
  }

  async function saveAssessment(
    projectId: number,
    buildingId: number,
    result: Record<string, unknown>,
    calibrated: boolean,
  ): Promise<Assessment> {
    const resp = await fetch(
      `${API_BASE}/projects/${projectId}/buildings/${buildingId}/assessments`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ result, calibrated }),
      },
    )
    return await resp.json()
  }

  return {
    projects,
    currentProject,
    loading,
    error,
    fetchProjects,
    fetchProject,
    createProject,
    deleteProject,
    createBuilding,
    saveAssessment,
  }
}
