<template>
  <div class="content-area grading">
    <header class="grading__hero">
      <div>
        <h1 class="grading__title">Grading</h1>
        <p class="grading__subtitle">Mark submissions, release results and manage finalists.</p>
      </div>
    </header>

    <nav class="grading__tabs" aria-label="Grading sections">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.to"
        :to="tab.to"
        class="grading__tab"
        :class="{ 'grading__tab--active': isTabActive(tab) }"
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
    to: '/grading/by-component',
    icon: 'fa-list-check',
    alsoMatches: ['/grading/components']
  },
  {
    label: 'By group',
    to: '/grading/by-group',
    icon: 'fa-users',
    alsoMatches: ['/grading/groups']
  },
  { label: 'Select Finalists', to: '/grading/finalists', icon: 'fa-star' },
  { label: 'Management', to: '/grading/management', icon: 'fa-sliders' }
]

const isTabActive = (tab: GradingTab) => {
  if (route.path.startsWith(tab.to)) return true
  return (tab.alsoMatches || []).some((prefix) => route.path.startsWith(prefix))
}
</script>

<style scoped>
.grading__hero {
  margin-bottom: 1.25rem;
}

.grading__title {
  margin-bottom: 0.25rem;
}

.grading__subtitle {
  color: var(--text-muted);
  margin: 0;
}

.grading__tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-light);
  padding-bottom: 0.75rem;
}

.grading__tab {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.9rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.9rem;
  text-decoration: none;
  transition:
    background-color 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}

/* Hover states set background AND color explicitly so no global rule can
   ever combine into green-on-green (invisible text). */
.grading__tab:hover {
  background: var(--accent-green-soft);
  border-color: var(--dark-green);
  color: var(--dark-green);
}

.grading__tab--active,
.grading__tab--active:hover {
  background: var(--dark-green);
  border-color: var(--dark-green);
  color: #fff;
}
</style>
