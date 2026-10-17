<template>
  <div class="content-area management">
    <header class="page-header">
      <h1 class="page-title">Management</h1>
      <p class="page-subtitle">
        Set deadlines, grant extensions, manage documents, releases and the new year.
      </p>
    </header>

    <nav class="tab-bar" role="tablist" aria-label="Management sections">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.to"
        :to="tab.to"
        role="tab"
        :aria-selected="isOpen(tab.to)"
        class="tab-pill"
        :class="{ active: isOpen(tab.to) }"
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

// The tab open: its own path or one under it, not one that only starts the
// same (Registration isn't open on /management/registration-dates, say).
const isOpen = (to: string) => route.path === to || route.path.startsWith(`${to}/`)

const tabs = [
  { label: 'Registration', to: '/management/registration' },
  { label: 'Late Registration', to: '/management/late-registration' },
  { label: 'Challenge Start', to: '/management/challenge-start' },
  { label: 'Submission Deadline', to: '/management/submission-deadline' },
  { label: 'Notify Finalists', to: '/management/notify-finalists' },
  { label: 'Finalist Presentation', to: '/management/finalist-presentation' },
  { label: 'Results', to: '/management/results' },
  { label: 'Release Results', to: '/management/release-results' },
  { label: 'Document Setup', to: '/management/document-setup' },
  { label: 'New Year', to: '/management/new-year' }
]
</script>
