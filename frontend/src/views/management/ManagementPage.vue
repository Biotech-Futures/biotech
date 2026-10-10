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
        :aria-selected="route.path.startsWith(tab.to)"
        class="tab-pill"
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
  { label: 'Extend Deadline', to: '/management/extend-deadline' },
  { label: 'Notify Finalists', to: '/management/notify-finalists' },
  { label: 'Notify Nonfinalist', to: '/management/email-nonfinalist' },
  { label: 'Finalist Presentation', to: '/management/finalist-presentation' },
  { label: 'Release Results', to: '/management/release-results' },
  { label: 'Document Setup', to: '/management/document-setup' },
  { label: 'New Year', to: '/management/new-year' }
]
</script>
