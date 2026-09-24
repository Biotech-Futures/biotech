<template>
  <div class="content-area management">
    <header class="management__hero">
      <div>
        <h1 class="management__title">Management</h1>
        <p class="management__subtitle">
          Set deadlines, grant extensions, manage documents, releases and the new year.
        </p>
      </div>
    </header>

    <nav class="management__switcher" role="tablist" aria-label="Management sections">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.to"
        :to="tab.to"
        role="tab"
        :aria-selected="route.path.startsWith(tab.to)"
        class="management__switch"
        :class="{ active: route.path.startsWith(tab.to) }"
      >
        {{ tab.label }}
      </RouterLink>
    </nav>

    <router-view />
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  { label: 'Submission Deadline', to: '/management/submission-deadline' },
  { label: 'Extend Deadline', to: '/management/extend-deadline' }
  // Hidden for now — pages still exist at their URLs; restore by uncommenting.
  // { label: 'Document Setup', to: '/management/document-setup' },
  // { label: 'Release Marks', to: '/management/release-marks' },
  // { label: 'Release Certificates', to: '/management/release-certificates' },
  // { label: 'Notify Finalists', to: '/management/notify-finalists' },
  // { label: 'New Year', to: '/management/new-year' }
]
</script>

<style scoped>
.management__hero {
  margin-bottom: 1.25rem;
}

.management__title {
  margin-bottom: 0.25rem;
}

.management__subtitle {
  color: var(--text-muted);
  margin: 0;
}

/* Same pill-bar treatment as the component switcher on the marking tables:
   one white rounded rail, the active option a solid green pill. */
.management__switcher {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.3rem;
  margin-bottom: 1.75rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  /* Not 999px: with the rail wrapped onto two rows a fully-round radius turns
     into a giant lozenge. 1.4rem still reads as a pill on a single row. */
  border-radius: 1.4rem;
  box-shadow: 0 1px 2px var(--shadow);
}

.management__switch {
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 0.5rem 1.1rem;
  font-weight: 600;
  font-size: 0.92rem;
  font-family: inherit;
  cursor: pointer;
  text-decoration: none;
  transition:
    color 0.18s ease,
    background-color 0.18s ease;
}

.management__switch:hover:not(.active) {
  color: var(--charcoal);
  background: var(--accent-green-soft);
}

.management__switch.active {
  background: var(--dark-green);
  color: #fff;
  box-shadow: 0 1px 3px rgba(1, 113, 81, 0.3);
}
</style>
