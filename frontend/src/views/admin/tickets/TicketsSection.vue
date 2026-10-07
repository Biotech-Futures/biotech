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
         in the Admin block of the sidebar instead.

         A labelled nav of links with aria-current, as GradingPage.vue has,
         and not role="tablist". Each option is a link to another address,
         and ARIA tabs promise arrow keys and a tab panel that these do not
         have. RouterLink would set the same aria-current by itself; it is
         written out so that the attribute and the pill read off one check. -->
    <nav class="tickets-section__switcher" aria-label="Support queue sections">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.name"
        :to="{ name: tab.name }"
        :aria-current="route.name === tab.name ? 'page' : undefined"
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
/* The first redesign round (October 2026): a 32px title as on the student
   Support Centre, a slimmer rail, quieter greys. */
.tickets-section__hero {
  margin-bottom: 1rem;
}

/* The design puts the subtitle's letters 160px down the screen; a 4px gap
   under this line box left them at 163. */
.tickets-section__title {
  margin-bottom: 1px;
  font-size: 2rem;
  line-height: 1.1;
  letter-spacing: -0.01em;
}

/* A literal colour rather than --text-muted: this page's ground is
   .content-area's --bg-light, where that token is 4.45:1, under AA. #5a6268
   is the redesign's muted grey, 5.89:1 there; its dark #a3b3ae is 8.34:1 on
   the dark page. */
.tickets-section__subtitle {
  color: #5a6268;
  margin: 0;
}

:root[data-theme='dark'] .tickets-section__subtitle {
  color: #a3b3ae;
}

/* Same pill rail as ManagementPage and GradingPage: one white rounded rail,
   the active option a solid green pill. */
.tickets-section__switcher {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.25rem;
  /* 23px down to the tab's own heading, the same on all three tabs, as the
     design spaces them. */
  margin-bottom: 1.4375rem;
  background: var(--white);
  border: 1px solid #e3e7e5;
  /* Not 999px: with the rail wrapped onto two rows a fully-round radius turns
     into a giant lozenge. 1.4rem still reads as a pill on a single row. */
  border-radius: 1.4rem;
  box-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);
}

/* The designer's dark rail is the card colour, a step up from the page. */
:root[data-theme='dark'] .tickets-section__switcher {
  background: #1d2826;
  border-color: #2b3936;
  box-shadow: 0 1px 2px var(--shadow);
}

.tickets-section__switch {
  border: none;
  background: transparent;
  color: #5a6268;
  border-radius: 999px;
  padding: 0.35rem 1.1rem;
  font-weight: 600;
  font-size: 0.9rem;
  font-family: inherit;
  cursor: pointer;
  text-decoration: none;
  transition:
    color 0.18s ease,
    background-color 0.18s ease;
}

/* #5a6268 on the dark rail would be 2.44:1. */
:root[data-theme='dark'] .tickets-section__switch {
  color: #a3b3ae;
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
}

/* The global focus ring is --dark-green, which the dark theme does not
   redefine: 2.52:1 on the dark rail, under the 3:1 a focus indicator needs.
   --mint-green is 5.52:1 there, the colour the audit, analytics and detail
   rings already use in dark. Checked by ticketsSectionContrast.spec.ts. */
:root[data-theme='dark'] .tickets-section__switch:focus-visible {
  outline-color: var(--mint-green);
}
</style>
