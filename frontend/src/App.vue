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
        <a class="p-header-nav-link">Projects</a>
        <a class="p-header-nav-link active">Energy Audit Lite</a>
      </div>
      <div class="p-header-right">
        <button class="p-offload-btn" title="Free model memory" @click="offloadModels" :disabled="offloading">
          {{ offloading ? 'Freeing...' : 'Free Memory' }}
        </button>
        <span class="p-header-role">DB Admin</span>
        <div class="p-avatar">BW</div>
      </div>
    </div>

    <!-- Main content -->
    <main class="app-container py-8">
      <nav class="flex gap-1 border-b border-gray-200 mb-6">
        <button
          @click="currentView = 'assessment'"
          :class="[
            'px-4 py-2 text-sm font-medium rounded-t-lg transition-colors',
            currentView === 'assessment'
              ? 'bg-white text-blue-600 border border-b-white -mb-px'
              : 'text-gray-500 hover:text-gray-700'
          ]"
        >
          Energy Audit
        </button>
        <button
          @click="currentView = 'projects'"
          :class="[
            'px-4 py-2 text-sm font-medium rounded-t-lg transition-colors',
            currentView === 'projects'
              ? 'bg-white text-blue-600 border border-b-white -mb-px'
              : 'text-gray-500 hover:text-gray-700'
          ]"
        >
          Projects
        </button>
      </nav>
      <AssessmentView v-if="currentView === 'assessment'" />
      <ProjectsView v-if="currentView === 'projects'" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AssessmentView from './views/AssessmentView.vue'
import ProjectsView from './components/ProjectsView.vue'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'
const offloading = ref(false)
const currentView = ref<'assessment' | 'projects'>('assessment')

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
  background: var(--partner-white, #ffffff);
  border-bottom: 1px solid var(--partner-gray-5, #a6adb4);
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
  color: var(--partner-blue-7, #005199);
  letter-spacing: 0.5px;
}

.p-logo-sub {
  font-size: 0.625rem;
  color: var(--partner-gray-6, #6f7881);
  letter-spacing: 0.026rem;
  text-transform: uppercase;
}

.p-header-nav-link {
  text-decoration: none;
  color: var(--partner-gray-6, #6f7881);
  font-weight: 500;
  font-size: 0.875rem;
  padding: 0.375rem 0;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
  cursor: pointer;
}

.p-header-nav-link:hover {
  color: var(--partner-blue-7, #005199);
}

.p-header-nav-link.active {
  color: var(--partner-blue-7, #005199);
  border-bottom-color: var(--partner-blue-7, #005199);
}

.p-header-role {
  font-weight: 400;
  font-size: 0.75rem;
  color: var(--partner-gray-6, #6f7881);
}

.p-offload-btn {
  font-family: var(--font-mono, monospace);
  font-size: 0.6875rem;
  color: #6f7881;
  background: transparent;
  border: 1px solid #c4cdd5;
  border-radius: 3px;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  transition: all 0.15s;
}

.p-offload-btn:hover:not(:disabled) {
  color: #005199;
  border-color: #005199;
}

.p-offload-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.p-avatar {
  width: 2rem;
  height: 2rem;
  border-radius: 9999px;
  background: var(--partner-blue-7, #005199);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.75rem;
}
</style>
