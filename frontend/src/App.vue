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
        <span class="p-header-role">DB Admin</span>
        <div class="p-avatar">BW</div>
      </div>
    </div>

    <!-- Main content -->
    <main class="app-container py-8">
      <AssessmentView />
    </main>
  </div>
</template>

<script setup lang="ts">
import AssessmentView from './views/AssessmentView.vue'
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
