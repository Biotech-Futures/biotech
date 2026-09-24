<template>
  <div class="content-area grading">
    <header class="grading__hero">
      <div>
        <h1 class="grading__title">Grading</h1>
        <p class="grading__subtitle">Mark submissions by component or group and select finalists.</p>
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

/* Segmented pill switcher — same design as the component switcher on the
   tables below (and the Events page view tabs). */
.grading__tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.3rem;
  margin-bottom: 1.5rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 999px;
  box-shadow: 0 1px 2px var(--shadow);
}

.grading__tab {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 0.5rem 1.1rem;
  font-weight: 600;
  font-size: 0.92rem;
  text-decoration: none;
  transition:
    color 0.18s ease,
    background-color 0.18s ease;
}

/* Hover states set background AND color explicitly so no global rule can
   ever combine into green-on-green (invisible text). */
.grading__tab:hover:not(.grading__tab--active) {
  color: var(--charcoal);
  background: var(--accent-green-soft);
}

.grading__tab--active,
.grading__tab--active:hover {
  background: var(--dark-green);
  color: #fff;
  box-shadow: 0 1px 3px rgba(1, 113, 81, 0.3);
}
</style>
