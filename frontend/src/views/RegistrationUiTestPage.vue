<template>
  <div class="ui-test-page">
    <header class="ui-test-header">
      <RouterLink to="/register" class="brand-link" aria-label="Return to public registration">
        <img :src="logo" :alt="BRAND_NAME" />
        <span>{{ BRAND_CONNECT }}</span>
      </RouterLink>
      <div class="test-warning" role="status">
        <strong>Development UI test surface</strong>
        <span>Simulated in memory only. No registration data is sent or persisted.</span>
      </div>
    </header>

    <section class="launcher" aria-labelledby="launcher-title">
      <div class="launcher-copy">
        <h1 id="launcher-title">Open an intake journey</h1>
        <p>
          Jump directly into any current registration path. Supervisor journeys use a synthetic,
          display-only account context and do not grant authorization.
        </p>
      </div>
      <div class="journey-launchers">
        <button
          v-for="option in launcherOptions"
          :key="option.value"
          type="button"
          :aria-pressed="selectedJourney === option.value"
          @click="launch(option.value)"
        >
          <span>{{ option.role }}</span>
          <strong>{{ option.label }}</strong>
        </button>
      </div>
    </section>

    <RegistrationDemoPage
      v-if="selectedJourney"
      :key="selectedJourney"
      mode="ui-test"
      :initial-journey="selectedJourney"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import logo from '@/assets/btf-logo.png'
import { BRAND_CONNECT, BRAND_NAME } from '@/constants/brand'
import type { RegistrationIntakeJourney } from '@/registration/registration'
import RegistrationDemoPage from '@/views/RegistrationDemoPage.vue'

const launcherOptions: Array<{
  value: RegistrationIntakeJourney
  role: string
  label: string
}> = [
  { value: 'student_individual', role: 'Student', label: 'Individual student' },
  { value: 'student_team', role: 'Student', label: 'Student team' },
  { value: 'supervisor_individual', role: 'Synthetic supervisor', label: 'One student' },
  { value: 'supervisor_group', role: 'Synthetic supervisor', label: 'Pre-formed group' },
  { value: 'supervisor_csv', role: 'Synthetic supervisor', label: 'CSV import' },
  { value: 'mentor', role: 'Mentor', label: 'Mentor application' },
]

const route = useRoute()
const router = useRouter()
const routeJourney = String(route.query.journey || '')
const selectedJourney = ref<RegistrationIntakeJourney | null>(
  launcherOptions.some((option) => option.value === routeJourney)
    ? (routeJourney as RegistrationIntakeJourney)
    : null,
)

const launch = (journey: RegistrationIntakeJourney) => {
  selectedJourney.value = journey
  void router.replace({ query: { journey } })
}
</script>

<style scoped>
.ui-test-page {
  min-height: 100vh;
  background: #f2f6f1;
  color: #173d33;
  font-family: Arial, Helvetica, sans-serif;
}

.ui-test-header {
  width: min(100% - 40px, 1220px);
  margin-inline: auto;
  padding-block: 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.brand-link {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: inherit;
  font-weight: 800;
  text-decoration: none;
}

.brand-link img {
  width: 44px;
  height: 44px;
  object-fit: contain;
}

.test-warning {
  max-width: 560px;
  padding: 12px 16px;
  display: grid;
  gap: 3px;
  border: 1px solid #b9892c;
  border-radius: 10px;
  background: #fff8df;
  color: #624715;
  font-size: 0.88rem;
}

.launcher {
  width: min(100% - 40px, 1220px);
  margin: 8px auto 28px;
  padding: 28px;
  display: grid;
  grid-template-columns: minmax(240px, 0.8fr) minmax(0, 1.5fr);
  gap: 32px;
  border: 1px solid #d7e2d9;
  border-radius: 18px;
  background: #fff;
}

.launcher-copy h1 {
  margin: 0 0 10px;
  font-size: clamp(1.65rem, 3vw, 2.35rem);
  letter-spacing: -0.025em;
}

.launcher-copy p {
  max-width: 58ch;
  margin: 0;
  color: #526a63;
  line-height: 1.6;
}

.journey-launchers {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.journey-launchers button {
  min-width: 0;
  min-height: 82px;
  padding: 14px;
  display: grid;
  align-content: center;
  gap: 5px;
  border: 1px solid #cbd9ce;
  border-radius: 12px;
  background: #f8fbf8;
  color: #173d33;
  text-align: left;
  cursor: pointer;
}

.journey-launchers button:hover,
.journey-launchers button[aria-pressed='true'] {
  border-color: #08745a;
  background: #edf8f3;
}

.journey-launchers button:focus-visible,
.brand-link:focus-visible {
  outline: 3px solid rgba(8, 116, 90, 0.28);
  outline-offset: 3px;
}

.journey-launchers span {
  color: #60756e;
  font-size: 0.75rem;
  font-weight: 700;
}

.journey-launchers strong {
  overflow-wrap: anywhere;
  font-size: 0.92rem;
}

@media (max-width: 850px) {
  .ui-test-header,
  .launcher {
    width: min(100% - 28px, 1220px);
  }

  .ui-test-header,
  .launcher {
    grid-template-columns: 1fr;
  }

  .ui-test-header {
    align-items: stretch;
    flex-direction: column;
  }
}

@media (max-width: 620px) {
  .launcher {
    padding: 20px;
  }

  .journey-launchers {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
