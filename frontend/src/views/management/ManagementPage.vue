<template>
  <div class="content-area management">
    <header class="page-header">
      <h1 class="page-title">Management</h1>
      <p class="page-subtitle">
        Set deadlines, grant extensions, manage documents, releases and the new year.
      </p>
    </header>

    <!-- Its sections, as Grading's tabs (each with its icon), the open one
         highlighted on any of its pages. -->
    <nav class="tab-bar tab-bar--main" aria-label="Management sections">
      <RouterLink
        v-for="section in sections"
        :key="section.label"
        :to="section.pages[0]!.to"
        class="tab-pill"
        :class="{ active: section === openSection }"
        :aria-current="section === openSection ? 'true' : undefined"
        data-test="management-section"
      >
        <i :class="['fas', section.icon]" aria-hidden="true"></i>
        <span>{{ section.label }}</span>
      </RouterLink>
    </nav>

    <!-- The open section's own pages, as Grading's components under its tabs:
         only for a section with more than one. -->
    <nav
      v-if="openSection && openSection.pages.length > 1"
      class="tab-bar"
      role="tablist"
      :aria-label="`${openSection.label} pages`"
    >
      <RouterLink
        v-for="page in openSection.pages"
        :key="page.to"
        :to="page.to"
        role="tab"
        :aria-selected="isOpen(page.to)"
        class="tab-pill"
        :class="{ active: isOpen(page.to) }"
      >
        {{ page.label }}
      </RouterLink>
    </nav>

    <router-view />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

// A page open: its own path or one under it, not one that only starts the
// same (Registration isn't open on /management/registration-dates, say).
const isOpen = (to: string) => route.path === to || route.path.startsWith(`${to}/`)

interface ManagementSection {
  label: string
  icon: string
  /** Its pages, in order: the section opens on the first. */
  pages: { label: string; to: string }[]
}

// The year's steps in order, then More.
const sections: ManagementSection[] = [
  {
    label: 'Registration',
    icon: 'fa-user-plus',
    pages: [
      { label: 'Registration', to: '/management/registration' },
      { label: 'Late Registration', to: '/management/late-registration' }
    ]
  },
  {
    label: 'Challenge Start',
    icon: 'fa-flag',
    pages: [{ label: 'Challenge Start', to: '/management/challenge-start' }]
  },
  {
    label: 'Submission Deadline',
    icon: 'fa-file-arrow-up',
    pages: [{ label: 'Submission Deadline', to: '/management/submission-deadline' }]
  },
  {
    label: 'Symposium',
    icon: 'fa-chalkboard-user',
    pages: [
      { label: 'Notify Finalists', to: '/management/notify-finalists' },
      { label: 'Finalist Presentation', to: '/management/finalist-presentation' }
    ]
  },
  {
    label: 'Results',
    icon: 'fa-trophy',
    pages: [
      { label: 'Results', to: '/management/results' },
      { label: 'Release Results', to: '/management/release-results' },
      { label: 'Document Setup', to: '/management/document-setup' }
    ]
  },
  {
    label: 'New Year',
    icon: 'fa-rotate',
    pages: [{ label: 'New Year', to: '/management/new-year' }]
  },
  {
    label: 'More',
    icon: 'fa-ellipsis',
    pages: [
      { label: 'Email Checks', to: '/management/email-checks' },
      { label: 'Known Universities', to: '/management/known-universities' }
    ]
  }
]

const openSection = computed(() => sections.find((section) => section.pages.some((page) => isOpen(page.to))))
</script>
