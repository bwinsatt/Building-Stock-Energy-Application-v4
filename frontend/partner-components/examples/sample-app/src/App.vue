<template>
  <div class="min-h-screen bg-background p-8">
    <div class="max-w-4xl mx-auto">
      <h1 class="text-3xl font-bold text-foreground mb-8">
        Partner Components - Sample Application
      </h1>

      <!-- Theme Controls -->
      <div class="bg-card rounded-lg shadow-md p-6 mb-8">
        <h2 class="text-xl font-semibold mb-4 text-card-foreground">
          Theme Controls
        </h2>
        <p class="text-muted-foreground mb-4">
          Toggle between light and dark mode:
        </p>
        <div class="flex flex-wrap gap-4">
          <button
            class="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
            @click="setLightMode"
          >
            ☀️ Light Mode
          </button>
          <button
            class="px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors"
            @click="setDarkMode"
          >
            🌙 Dark Mode
          </button>
        </div>
      </div>

      <!-- Component Examples -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        <!-- Component -->
        <div class="bg-card rounded-lg shadow-md p-6">
          <h2 class="text-xl font-semibold mb-4 text-card-foreground">
            Component
          </h2>
          <div class="space-y-3 space-x-3">
            Component examples will go here
          </div>
        </div>

        <!-- Cards -->
        <div class="bg-card rounded-lg shadow-md p-6">
          <h2 class="text-xl font-semibold mb-4 text-card-foreground">
            Cards
          </h2>
          <PCard>
            <h3 class="text-lg font-semibold mb-2">
              Sample Card
            </h3>
            <p class="text-muted-foreground">
              This is a sample card that adapts to light and dark mode.
            </p>
          </PCard>
        </div>

        <!-- Inputs -->
        <div class="bg-card rounded-lg shadow-md p-6">
          <h2 class="text-xl font-semibold mb-4 text-card-foreground">
            Inputs
          </h2>
          <div class="space-y-3">
            <PInput
              placeholder="Primary input"
              color="primary"
            />
            <PInput
              placeholder="Secondary input"
              color="secondary"
            />
            <PInput
              placeholder="Success input"
              color="success"
            />
          </div>
        </div>

        <!-- Modal -->
        <div class="bg-card rounded-lg shadow-md p-6">
          <h2 class="text-xl font-semibold mb-4 text-card-foreground">
            Modal
          </h2>
          Open Modal example will go here
        </div>
      </div>

      <!-- Theme Demonstration -->
      <div class="bg-card rounded-lg shadow-md p-6 mt-8">
        <h2 class="text-xl font-semibold mb-4 text-card-foreground">
          🎨 Theme-Aware Components
        </h2>
        <p class="text-muted-foreground mb-6">
          <strong>Click the theme buttons above</strong> to see how components automatically adapt between light and dark mode.
        </p>

        <!-- Live Theme Examples -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <!-- Background Examples -->
          <div class="space-y-4">
            <h3 class="font-medium text-foreground">
              Background Colors
            </h3>
            <div class="space-y-2">
              <div class="bg-muted text-muted-foreground px-3 py-2 rounded text-sm">
                <code>bg-muted text-muted-foreground</code>
              </div>
              <div class="bg-accent text-accent-foreground px-3 py-2 rounded text-sm">
                <code>bg-accent text-accent-foreground</code>
              </div>
              <div class="bg-primary text-primary-foreground px-3 py-2 rounded text-sm">
                <code>bg-primary text-primary-foreground</code>
              </div>
            </div>
          </div>

          <!-- Interactive Elements -->
          <div class="space-y-4">
            <h3 class="font-medium text-foreground">
              Interactive Elements
            </h3>
            <div class="space-y-3">
              <button
                class="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded transition-colors w-full text-sm"
              >
                <code>hover:bg-primary/90</code> (hover me!)
              </button>
              <button
                class="border border-input bg-background hover:bg-accent hover:text-accent-foreground px-4 py-2 rounded transition-colors w-full text-sm"
              >
                <code>hover:bg-accent</code>
              </button>
              <div class="bg-destructive/10 text-destructive border border-destructive/20 px-3 py-2 rounded text-sm text-center">
                <code>bg-destructive/10</code>
              </div>
            </div>
          </div>
        </div>

        <!-- Current Theme Info -->
        <div class="pt-6 border-t border-border">
          <h3 class="font-medium mb-3 text-foreground">
            Current Theme: <span class="text-primary">{{ currentTheme }}</span>
          </h3>
          <p class="text-sm text-muted-foreground">
            The <code>data-mode</code> attribute on the document root controls light/dark mode for all components.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue'

  const setLightMode = () => {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-mode', 'light')
    }
  }

  const setDarkMode = () => {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-mode', 'dark')
    }
  }

  const currentTheme = computed(() => {
    if (typeof document !== 'undefined') {
      return document.documentElement.getAttribute('data-mode') || 'light'
    }
    return 'light'
  })
</script>
