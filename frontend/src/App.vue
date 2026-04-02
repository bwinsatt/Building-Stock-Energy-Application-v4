<template>
  <div class="min-h-screen" :style="{ backgroundColor: 'var(--app-surface)' }">
    <!-- SiteLynx Header -->
    <div class="p-header">
      <div class="p-header-left">
        <div>
          <div class="p-logo-text">SITELYNX</div>
          <div class="p-logo-sub">Partner Engineering</div>
        </div>
      </div>
      <div class="p-header-center">
        <a class="p-header-nav-link">Home</a>
        <a class="p-header-nav-link">Services</a>
        <a class="p-header-nav-link">Properties</a>
        <a class="p-header-nav-link" :class="{ active: currentView === 'projects' }" @click="currentView = 'projects'">Projects</a>
        <a class="p-header-nav-link" :class="{ active: currentView === 'assessment' }" @click="currentView = 'assessment'">Energy Audit Lite</a>
      </div>
      <div class="p-header-right">
        <PButton variant="neutral" appearance="outlined" size="small" :disabled="offloading" @click="offloadModels">
          {{ offloading ? 'Freeing...' : 'Free Memory' }}
        </PButton>
        <span class="p-header-role">DB Admin</span>
        <PAvatar initials="BW" size="small" />
      </div>
    </div>

    <!-- Main content -->
    <main class="app-container py-8">
      <AssessmentView v-if="currentView === 'assessment'" />
      <ProjectsView v-if="currentView === 'projects'" />
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { PButton, PAvatar } from '@partnerdevops/partner-components'
import AssessmentView from './views/AssessmentView.vue'
import ProjectsView from './components/ProjectsView.vue'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'
const offloading = ref(false)
const currentView = ref('assessment')

async function offloadModels() {
  offloading.value = true
  try {
    await fetch(`${API_BASE}/offload`, { method: 'POST' })
  } finally {
    offloading.value = false
  }
}
</script>

<style scoped>
.p-header {
  height: 53px;
  background: var(--partner-white);
  border-bottom: 1px solid var(--partner-gray-5);
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  padding: 0 1rem;
  font-family: 'Roboto', system-ui, -apple-system, sans-serif;
}

.p-header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.p-header-center {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.p-header-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 1rem;
}

.p-logo-text {
  font-weight: 700;
  font-size: 1.125rem;
  color: var(--partner-blue-7);
  letter-spacing: 0.5px;
}

.p-logo-sub {
  font-size: 0.625rem;
  color: var(--partner-gray-6);
  letter-spacing: 0.026rem;
  text-transform: uppercase;
}

.p-header-nav-link {
  text-decoration: none;
  color: var(--partner-gray-6);
  font-weight: 500;
  font-size: 0.875rem;
  padding: 0.375rem 0;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
  cursor: pointer;
}

.p-header-nav-link:hover {
  color: var(--partner-blue-7);
}

.p-header-nav-link.active {
  color: var(--partner-blue-7);
  border-bottom-color: var(--partner-blue-7);
}

.p-header-role {
  font-weight: 400;
  font-size: 0.75rem;
  color: var(--partner-gray-6);
}
</style>
