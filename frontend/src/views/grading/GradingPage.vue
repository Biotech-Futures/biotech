<template>
  <div class="content-area grading" :class="{ 'grading--marking': route.meta.hideSidebar === true }">
    <header class="page-header">
      <h1 class="page-title">Grading</h1>
      <p class="page-subtitle">Mark submissions by component or group and select finalists.</p>
    </header>

    <nav class="tab-bar tab-bar--main" aria-label="Grading sections">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.to"
        :to="tab.to"
        class="tab-pill"
        :class="{ active: isTabActive(tab) }"
      >
        <i :class="['fas', tab.icon]" aria-hidden="true"></i>
        <span>{{ tab.label }}</span>
      </RouterLink>
    </nav>

    <router-view />
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

interface GradingTab {
  label: string
  to: string
  icon: string
  /** Extra path prefixes that should keep this tab highlighted. */
  alsoMatches?: string[]
}

const tabs: GradingTab[] = [
  {
    label: 'By component',
    to: '/grading/components/SAQ',
    icon: 'fa-list-check',
    alsoMatches: ['/grading/components']
  },
  {
    label: 'By group',
    to: '/grading/by-group',
    icon: 'fa-users',
    alsoMatches: ['/grading/groups']
  },
  { label: 'Select Finalists', to: '/grading/finalists', icon: 'fa-star' }
  // Management moved to the admin side nav (its pages keep their URLs).
]

const isTabActive = (tab: GradingTab) => {
  if (route.path.startsWith(tab.to)) return true
  return (tab.alsoMatches || []).some((prefix) => route.path.startsWith(prefix))
}
</script>

<style scoped>
/* The marking panes reach a little past this area's right edge; that
   overhang is cut off rather than giving the page a sideways scrollbar. */
.grading--marking {
  overflow-x: hidden;
}
</style>
