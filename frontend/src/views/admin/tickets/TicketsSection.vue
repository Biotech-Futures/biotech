<template>
  <div class="content-area tickets-section">
    <header class="tickets-section__hero">
      <div>
        <h1 class="tickets-section__title">Support queue</h1>
        <p class="tickets-section__subtitle">
          Work enquiries from across the platform, review every recorded action, and see how
          the queue is doing.
        </p>
      </div>
    </header>

    <!-- The roster (Support agents) is not a tab here. Everyone who can open
         this section can work the queue, and a support agent must never be
         offered the screen that grants the role (adminweb Nav.tsx). It lives
         in the Admin block of the sidebar instead. -->
    <nav class="tickets-section__switcher" role="tablist" aria-label="Support queue sections">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.name"
        :to="{ name: tab.name }"
        role="tab"
        :aria-selected="route.name === tab.name"
        class="tickets-section__switch"
        :class="{ active: route.name === tab.name }"
      >
        {{ tab.label }}
      </RouterLink>
    </nav>

    <router-view />
  </div>
</template>

<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

// Matched by route name, not by path prefix as ManagementPage does: the
// queue's path is a prefix of the other two, so startsWith would keep it lit
// on every tab.
const tabs = [
  { label: 'Queue', name: 'admin-tickets' },
  { label: 'Audit', name: 'admin-tickets-audit' },
  { label: 'Analytics', name: 'admin-tickets-analytics' }
]
</script>

<style scoped>
.tickets-section__hero {
  margin-bottom: 1.25rem;
}

.tickets-section__title {
  margin-bottom: 0.25rem;
}

/* A literal colour rather than --text-muted: this page's ground is
   .content-area's --bg-light, where that token is 4.45:1, under AA. #616970
   is the value TicketDetailPage.vue uses for the same reason (5.29:1 there).
   Dark hands it back to the theme, which is 6.19:1 on its ground. */
.tickets-section__subtitle {
  color: #616970;
  margin: 0;
}

:root[data-theme='dark'] .tickets-section__subtitle {
  color: var(--text-muted);
}

/* Same pill rail as ManagementPage and GradingPage: one white rounded rail,
   the active option a solid green pill. */
.tickets-section__switcher {
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

.tickets-section__switch {
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

/* Hover sets background AND colour so no global rule can combine into
   green-on-green. */
.tickets-section__switch:hover:not(.active) {
  color: var(--charcoal);
  background: var(--accent-green-soft);
}

/* Literal #fff, not var(--white): --white is a surface colour and turns dark
   green-black in the dark theme, 2.79:1 on this green. */
.tickets-section__switch.active {
  background: var(--dark-green);
  color: #fff;
  box-shadow: 0 1px 3px rgba(1, 113, 81, 0.3);
}
</style>
